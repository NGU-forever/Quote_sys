"""LLM 计量、成本折算与远端调用防护测试。"""
import os
import unittest
from unittest.mock import patch

from tests import db_support  # noqa: F401  # 统一测试库连接，必须在 app.* 之前导入

from sqlalchemy.orm import sessionmaker

from app.agent.llm_client import (
    OpenAICompatibleClient,
    normalize_usage,
    remote_calls_blocked,
)
from app.agent.metrics import estimate_cost, record_llm_call, summarize_run_llm
from app.core.config import settings
from app.models.llm_call import LlmCall


class UsageNormalizeTests(unittest.TestCase):
    def test_openai_style_usage(self):
        self.assertEqual(
            normalize_usage({"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}),
            {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
        )

    def test_input_output_alias(self):
        self.assertEqual(
            normalize_usage({"input_tokens": 7, "output_tokens": 3}),
            {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
        )

    def test_total_is_derived_when_missing(self):
        usage = normalize_usage({"prompt_tokens": 2, "completion_tokens": 5})
        self.assertEqual(usage["total_tokens"], 7)

    def test_missing_usage_returns_none(self):
        self.assertIsNone(normalize_usage(None))
        self.assertIsNone(normalize_usage("nope"))


class CostTests(unittest.TestCase):
    def test_cost_follows_configured_prices(self):
        with (
            patch.object(settings, "llm_input_price_per_1m", 2.0),
            patch.object(settings, "llm_output_price_per_1m", 8.0),
        ):
            self.assertAlmostEqual(estimate_cost(1_000_000, 1_000_000), 10.0)
            self.assertAlmostEqual(estimate_cost(500_000, 0), 1.0)
            self.assertAlmostEqual(estimate_cost(0, 250_000), 2.0)

    def test_cost_is_zero_without_pricing(self):
        with (
            patch.object(settings, "llm_input_price_per_1m", 0.0),
            patch.object(settings, "llm_output_price_per_1m", 0.0),
        ):
            self.assertEqual(estimate_cost(123456, 7890), 0.0)

    def test_negative_tokens_are_clamped(self):
        with (
            patch.object(settings, "llm_input_price_per_1m", 1.0),
            patch.object(settings, "llm_output_price_per_1m", 1.0),
        ):
            self.assertEqual(estimate_cost(-100, -100), 0.0)


class RecordAndSummarizeTests(unittest.TestCase):
    def setUp(self):
        self.engine = db_support.create_test_engine()
        db_support.reset_schema(self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)

    def tearDown(self):
        self.engine.dispose()

    def test_record_and_summarize(self):
        with self.Session() as db:
            with (
                patch.object(settings, "llm_input_price_per_1m", 2.0),
                patch.object(settings, "llm_output_price_per_1m", 8.0),
                patch.object(settings, "llm_price_currency", "CNY"),
            ):
                record_llm_call(
                    db,
                    run_id=7,
                    node="profiler_node",
                    provider="openai",
                    model="deepseek-chat",
                    prompt_version="v1",
                    usage={"prompt_tokens": 100, "completion_tokens": 20},
                    latency_ms=120,
                )
                record_llm_call(
                    db,
                    run_id=7,
                    node="profiler_node",
                    provider="openai",
                    model="deepseek-chat",
                    prompt_version="v1",
                    usage={"prompt_tokens": 300, "completion_tokens": 30},
                    latency_ms=200,
                )
                record_llm_call(
                    db,
                    run_id=7,
                    node="correction_node",
                    provider="openai",
                    model="deepseek-chat",
                    prompt_version="v1",
                    usage=None,
                    latency_ms=5,
                )
                summary = summarize_run_llm(db, 7)

        self.assertEqual(summary["calls"], 3)
        self.assertEqual(summary["prompt_tokens"], 400)
        self.assertEqual(summary["completion_tokens"], 50)
        self.assertEqual(summary["total_tokens"], 450)
        self.assertEqual(summary["latency_ms"], 325)
        self.assertEqual(summary["currency"], "CNY")
        # 400 prompt × 2/1M + 50 completion × 8/1M = 0.0008 + 0.0004
        self.assertAlmostEqual(summary["cost"], 0.0012, places=6)
        self.assertEqual([item["node"] for item in summary["per_node"]], ["correction_node", "profiler_node"])
        profiler = next(item for item in summary["per_node"] if item["node"] == "profiler_node")
        self.assertEqual(profiler["calls"], 2)
        self.assertEqual(profiler["prompt_tokens"], 400)

    def test_summary_of_unknown_run_is_empty(self):
        with self.Session() as db:
            summary = summarize_run_llm(db, 999999)
            rows = db.query(LlmCall).all()
        self.assertEqual(summary["calls"], 0)
        self.assertEqual(summary["total_tokens"], 0)
        self.assertEqual(summary["per_node"], [])
        self.assertEqual(rows, [])


class RemoteGuardTests(unittest.TestCase):
    def test_blocked_when_test_flag_present(self):
        with patch.dict(os.environ, {"QUOTESYS_TESTING": "1"}, clear=False):
            os.environ.pop("QUOTESYS_ALLOW_REMOTE_LLM", None)
            self.assertTrue(remote_calls_blocked())

    def test_explicit_allow_bypasses_guard(self):
        with patch.dict(
            os.environ,
            {"QUOTESYS_TESTING": "1", "QUOTESYS_ALLOW_REMOTE_LLM": "1"},
            clear=False,
        ):
            self.assertFalse(remote_calls_blocked())

    def test_chat_is_blocked_instead_of_calling_paid_api(self):
        client = OpenAICompatibleClient(
            base_url="https://api.invalid.example/v1", api_key="k", model="m"
        )
        with patch.dict(
            os.environ,
            {"QUOTESYS_TESTING": "1", "QUOTESYS_ALLOW_REMOTE_LLM": "0"},
            clear=False,
        ):
            with self.assertRaises(RuntimeError) as ctx:
                client.chat([{"role": "user", "content": "hi"}], [])
        self.assertIn("测试环境禁止调用真实 LLM 接口", str(ctx.exception))

    def test_auto_provider_warns_before_paid_calls(self):
        from app.agent.agent_service import _provider

        with self.assertLogs("app.agent.agent_service", level="WARNING") as captured:
            provider, name = _provider(
                {
                    "provider": "auto",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-chat",
                    "api_key": "secret",
                }
            )
        self.assertEqual(name, "openai")
        self.assertTrue(provider.__class__.__name__ == "OpenAICompatibleClient")
        self.assertIn("真实 LLM 接口", "\n".join(captured.output))

    def test_mock_provider_never_touches_network(self):
        from app.agent.agent_service import _provider

        provider, name = _provider({"provider": "mock"})
        self.assertEqual(name, "mock")


if __name__ == "__main__":
    unittest.main()
