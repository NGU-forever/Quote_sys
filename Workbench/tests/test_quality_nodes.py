"""仲裁、质检、自愈与状态图拓扑测试。"""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.graph.builder import build_import_graph
from app.agent.graph.nodes.quality import (
    correction_node,
    reconcile_node,
    should_continue_correction,
)
from app.agent.graph.runtime import GraphRuntime
from app.agent.llm_client import LLMResponse, ToolCall
from app.agent.mock_provider import MockProvider
from app.agent.readers.manifest import build_manifest
from app.core.config import settings
from app.db.base import Base
from app.models.device_binding import DeviceBinding  # noqa: F401
from app.models.package import Package  # noqa: F401
from app.models.product import Product  # noqa: F401


class ScriptedProvider:
    def __init__(self, arguments: dict):
        self.arguments = arguments
        self.calls = []

    def chat(self, messages, tool_schemas):
        self.calls.append({"messages": messages, "schema": tool_schemas[0]})
        name = tool_schemas[0]["function"]["name"]
        return LLMResponse(
            tool_calls=[ToolCall(name, self.arguments, call_id="correction")],
            summary="corrected",
        )


class StubbornInvalidProvider:
    def __init__(self):
        self.correction_calls = 0

    def chat(self, messages, tool_schemas):
        name = tool_schemas[0]["function"]["name"]
        invalid_product = {
            "sku_id": "P999",
            "category": "invalid-category",
            "name": "非法商品",
        }
        if name == "extract_products":
            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        name,
                        {"products": [invalid_product], "issues": []},
                        call_id="invalid-products",
                    )
                ],
                summary="invalid products",
            )
        if name == "correct_candidates":
            self.correction_calls += 1
            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        name,
                        {
                            "candidates": {
                                "products": [invalid_product],
                                "packages": [],
                                "bindings": [],
                                "issues": [],
                            }
                        },
                        call_id="still-invalid",
                    )
                ],
                summary="still invalid",
            )
        raise AssertionError(f"unexpected tool: {name}")


def _db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _close_db(db) -> None:
    engine = db.get_bind()
    db.close()
    engine.dispose()


def _initial_state(mode: str = "dry-run") -> dict:
    return {
        "run_id": 1,
        "mode": mode,
        "manifest": {},
        "db_stats": {},
        "sources_plan": {},
        "products_extracted": [],
        "packages_extracted": [],
        "bindings_extracted": [],
        "issues": [],
        "candidates": None,
        "validation_errors": [],
        "retry_count": 0,
        "status": "running",
        "apply_result": {},
        "report": {},
    }


