"""来源定位节点（ReAct 工具循环）测试。

覆盖：模型自主选工具 → 服务端执行 → Observation 回灌 → 提交计划 → 服务端校验；
以及 max_steps 硬上限、工具异常降级、无工具调用时的确定性回退。
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import db_support  # noqa: F401  # 统一测试库连接，必须在 app.* 之前导入

from app.agent.graph.nodes.profiler import profiler_node
from app.agent.graph.runtime import GraphRuntime
from app.agent.llm_client import LLMResponse, ToolCall
from app.agent.readers.manifest import build_manifest
from app.core.config import settings


class ScriptedProvider:
    """按脚本返回工具调用，并记录每次收到的 messages（用于断言 Observation 回灌）。"""

    def __init__(self, script: list):
        self.script = list(script)
        self.seen: list[dict] = []

    def chat(self, messages, tool_schemas):
        self.seen.append(
            {
                "messages": json.loads(json.dumps(messages, default=str)),
                "tools": [t["function"]["name"] for t in tool_schemas],
            }
        )
        if not self.script:
            return LLMResponse(summary="没有更多动作")
        item = self.script.pop(0)
        if isinstance(item, LLMResponse):
            return item
        name, args = item
        return LLMResponse(
            tool_calls=[ToolCall(name, args, call_id=f"call-{name}")],
            summary=f"Thought：调用 {name}",
            model="scripted",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            latency_ms=7,
        )


def _state(manifest: dict) -> dict:
    return {
        "run_id": 1,
        "mode": "dry-run",
        "manifest": manifest,
        "db_stats": {"products": 0},
        "sources_plan": {},
        "products_extracted": [],
        "packages_extracted": [],
        "bindings_extracted": [],
        "issues": [],
        "candidates": None,
        "validation_errors": [],
        "retry_count": 0,
        "status": "running",
    }


def _fixture(root: Path) -> None:
    import openpyxl

    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "SKU主表"
    ws1.append(["sku_id", "产品名称", "最低价", "单位", "适用设备"])
    ws1.append(["P001", "超声波治疗仪CSY-200", 2500, "台", "C001"])
    ws2 = wb.create_sheet("套餐定义表")
    ws2.append(["套餐编号", "套餐名称", "商品组合", "套餐售价"])
    ws2.append(["PKG001", "推广套餐", "P001*1", 6000])
    wb.save(root / "产品最低价格.xlsx")
    (root / "notes.md").write_text("# 兼容说明\nC001 适用于 P001。\n", encoding="utf-8")


def _runtime(provider, **kwargs) -> GraphRuntime:
    return GraphRuntime(
        provider=provider,
        provider_name="scripted",
        db=None,
        cancel_check=lambda: False,
        enable_tool_loop=True,
        **kwargs,
    )


class ProfilerReactTests(unittest.TestCase):
    def test_model_driven_plan_with_observation_feedback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture(root)
            provider = ScriptedProvider(
                [
                    ("list_assets", {}),
                    ("read_excel", {"path": "产品最低价格.xlsx", "sheet": "SKU主表"}),
                    (
                        "submit_sources_plan",
                        {
                            "products": [{"file": "产品最低价格.xlsx", "sheet": "SKU主表"}],
                            "packages": [{"file": "产品最低价格.xlsx", "sheet": "套餐定义表"}],
                            "bindings": [{"file": "notes.md", "section": "兼容说明"}],
                            "issues": ["资料未给出耗材单价"],
                        },
                    ),
                ]
            )
            with patch.object(settings, "assets_dir", str(root)):
                manifest = build_manifest(root)
                result = profiler_node(_state(manifest), _runtime(provider, max_steps=6))

        plan = result["sources_plan"]
        self.assertEqual(
            [item["file"] for item in plan["products"]], ["产品最低价格.xlsx"]
        )
        self.assertEqual(plan["products"][0]["locator"]["sheet"], "SKU主表")
        self.assertEqual(plan["packages"][0]["locator"]["sheet"], "套餐定义表")
        self.assertEqual(plan["bindings"][0]["locator"]["section"], "兼容说明")
        self.assertIn("资料未给出耗材单价", result["issues"])

        # Observation 必须回灌给模型：第二次调用应看到 role=tool 的读取结果
        second_call = provider.seen[1]["messages"]
        self.assertTrue(
            any(message.get("role") == "tool" for message in second_call),
            second_call,
        )
        # 工具集里只有只读探测工具 + 提交工具
        self.assertNotIn("propose_candidates", provider.seen[0]["tools"])
        self.assertIn("submit_sources_plan", provider.seen[0]["tools"])
        self.assertEqual(len(result["react_trace"]), 6)  # 3 步 × (assistant + tool)

    def test_invalid_sources_are_dropped_by_server_side_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture(root)
            provider = ScriptedProvider(
                [
                    (
                        "submit_sources_plan",
                        {
                            "products": [
                                {"file": "不存在.xlsx", "sheet": "SKU主表"},
                                {"file": "产品最低价格.xlsx", "sheet": "不存在的工作表"},
                                {"file": "产品最低价格.xlsx", "sheet": "SKU主表"},
                            ],
                            "packages": [],
                            "bindings": [],
                        },
                    )
                ]
            )
            with patch.object(settings, "assets_dir", str(root)):
                result = profiler_node(
                    _state(build_manifest(root)), _runtime(provider, max_steps=3)
                )

        files = [item["file"] for item in result["sources_plan"]["products"]]
        self.assertEqual(files, ["产品最低价格.xlsx"])
        # 非法工作表降级为文件级来源，随后被同文件的精确来源去重覆盖
        self.assertEqual(
            result["sources_plan"]["products"][0]["locator"]["sheet"], "SKU主表"
        )
        joined = " ".join(result["issues"])
        self.assertIn("不存在.xlsx", joined)
        self.assertIn("不存在的工作表", joined)

    def test_max_steps_is_enforced_and_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture(root)
            provider = ScriptedProvider([("list_assets", {})] * 10)
            with patch.object(settings, "assets_dir", str(root)):
                result = profiler_node(
                    _state(build_manifest(root)), _runtime(provider, max_steps=3)
                )

        self.assertEqual(len(provider.seen), 3, "模型调用次数必须被 max_steps 限制")
        self.assertTrue(
            any("max_steps" in issue for issue in result["issues"]), result["issues"]
        )
        # 兜底：规则定位仍然给出了来源
        self.assertTrue(result["sources_plan"]["products"])

    def test_no_tool_call_falls_back_silently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture(root)
            provider = ScriptedProvider([LLMResponse(summary="我不打算调用工具")])
            with patch.object(settings, "assets_dir", str(root)):
                result = profiler_node(
                    _state(build_manifest(root)), _runtime(provider, max_steps=3)
                )

        self.assertEqual(result["issues"], [])
        self.assertTrue(result["sources_plan"]["products"])

    def test_tool_errors_become_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture(root)
            provider = ScriptedProvider(
                [
                    ("read_excel", {"path": "../../etc/passwd"}),
                    (
                        "submit_sources_plan",
                        {"products": [{"file": "产品最低价格.xlsx"}], "packages": [], "bindings": []},
                    ),
                ]
            )
            with patch.object(settings, "assets_dir", str(root)):
                result = profiler_node(
                    _state(build_manifest(root)), _runtime(provider, max_steps=4)
                )

        # 越界路径被沙箱拒绝，但只是 Observation，循环继续并成功提交
        tool_message = provider.seen[1]["messages"][-1]
        self.assertEqual(tool_message["role"], "tool")
        self.assertIn("非法文件路径", tool_message["content"])
        self.assertEqual(
            [item["file"] for item in result["sources_plan"]["products"]],
            ["产品最低价格.xlsx"],
        )

    def test_tool_loop_disabled_uses_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture(root)
            provider = ScriptedProvider([("list_assets", {})])
            with patch.object(settings, "assets_dir", str(root)):
                result = profiler_node(
                    _state(build_manifest(root)),
                    GraphRuntime(
                        provider=provider,
                        provider_name="mock",
                        db=None,
                        cancel_check=lambda: False,
                    ),
                )

        self.assertEqual(provider.seen, [], "未启用工具循环时不应调用模型")
        self.assertTrue(result["sources_plan"]["products"])


if __name__ == "__main__":
    unittest.main()
