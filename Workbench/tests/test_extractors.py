"""专职提取节点与离线 MockProvider 测试。"""
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app.agent.graph.nodes.extractors import (
    extract_bindings_node,
    extract_packages_node,
    extract_products_node,
)
from app.agent.graph.runtime import GraphRuntime
from app.agent.llm_client import LLMResponse, ToolCall
from app.agent.mock_provider import MockProvider
from app.agent.readers.manifest import build_manifest
from app.core.config import settings


class ScriptedProvider:
    def __init__(self, payloads: dict):
        self.payloads = payloads
        self.calls = []

    def chat(self, messages, tool_schemas):
        name = tool_schemas[0]["function"]["name"]
        self.calls.append({"messages": messages, "schema": tool_schemas[0]})
        return LLMResponse(
            tool_calls=[ToolCall(name, self.payloads[name], call_id=f"test-{name}")],
            summary=f"test {name}",
        )


def _runtime(provider) -> GraphRuntime:
    return GraphRuntime(
        provider=provider,
        provider_name="mock",
        db=None,
        cancel_check=lambda: False,
    )


class ExtractorNodeTests(unittest.TestCase):
    def test_runtime_retries_transient_transport_errors(self):
        class FlakyProvider:
            def __init__(self):
                self.calls = 0

            def chat(self, messages, tool_schemas):
                self.calls += 1
                if self.calls == 1:
                    raise httpx.TransportError("temporary")
                return LLMResponse(summary="recovered")

        provider = FlakyProvider()
        runtime = _runtime(provider)
        with patch("app.agent.graph.runtime.time.sleep"):
            response = runtime.chat([], [])

        self.assertEqual(provider.calls, 2)
        self.assertEqual(response.summary, "recovered")

    def test_packages_with_no_source_skip_provider(self):
        class NeverCalled:
            def chat(self, messages, tool_schemas):
                raise AssertionError("无套餐来源时不应调用 provider")

        result = extract_packages_node(
            {"sources_plan": {"packages": []}},
            _runtime(NeverCalled()),
        )

        self.assertEqual(result["packages_extracted"], [])
        self.assertEqual(result["issues"], [])

    def test_product_extractor_calls_single_structured_tool(self):
        root = Path(__file__).resolve().parents[2] / "assets"
        product = {
            "sku_id": "P001",
            "category": "device",
            "name": "超声波治疗仪CSY-200（台式）",
            "min_price": 2500,
        }
        provider = ScriptedProvider(
            {"extract_products": {"products": [product], "issues": []}}
        )
        manifest = build_manifest(root)
        source = {
            "file": "产品最低价格.xlsx",
            "type": "excel",
            "locator": {"sheet": "SKU主表"},
        }
        state = {"sources_plan": {"products": [source]}, "manifest": manifest}

        with patch.object(settings, "assets_dir", str(root)):
            result = extract_products_node(state, _runtime(provider))

        self.assertEqual(result["products_extracted"], [product])
        self.assertEqual(
            provider.calls[0]["schema"]["function"]["name"],
            "extract_products",
        )
        self.assertIn("SKU主表", provider.calls[0]["messages"][1]["content"])

    def test_package_and_binding_extractors_return_structured_slices(self):
        package = {
            "package_id": "PKG001",
            "name": "推广套餐",
            "sku_ids": ["P001", "C001"],
            "quantities": [1, 2],
            "fixed_bundle": False,
        }
        binding = {"device_sku_id": "P001", "consumable_sku_id": "C001"}
        provider = ScriptedProvider(
            {
                "extract_packages": {"packages": [package], "issues": ["原文档"]},
                "extract_bindings": {"bindings": [binding], "issues": []},
            }
        )

        package_result = extract_packages_node(
            {
                "sources_plan": {
                    "packages": [
                        {
                            "file": "business.md",
                            "type": "text",
                            "locator": {"section": "套餐说明"},
                        }
                    ]
                },
                "manifest": {
                    "files": [
                        {
                            "path": "business.md",
                            "type": "text",
                            "supported": True,
                        }
                    ]
                },
            },
            _runtime(provider),
        )
        binding_result = extract_bindings_node(
            {
                "sources_plan": {
                    "bindings": [
                        {
                            "file": "business.md",
                            "type": "text",
                            "locator": {"section": "适配关系"},
                        }
                    ]
                },
                "manifest": {
                    "files": [
                        {
                            "path": "business.md",
                            "type": "text",
                            "supported": True,
                        }
                    ]
                },
            },
            _runtime(provider),
        )

        self.assertEqual(package_result["packages_extracted"], [package])
        self.assertEqual(binding_result["bindings_extracted"], [binding])
        self.assertEqual(
            [call["schema"]["function"]["name"] for call in provider.calls],
            ["extract_packages", "extract_bindings"],
        )

    def test_mock_provider_preserves_baseline_candidate_counts(self):
        root = Path(__file__).resolve().parents[2] / "assets"
        provider = MockProvider()
        runtime = _runtime(provider)
        with patch.object(settings, "assets_dir", str(root)):
            products = extract_products_node(
                {
                    "sources_plan": {
                        "products": [
                            {
                                "file": "产品最低价格.xlsx",
                                "type": "excel",
                                "locator": {"sheet": "SKU主表"},
                            }
                        ]
                    }
                },
                runtime,
            )
            packages = extract_packages_node(
                {
                    "sources_plan": {
                        "packages": [
                            {
                                "file": "产品最低价格.xlsx",
                                "type": "excel",
                                "locator": {"sheet": "套餐定义表"},
                            }
                        ]
                    }
                },
                runtime,
            )
            bindings = extract_bindings_node(
                {
                    "sources_plan": {
                        "bindings": [
                            {
                                "file": "产品最低价格.xlsx",
                                "type": "excel",
                                "locator": {"sheet": "SKU主表", "column": "适用设备"},
                            }
                        ]
                    }
                },
                runtime,
            )

        self.assertEqual(len(products["products_extracted"]), 25)
        self.assertEqual(len(packages["packages_extracted"]), 3)
        self.assertEqual(len(bindings["bindings_extracted"]), 41)


if __name__ == "__main__":
    unittest.main()