class QualityNodeTests(unittest.TestCase):
    def test_branch_routing_uses_three_retry_limit(self):
        self.assertEqual(
            should_continue_correction(
                {"validation_errors": ["err"], "retry_count": 0}
            ),
            "correction_node",
        )
        self.assertEqual(
            should_continue_correction(
                {"validation_errors": ["err"], "retry_count": 2}
            ),
            "correction_node",
        )
        self.assertEqual(
            should_continue_correction(
                {"validation_errors": ["err"], "retry_count": 3}
            ),
            "fail_node",
        )
        self.assertEqual(
            should_continue_correction(
                {"validation_errors": [], "retry_count": 1}
            ),
            "apply_node",
        )

    def test_reconcile_aligns_unique_natural_language_name(self):
        state = {
            "products_extracted": [
                {
                    "sku_id": "P001",
                    "category": "device",
                    "name": "超声波治疗仪CSY-200（台式）",
                },
                {
                    "sku_id": "C001",
                    "category": "consumable",
                    "name": "超声贴片",
                },
            ],
            "packages_extracted": [
                {
                    "package_id": "PKG001",
                    "name": "推广套餐",
                    "sku_ids": ["CSY-200 台式机", "C001"],
                    "quantities": [1, 2],
                }
            ],
            "bindings_extracted": [],
            "issues": [],
        }
        runtime = GraphRuntime(
            provider=None,
            provider_name="test",
            db=_db_session(),
            cancel_check=lambda: False,
        )
        try:
            result = reconcile_node(state, runtime)
        finally:
            _close_db(runtime.db)

        self.assertEqual(
            result["candidates"]["packages"][0]["sku_ids"],
            ["P001", "C001"],
        )

    def test_correction_receives_exact_errors_and_increments_retry(self):
        corrected = {
            "products": [],
            "packages": [],
            "bindings": [],
            "issues": [],
        }
        provider = ScriptedProvider({"candidates": corrected})
        runtime = GraphRuntime(
            provider=provider,
            provider_name="test",
            db=_db_session(),
            cancel_check=lambda: False,
        )
        try:
            result = correction_node(
                {
                    "candidates": {
                        "products": [],
                        "packages": [
                            {
                                "package_id": "PKG001",
                                "name": "坏套餐",
                                "sku_ids": ["C999"],
                                "quantities": [1],
                            }
                        ],
                        "bindings": [],
                        "issues": [],
                    },
                    "validation_errors": ["套餐 PKG001 引用了不存在的 SKU: C999"],
                    "retry_count": 0,
                    "sources_plan": {"packages": [{"file": "package.md"}]},
                },
                runtime,
            )
        finally:
            _close_db(runtime.db)

        self.assertEqual(result["retry_count"], 1)
        self.assertEqual(result["candidates"]["packages"], [])
        prompt = provider.calls[0]["messages"][1]["content"]
        self.assertIn("C999", prompt)

    def test_correction_cannot_create_packages_without_package_source(self):
        candidate_with_package = {
            "products": [],
            "packages": [
                {
                    "package_id": "PKG999",
                    "name": "模型新增套餐",
                    "sku_ids": ["P001"],
                    "quantities": [1],
                }
            ],
            "bindings": [],
            "issues": [],
        }
        provider = ScriptedProvider({"candidates": candidate_with_package})
        runtime = GraphRuntime(
            provider=provider,
            provider_name="test",
            db=_db_session(),
            cancel_check=lambda: False,
        )
        try:
            result = correction_node(
                {
                    "candidates": candidate_with_package,
                    "validation_errors": ["需要修复"],
                    "retry_count": 1,
                    "sources_plan": {"packages": []},
                },
                runtime,
            )
        finally:
            _close_db(runtime.db)

        self.assertEqual(result["candidates"]["packages"], [])
        self.assertTrue(any("套餐" in issue for issue in result["issues"]))

    def test_compiled_graph_completes_baseline_with_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import openpyxl

            wb = openpyxl.Workbook()
            ws1 = wb.active
            ws1.title = "SKU主表"
            ws1.append(["sku_id", "产品名称", "最低价", "单位", "适用设备", "包装规格", "备注"])
            ws1.append(["P001", "超声波治疗仪CSY-200（台式）", 2500, "台", "", "", ""])
            ws2 = wb.create_sheet("套餐定义表")
            ws2.append(["套餐编号", "套餐名称", "商品组合", "套餐售价", "备注"])
            ws2.append(["PKG001", "超声治疗（台式）推广套餐", "P001*1", 6000, "促销买赠套餐"])
            wb.save(root / "产品最低价格.xlsx")

            db = _db_session()
            runtime = GraphRuntime(
                provider=MockProvider(),
                provider_name="mock",
                db=db,
                cancel_check=lambda: False,
            )
            graph = build_import_graph(runtime, InMemorySaver())
            config = {"configurable": {"thread_id": "quality-e2e"}}
            initial = _initial_state()
            try:
                with patch.object(settings, "assets_dir", str(root)):
                    result = graph.invoke(initial, config=config)
                snapshot = graph.get_state(config)
            finally:
                _close_db(db)

            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(len(result["candidates"]["products"]), 25)
            self.assertEqual(len(result["candidates"]["packages"]), 3)
            self.assertEqual(len(result["candidates"]["bindings"]), 41)
            self.assertEqual(snapshot.values["status"], "succeeded")

    def test_compiled_graph_stops_after_three_failed_corrections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "prices.txt").write_text(
                "设备 P999 非法商品，最低价 10 元/台。\n",
                encoding="utf-8",
            )
            provider = StubbornInvalidProvider()
            db = _db_session()
            runtime = GraphRuntime(
                provider=provider,
                provider_name="mock",
                db=db,
                cancel_check=lambda: False,
            )
            graph = build_import_graph(runtime, None)
            try:
                with patch.object(settings, "assets_dir", tmp):
                    result = graph.invoke(_initial_state("apply"))
            finally:
                _close_db(db)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["retry_count"], 3)
        self.assertEqual(provider.correction_calls, 3)
        self.assertTrue(result["validation_errors"])


if __name__ == "__main__":
    unittest.main()
