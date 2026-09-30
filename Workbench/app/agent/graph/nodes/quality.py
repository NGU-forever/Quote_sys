"""Reconciliation, hard validation, correction and persistence nodes."""
import json
import re
from difflib import SequenceMatcher

from sqlalchemy import select

from app.agent import persistence, validation
from app.agent.graph.runtime import GraphRuntime
from app.agent.graph.state import AgentGraphState
from app.agent.schemas import CandidateSet
from app.agent.schema_utils import function_tool_schema
from app.models.product import Product


def _normalized(value: object) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _model_codes(value: object) -> set[str]:
    return {
        "".join(ch for ch in token.lower() if ch.isalnum())
        for token in re.findall(r"[A-Za-z]{1,8}[-_ ]?\d{2,}", str(value or ""))
    }


def _alias_targets(
    products: list[dict],
    existing_products: list[Product],
) -> tuple[set[str], dict[str, set[str]]]:
    known = {
        str(product.get("sku_id"))
        for product in products
        if product.get("sku_id")
    }
    known.update(product.sku_id for product in existing_products)
    aliases: dict[str, set[str]] = {sku: {_normalized(sku)} for sku in known}
    for product in products:
        sku = str(product.get("sku_id") or "")
        if sku:
            aliases.setdefault(sku, set()).add(_normalized(product.get("name")))
    for product in existing_products:
        aliases.setdefault(product.sku_id, set()).add(_normalized(product.name))
    return known, aliases


def _resolve_reference(
    reference: object,
    known: set[str],
    aliases: dict[str, set[str]],
) -> tuple[str | None, str | None]:
    ref = str(reference or "").strip()
    if not ref:
        return None, "空 SKU 引用已被移除"
    if ref in known:
        return ref, None

    normalized_ref = _normalized(ref)
    ref_codes = _model_codes(ref)
    matches: set[str] = set()
    for sku, values in aliases.items():
        cleaned_values = {value for value in values if value}
        exact = normalized_ref in cleaned_values
        contained = any(
            len(value) >= 4
            and (value in normalized_ref or normalized_ref in value)
            for value in cleaned_values
        )
        model_match = bool(
            ref_codes
            and any(ref_codes & _model_codes(value) for value in values)
        )
        fuzzy = any(
            len(value) >= 6
            and SequenceMatcher(None, normalized_ref, value).ratio() >= 0.72
            for value in cleaned_values
        )
        if exact or contained or model_match or fuzzy:
            matches.add(sku)

    if len(matches) == 1:
        return next(iter(matches)), None
    if not matches:
        return None, f"无法在商品中唯一定位引用“{ref}”，已移除"
    return None, f"引用“{ref}”同时匹配 {', '.join(sorted(matches))}，已移除"


def reconcile_node(state: AgentGraphState, runtime: GraphRuntime) -> dict:
    """Align natural-language references to canonical product SKUs."""
    products = list(state.get("products_extracted") or [])
    raw_packages = list(state.get("packages_extracted") or [])
    raw_bindings = list(state.get("bindings_extracted") or [])
    existing_products = []
    if runtime.db is not None:
        # 只取 sku_id / name 两列：别名解析需要全量 SKU，但无需实体对象
        existing_products = list(
            runtime.db.execute(select(Product.sku_id, Product.name)).all()
        )
    known, aliases = _alias_targets(products, existing_products)

    issues: list[str] = []
    packages: list[dict] = []
    for package in raw_packages:
        item = dict(package)
        resolved: list[str] = []
        failed = False
        for reference in item.get("sku_ids") or []:
            sku, issue = _resolve_reference(reference, known, aliases)
            if issue:
                issues.append(f"套餐 {item.get('package_id', '')}：{issue}")
                failed = True
                break
            resolved.append(sku)
        if failed:
            continue
        item["sku_ids"] = resolved
        packages.append(item)

    bindings: list[dict] = []
    for binding in raw_bindings:
        device, device_issue = _resolve_reference(
            binding.get("device_sku_id"), known, aliases
        )
        consumable, consumable_issue = _resolve_reference(
            binding.get("consumable_sku_id"), known, aliases
        )
        if device_issue:
            issues.append(f"绑定设备：{device_issue}")
        if consumable_issue:
            issues.append(f"绑定耗材：{consumable_issue}")
        if device and consumable:
            bindings.append(
                {
                    "device_sku_id": device,
                    "consumable_sku_id": consumable,
                }
            )

    inherited_issues = list(
        dict.fromkeys(str(issue) for issue in state.get("issues") or [] if str(issue).strip())
    )
    candidates = {
        "products": products,
        "packages": packages,
        "bindings": bindings,
        "issues": list(dict.fromkeys(inherited_issues + issues)),
    }
    return {"candidates": candidates, "issues": issues}


