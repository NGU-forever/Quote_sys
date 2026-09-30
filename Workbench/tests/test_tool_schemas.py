"""工具 schema 完整性回归。

历史缺陷：``CandidateSet.model_json_schema()`` 后直接 ``pop("$defs")``，
定义被删但 ``$ref: #/$defs/ProductCandidate`` 仍在，DeepSeek 等 strict 服务端会
直接返回 HTTP 400（Pointer '/$defs/ProductCandidate' does not exist）。
本模块确保**所有发给模型的 schema** 都不含 $ref/$defs 残留。
"""
import unittest

from tests import db_support  # noqa: F401  # 统一测试库连接，必须在 app.* 之前导入

from app.agent.graph.nodes.extractors import BINDING_TOOL, PACKAGE_TOOL, PRODUCT_TOOL
from app.agent.graph.nodes.profiler import _profiler_tool_schemas
from app.agent.graph.nodes.quality import _candidate_tool_schema
from app.agent.tool_registry import TOOL_SCHEMAS


def _walk(node, path="$"):
    yield path, node
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, f"{path}[{index}]")


def all_tool_schemas() -> dict[str, dict]:
    """收集全部会发送给模型的工具定义（新增工具必须在此登记）。"""
    schemas = {
        "extract_products": PRODUCT_TOOL,
        "extract_packages": PACKAGE_TOOL,
        "extract_bindings": BINDING_TOOL,
        "correct_candidates": _candidate_tool_schema(),
    }
    for schema in TOOL_SCHEMAS:
        schemas[schema["function"]["name"]] = schema
    for schema in _profiler_tool_schemas():
        schemas[schema["function"]["name"]] = schema
    return schemas


class ToolSchemaTests(unittest.TestCase):
    def test_no_dangling_ref(self):
        for name, schema in all_tool_schemas().items():
            for path, node in _walk(schema):
                if not isinstance(node, dict):
                    continue
                self.assertNotIn("$ref", node, f"{name} 在 {path} 残留 $ref")
                self.assertNotIn("$defs", node, f"{name} 在 {path} 残留 $defs")
                self.assertNotIn("definitions", node, f"{name} 在 {path} 残留 definitions")

    def test_required_keys_are_declared(self):
        for name, schema in all_tool_schemas().items():
            for path, node in _walk(schema):
                if not isinstance(node, dict) or node.get("type") != "object":
                    continue
                properties = node.get("properties") or {}
                for key in node.get("required") or []:
                    self.assertIn(
                        key, properties, f"{name} 在 {path} 的 required 键 {key} 未声明"
                    )

    def test_candidate_nested_models_are_inlined(self):
        schema = _candidate_tool_schema()
        params = schema["function"]["parameters"]
        self.assertEqual(
            sorted(params["properties"].keys()),
            ["bindings", "issues", "packages", "products"],
        )
        product_item = params["properties"]["products"]["items"]
        self.assertEqual(product_item["type"], "object")
        self.assertIn("sku_id", product_item["properties"])
        self.assertIn("category", product_item["properties"])
        self.assertIs(product_item["additionalProperties"], False)

    def test_profiler_tools_exclude_write_paths(self):
        names = {schema["function"]["name"] for schema in _profiler_tool_schemas()}
        self.assertNotIn("propose_candidates", names)
        self.assertNotIn("finish", names)
        self.assertIn("submit_sources_plan", names)


if __name__ == "__main__":
    unittest.main()
