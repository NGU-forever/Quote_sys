"""JSON Schema 工具：把 Pydantic 产物内联成自包含的 function parameters。

背景：``Model.model_json_schema()`` 对嵌套模型使用 ``$defs`` + ``$ref`` 复用定义。
历史实现直接 ``schema.pop("$defs")``，定义被删掉但 ``$ref`` 仍在，strict 服务端
（如 DeepSeek / OpenAI）会直接拒绝并返回 HTTP 400：

    Invalid schema for function 'correct_candidates':
    Pointer '/$defs/ProductCandidate' does not exist

这里统一递归内联 ``$ref``，产出既不依赖 ``$defs``、也不残留 ``$ref`` 的 schema，
对任何服务端都安全。所有发送给模型的工具 schema 都必须走这里。
"""
from __future__ import annotations

import copy
from typing import Any

_REF_PREFIXES = ("#/$defs/", "#/definitions/")
_MAX_DEPTH = 40


def _resolve(node: Any, defs: dict, depth: int = 0) -> Any:
    if depth > _MAX_DEPTH:
        raise ValueError("JSON Schema $ref 嵌套过深，疑似循环引用")
    if isinstance(node, list):
        return [_resolve(item, defs, depth + 1) for item in node]
    if not isinstance(node, dict):
        return node

    ref = node.get("$ref")
    if isinstance(ref, str):
        target: Any = None
        for prefix in _REF_PREFIXES:
            if ref.startswith(prefix):
                target = defs.get(ref[len(prefix) :])
                break
        if target is None:
            raise ValueError(f"无法解析的 $ref：{ref}")
        merged = _resolve(target, defs, depth + 1)
        extras = {key: value for key, value in node.items() if key != "$ref"}
        if extras and isinstance(merged, dict):
            merged = {
                **merged,
                **{key: _resolve(value, defs, depth + 1) for key, value in extras.items()},
            }
        return merged

    local_defs = node.get("$defs") or node.get("definitions") or {}
    scoped = {**defs, **local_defs} if local_defs else defs
    return {
        key: _resolve(value, scoped, depth + 1)
        for key, value in node.items()
        if key not in ("$defs", "definitions")
    }


def inline_json_schema(schema: dict) -> dict:
    """返回内联展开后的 schema 副本（不修改入参）。"""
    root = copy.deepcopy(schema or {})
    defs = root.get("$defs") or root.get("definitions") or {}
    stripped = {k: v for k, v in root.items() if k not in ("$defs", "definitions")}
    return _resolve(stripped, defs)


def function_tool_schema(name: str, description: str, schema: dict) -> dict:
    """组装 OpenAI 兼容的 function tool 定义，parameters 中不再含 $ref/$defs。"""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": inline_json_schema(schema),
        },
    }
