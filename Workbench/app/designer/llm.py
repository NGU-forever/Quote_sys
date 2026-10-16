"""设计器的 LLM 增强层：受约束的模型输出 + 有界自愈。

设计文档 §2 D3 / §4.4 / §14 M4：
- 模型只做两件事：① 资料 → 业务画像 ② 文案与术语本地化；
- 规则优先：没有模型（未配置接口 / 离线 / 调用失败）时全部走规则，功能不降级；
- 有界自愈：模型给出的字段/结构若被三道门拒绝，把**具体错误**回传，最多 3 次，
  仍不通过则回退规则 Spec——错误永远不会抛给终端用户。
"""
from __future__ import annotations

import json
from typing import Any, Callable

from app.designer.schema import get_db_fields_registry
from app.designer.validator import validate_and_repair_spec

MAX_ATTEMPTS = 3

# 触发重试的校验问题特征：只认"模型提案被拒绝"，
# 良性修复（如"缺少 screens 已回退默认"）不应触发重试。
_VIOLATION_MARKERS = (
    "非法字段",
    "过滤后为空",
    "不在骨架",
    "未知 Block",
    "非法模块",
    "非法骨架",
    "非法 preset_id",
    "非法 density",
)


ENRICHMENT_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_design_enrichment",
        "description": (
            "提交报价系统的业务画像与界面文案：行业、售卖方式、开单场景、定价口径、"
            "字段术语标签、列表列建议。字段名必须来自给定白名单。"
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "profile": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "industry": {
                            "type": "string",
                            "enum": ["medical", "industrial", "service", "retail", "other"],
                        },
                        "sell_mode": {
                            "type": "string",
                            "enum": [
                                "device_only",
                                "consumable_only",
                                "device_with_consumable",
                                "service",
                                "mixed",
                            ],
                        },
                        "scene": {
                            "type": "string",
                            "enum": ["on_site", "office", "customer_self", "mobile"],
                        },
                        "pricing_mode": {
                            "type": "string",
                            "enum": ["floor_price", "negotiable", "tiered", "bundle_fixed"],
                        },
                        "category_name": {"type": "string"},
                        "tone": {"type": "string"},
                    },
                    "required": ["industry", "sell_mode", "scene", "pricing_mode"],
                },
                "labels": {
                    "type": "object",
                    "description": "按实体覆盖字段标签，例如 product.min_price = 供货价",
                    "additionalProperties": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "list_columns": {
                    "type": "object",
                    "description": "按实体建议列表列，字段名必须在白名单内",
                    "additionalProperties": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "issues": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["profile"],
        },
    },
}


SYSTEM_PROMPT = """你是报价系统的方案设计师，负责两件事：
1. 依据给定的真实数据与资料片段，判断这家企业是怎么做生意的（行业、售卖方式、开单场景、定价口径）；
2. 给出界面上的字段术语（例如 min_price 该叫"最低底价"还是"供货价"）与列表列建议。

硬约束：
- 只能调用 submit_design_enrichment，不要输出其它内容；
- list_columns 里的字段名必须来自给定的字段白名单，不得发明字段名；
- 不确定就少给，宁可留空也不要猜；价格与合同条款文本不要臆造。"""


def is_violation(issue: str) -> bool:
    """判断该问题是否属于"模型提案被门禁拒绝"（需要回传重试）。"""
    if not isinstance(issue, str):
        return False
    return any(marker in issue for marker in _VIOLATION_MARKERS)