def validate_node(state: AgentGraphState, runtime: GraphRuntime) -> dict:
    """Run the existing server-side hard validation as the graph gate."""
    if runtime.db is None:
        raise RuntimeError("validate_node 需要数据库会话")
    runtime.ensure_active()
    current = state.get("candidates") or {
        "products": [],
        "packages": [],
        "bindings": [],
        "issues": list(state.get("issues") or []),
    }
    normalized, _, errors = validation.validate_candidates(current, runtime.db)
    if errors and not (
        normalized.get("products")
        or normalized.get("packages")
        or normalized.get("bindings")
    ):
        normalized = dict(current)
    normalized["issues"] = list(
        dict.fromkeys(
            [
                *(current.get("issues") or []),
                *(state.get("issues") or []),
            ]
        )
    )
    return {"candidates": normalized, "validation_errors": errors, "issues": []}


def should_continue_correction(state: AgentGraphState) -> str:
    errors = state.get("validation_errors") or []
    if not errors:
        return "apply_node"
    if int(state.get("retry_count") or 0) < 3:
        return "correction_node"
    return "fail_node"


def _candidate_tool_schema() -> dict:
    """修复工具的 parameters：内联 $ref，避免 strict 服务端因悬空引用返回 400。"""
    return function_tool_schema(
        "correct_candidates",
        "仅修复给定错误，不新增无资料依据的套餐或 SKU。",
        CandidateSet.model_json_schema(),
    )


def correction_node(state: AgentGraphState, runtime: GraphRuntime) -> dict:
    """Send only the current candidate set and exact errors back to the model."""
    runtime.ensure_active()
    candidates = state.get("candidates") or {
        "products": [],
        "packages": [],
        "bindings": [],
        "issues": [],
    }
    messages = [
        {
            "role": "system",
            "content": (
                "你是 Workbench 候选数据修复节点。只修复给定错误和相关条目，"
                "不得新增或组合套餐；若资料没有套餐依据，packages 必须保持空数组。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "validation_errors": state.get("validation_errors") or [],
                    "candidates": candidates,
                },
                ensure_ascii=False,
                default=str,
            )[:60000],
        },
    ]
    runtime.ensure_active()
    response = runtime.chat(messages, [_candidate_tool_schema()])
    call = next(
        (
            item
            for item in response.tool_calls
            if item.name == "correct_candidates"
        ),
        None,
    )
    if call is None:
        raise RuntimeError("correct_candidates 未返回修复结果")
    arguments = call.arguments if isinstance(call.arguments, dict) else {}
    corrected = arguments.get("candidates") or arguments
    if not isinstance(corrected, dict):
        corrected = candidates
    corrected = {
        "products": list(corrected.get("products") or []),
        "packages": list(corrected.get("packages") or []),
        "bindings": list(corrected.get("bindings") or []),
        "issues": list(corrected.get("issues") or []),
    }
    issues = [str(issue) for issue in corrected["issues"] if str(issue).strip()]
    # 证据约束：自愈只能修复或删减，不能凭空新增没有资料依据的商品/套餐
    plan = state.get("sources_plan") or {}
    if not (plan.get("products") or []) and corrected["products"]:
        corrected["products"] = []
        issues.append("资料中没有商品依据，已拒绝自愈节点新增商品")
    if not (plan.get("packages") or []) and corrected["packages"]:
        corrected["packages"] = []
        issues.append("资料中没有套餐依据，已拒绝自愈节点新增套餐")
    corrected["issues"] = list(
        dict.fromkeys([*(candidates.get("issues") or []), *issues])
    )
    return {
        "candidates": corrected,
        "issues": issues,
        "retry_count": int(state.get("retry_count") or 0) + 1,
    }


def fail_node(state: AgentGraphState, runtime: GraphRuntime) -> dict:
    if runtime.db is not None:
        runtime.db.rollback()
    return {"status": "failed"}


def apply_node(state: AgentGraphState, runtime: GraphRuntime) -> dict:
    runtime.ensure_active()
    if state.get("validation_errors"):
        raise RuntimeError("质检未通过，禁止进入入库节点")
    if runtime.db is None:
        raise RuntimeError("apply_node 需要数据库会话")
    result = persistence.apply_candidates(
        runtime.db,
        state.get("candidates") or {},
        str(state.get("mode") or "dry-run"),
    )
    return {"apply_result": result, "status": "succeeded"}


def report_node(state: AgentGraphState, runtime: GraphRuntime) -> dict:
    candidates = state.get("candidates") or {}
    result = state.get("apply_result") or {
        "mode": state.get("mode"),
        "products_added": 0,
        "products_updated": 0,
        "products_skipped": 0,
        "packages_added": 0,
        "packages_updated": 0,
        "packages_skipped": 0,
        "bindings_added": 0,
        "bindings_skipped": 0,
        "issues": [],
    }
    issues = list(
        dict.fromkeys(
            [
                *(candidates.get("issues") or []),
                *(result.get("issues") or []),
                *(state.get("issues") or []),
            ]
        )
    )
    result["issues"] = issues
    return {
        "apply_result": result,
        "report": {
            "mode": state.get("mode"),
            "provider": runtime.provider_name,
            "summary": result,
            "issues": issues,
        },
    }
