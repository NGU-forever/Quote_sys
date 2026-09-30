"""Specialized structured extraction nodes."""
import json
from typing import Any

from app.agent.graph.runtime import GraphRuntime
from app.agent.graph.state import AgentGraphState
from app.agent.readers.common import safe_file_path
from app.agent.readers.excel_reader import read_excel
from app.agent.readers.text_reader import read_csv, read_markdown, read_text
from app.agent.readers.word_reader import read_word
from app.agent.schemas import BindingCandidate, PackageCandidate, ProductCandidate
from app.agent.schema_utils import inline_json_schema


def _item_schema(model) -> dict:
    return inline_json_schema(model.model_json_schema())


def _tool_schema(tool_name: str, item_key: str, model, description: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    item_key: {
                        "type": "array",
                        "items": _item_schema(model),
                    },
                    "issues": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [item_key],
            },
        },
    }


PRODUCT_TOOL = _tool_schema(
    "extract_products",
    "products",
    ProductCandidate,
    "仅转录资料中明确存在的设备与耗材；没有底价时 min_price 留空。",
)
PACKAGE_TOOL = _tool_schema(
    "extract_packages",
    "packages",
    PackageCandidate,
    "只结构化资料中已经存在的套餐；禁止设计、组合或推测新套餐。",
)
BINDING_TOOL = _tool_schema(
    "extract_bindings",
    "bindings",
    BindingCandidate,
    "只提取资料明确声明的设备与耗材兼容关系。",
)


def _read_source(source: dict) -> dict:
    payload = {
        "file": source.get("file"),
        "type": source.get("type"),
        "locator": source.get("locator") or {},
        "content": None,
        "error": None,
    }
    try:
        path = safe_file_path(source["file"])
        kind = source.get("type")
        locator = source.get("locator") or {}
        if kind == "excel":
            payload["content"] = read_excel(
                path,
                sheet=locator.get("sheet"),
                max_rows=100,
            )
        elif kind == "word":
            payload["content"] = read_word(
                path,
                headings_only=False,
                max_paragraphs=200,
            )
        elif path.suffix.lower() == ".csv":
            payload["content"] = read_csv(path, max_rows=100)
        elif path.suffix.lower() == ".md":
            payload["content"] = read_markdown(path, max_rows=200)
        else:
            payload["content"] = read_text(path, max_lines=200)
    except (KeyError, ValueError, FileNotFoundError, OSError) as exc:
        payload["error"] = str(exc)
    return payload


def _extract_slice(
    state: AgentGraphState,
    runtime: GraphRuntime,
    *,
    source_key: str,
    item_key: str,
    tool_name: str,
    tool_schema: dict,
    instruction: str,
) -> dict:
    runtime.ensure_active()
    sources = (state.get("sources_plan") or {}).get(source_key) or []
    if not sources:
        return {f"{item_key}_extracted": [], "issues": []}

    evidence = [_read_source(source) for source in sources]
    messages = [
        {
            "role": "system",
            "content": (
                f"你是 Workbench 的{source_key}专职提取节点。{instruction}"
                "只允许调用给定函数，不得输出函数以外的说明。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {"sources": evidence},
                ensure_ascii=False,
                default=str,
            ),
        },
    ]
    runtime.ensure_active()
    response = runtime.chat(messages, [tool_schema])
    call = next(
        (
            item
            for item in response.tool_calls
            if item.name == tool_name
        ),
        None,
    )
    if call is None:
        raise RuntimeError(f"{tool_name} 未返回结构化提取结果")
    arguments: dict[str, Any] = call.arguments if isinstance(call.arguments, dict) else {}
    items = arguments.get(item_key)
    if not isinstance(items, list):
        items = []
    issues = arguments.get("issues")
    if not isinstance(issues, list):
        issues = []
    return {
        f"{item_key}_extracted": items,
        "issues": [str(issue) for issue in issues if str(issue).strip()],
    }


def extract_products_node(state: AgentGraphState, runtime: GraphRuntime) -> dict:
    return _extract_slice(
        state,
        runtime,
        source_key="products",
        item_key="products",
        tool_name="extract_products",
        tool_schema=PRODUCT_TOOL,
        instruction=(
            "严格区分 device 与 consumable。min_price 只能是资料明确的底价或最低价；"
            "没有该口径必须留空，不能把零售价、成本价或套餐价填入。"
        ),
    )


def extract_packages_node(state: AgentGraphState, runtime: GraphRuntime) -> dict:
    return _extract_slice(
        state,
        runtime,
        source_key="packages",
        item_key="packages",
        tool_name="extract_packages",
        tool_schema=PACKAGE_TOOL,
        instruction=(
            "你只被授权转写资料中明确存在且可唯一解释的套餐。"
            "禁止根据商品目录自行组合套餐；没有明确套餐时必须返回空数组。"
            "买赠型在 note 中保留原文依据，固定整购型设置 fixed_bundle=true。"
        ),
    )


def extract_bindings_node(state: AgentGraphState, runtime: GraphRuntime) -> dict:
    return _extract_slice(
        state,
        runtime,
        source_key="bindings",
        item_key="bindings",
        tool_name="extract_bindings",
        tool_schema=BINDING_TOOL,
        instruction="只转录明确声明的设备-耗材适配关系，禁止根据产品名称推测。",
    )