def merge_enrichment(spec: dict, payload: dict) -> dict:
    """把模型返回的画像/标签/列建议合并进 Spec（不修改入参）。"""
    merged = json.loads(json.dumps(spec, ensure_ascii=False, default=str))

    profile = payload.get("profile")
    if isinstance(profile, dict):
        target = merged.setdefault("profile", {})
        for key in ("industry", "sell_mode", "scene", "pricing_mode", "category_name", "tone"):
            value = profile.get(key)
            if value:
                target[key] = value

    labels = payload.get("labels")
    if isinstance(labels, dict):
        for entity, fields in labels.items():
            if not isinstance(fields, dict):
                continue
            entity_config = merged.setdefault("entities", {}).setdefault(entity, {})
            entity_labels = entity_config.setdefault("labels", {})
            for key, value in fields.items():
                if value:
                    entity_labels[str(key)] = str(value)

    columns = payload.get("list_columns")
    if isinstance(columns, dict):
        for entity, keys in columns.items():
            if isinstance(keys, list) and keys:
                merged.setdefault("entities", {}).setdefault(entity, {})[
                    "list_columns"
                ] = list(keys)

    issues = [str(item) for item in (payload.get("issues") or []) if str(item).strip()]
    if issues:
        merged.setdefault("meta", {})["llm_issues"] = issues
    merged.setdefault("meta", {})["llm_enriched"] = True
    return merged


def _build_user_prompt(spec: dict, digest: dict, previous_errors: list[str]) -> str:
    payload: dict[str, Any] = {
        "existing_db_stats": digest.get("signals") or {},
        "allowed_fields": get_db_fields_registry(),
        "assets_digest": digest.get("assets") or [],
        "terminology_hints": digest.get("terminology_hints") or {},
        "current_spec_hint": {
            "preset_id": (spec.get("style") or {}).get("preset_id"),
            "skeleton": ((spec.get("screens") or [{}])[0] or {}).get("skeleton"),
            "modules": spec.get("modules") or [],
        },
    }
    if previous_errors:
        payload["previous_validation_errors"] = previous_errors
        payload["instruction"] = "上次提交被服务端校验拒绝，请依据错误修正后重新提交。"
    return json.dumps(payload, ensure_ascii=False, default=str)[:20000]


def resolve_provider(db: Any) -> Any:
    """解析设计器可用的模型客户端。

    与 Agent 共用同一套解析逻辑（含 provider=auto 命中真实接口时的告警）；
    mock / 未配置 / 解析失败一律返回 None —— 设计器此时全程走规则。
    """
    try:
        from app.agent.agent_service import _provider
        from app.services.agent_config_service import get_agent_ai

        client, name = _provider(get_agent_ai(db))
    except Exception:
        return None
    return client if name != "mock" else None


def enrich_spec_with_llm(
    spec: dict,
    digest: dict,
    provider: Any,
    max_attempts: int = MAX_ATTEMPTS,
    on_attempt: Callable[[dict], None] | None = None,
) -> tuple[dict, list[str], int]:
    """用模型增强 Spec，带**有界自愈**。

    返回 (最终 spec, issues, 实际尝试次数)。provider 为 None 时原样返回（离线模式）。
    """
    if provider is None:
        return spec, [], 0

    errors: list[str] = []
    for attempt in range(1, max_attempts + 1):
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(spec, digest, errors)},
        ]
        try:
            response = provider.chat(messages, [ENRICHMENT_TOOL])
        except Exception as exc:  # 模型不可用：直接回退规则 Spec，不影响出结果
            return spec, [f"模型调用失败，已回退规则方案：{exc}"], attempt

        call = next(
            (item for item in (getattr(response, "tool_calls", None) or []) if item.name == ENRICHMENT_TOOL["function"]["name"]),
            None,
        )
        if call is None or not isinstance(call.arguments, dict):
            errors = ["未返回 submit_design_enrichment 结构化结果"]
        else:
            candidate = merge_enrichment(spec, call.arguments)
            repaired, issues = validate_and_repair_spec(candidate)
            violations = [issue for issue in issues if is_violation(issue)]
            if not violations:
                return repaired, issues, attempt
            errors = violations

        if on_attempt is not None:
            on_attempt({"attempt": attempt, "errors": list(errors)})

    return spec, [
        f"模型增强在 {max_attempts} 次自愈后仍未通过校验，已回退规则 Spec",
        *errors,
    ], max_attempts
