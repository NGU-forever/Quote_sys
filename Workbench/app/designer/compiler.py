"""向导答案编译器：规则优先生成 UiSpec，模型只做画像与文案增强。

设计文档 §2 D3：约 70% 的 Spec 由确定性规则产出；
模型（可选）只在两处介入：业务画像、字段术语与列建议；
全部输出必须过三道门，模型提案被拒绝时走有界自愈（最多 3 次）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.designer.llm import enrich_spec_with_llm
from app.designer.navigation import rebuild_navigation
from app.designer.profiles import rule_based_profile
from app.designer.schema import get_fallback_spec
from app.designer.terminology import localize_field_labels, merge_labels
from app.designer.validator import validate_and_repair_spec


# 枚举码 → 人话。向导/画像传进来的是代码，摘要却是给老板看的中文，
# 缺了这层映射就会把 on_site / floor_price / print_a4 直接写进句子。
INDUSTRY_LABELS = {
    "medical": "医疗机构",
    "industrial": "工业制造",
    "retail": "零售门店",
    "education": "教育机构",
    "service": "服务行业",
}
SCENE_LABELS = {"on_site": "客户现场", "office": "办公室电脑", "mobile": "手机移动端"}
PRICING_MODE_LABELS = {
    "floor_price": "按底价卖不议价",
    "negotiable": "允许折让但超限需审批",
    "tiered": "按批发数量自动阶梯价",
    "bundle_fixed": "按套餐一口价",
}
OUTPUT_TARGET_LABELS = {
    "print_a4": "打印 A4 纸质",
    "pdf": "高品质 PDF",
    "screen": "屏幕演示",
}
ROLE_LABELS = {"admin": "老板", "sales": "销售", "manager": "主管"}


def _localize(code: Any, labels: Dict[str, str], default: str) -> str:
    """把枚举码翻译成人话；已经是人话（或未知码）时原样返回，不清空信息。"""
    if not code:
        return default
    return labels.get(str(code), str(code))


def generate_summary_text(data: Dict[str, Any], profile: Dict[str, Any] | None = None) -> str:
    """第 8 屏的一句话人话摘要（向导答案优先，画像兜底）。

    答案缺项时逐级回退到画像，保证只传画像（第 8 屏进页前）也能出通顺句子。
    """
    profile = profile or {}
    data = data or {}

    industry_code = profile.get("industry")
    customer_group = (
        data.get("industry")
        or profile.get("industry_label")
        or (_localize(industry_code, INDUSTRY_LABELS, "") if industry_code else "")
        or "客户"
    )
    category_name = data.get("category_name") or profile.get("category_name") or "主要商品"
    has_consumables = data.get("has_consumables", False)
    consumable_text = "、配套耗材" if has_consumables else ""

    roles = data.get("roles") or profile.get("roles") or []
    if isinstance(roles, str):
        roles_text = roles
    else:
        roles_text = "、".join(ROLE_LABELS.get(str(role), str(role)) for role in roles)
    roles_text = data.get("roles_text") or roles_text or "销售"

    scene_text = data.get("scene_label") or _localize(
        data.get("scene") or profile.get("scene"), SCENE_LABELS, "客户现场"
    )
    pricing_mode = data.get("pricing_label") or _localize(
        data.get("pricing_mode") or profile.get("pricing_mode"),
        PRICING_MODE_LABELS,
        "按底价卖不议价",
    )
    targets = profile.get("output_targets") or []
    output_target = data.get("output_target_label") or _localize(
        data.get("output_target") or (targets[0] if targets else None),
        OUTPUT_TARGET_LABELS,
        "打印 A4",
    )
    # 只有明确要求审批时才写"需要审批"；未知不等于需要。
    approval_text = "、破价需要审批" if data.get("require_approval") is True else ""
    brand_color = data.get("brand_color_name") or "你的品牌蓝"

    return (
        f"我理解你是：向{customer_group}销售{category_name}{consumable_text}，"
        f"{roles_text}在{scene_text}开单，{pricing_mode}{approval_text}，"
        f"报价单{output_target}给客户，主色用{brand_color}。"
    )


def resolve_skeleton(answers: Dict[str, Any], signals: Dict[str, Any]) -> str:
    """骨架映射（确定性、可测试；5 个骨架全部可达）。

    对应设计文档 §5.1 / §8 的映射表。
    """
    if answers.get("view_mode") == "management":
        return "dashboard-grid"
    scene = answers.get("scene", "on_site")
    if scene == "mobile":
        return "mobile-single-column"
    pricing = answers.get("pricing_mode", "floor_price")
    if answers.get("require_approval") or pricing in {"tiered", "bundle_fixed", "negotiable"}:
        return "form-first-wizard"
    if scene == "office":
        return "list-detail-split"
    return "catalog-left-form-right"


def resolve_modules(answers: Dict[str, Any], signals: Dict[str, Any]) -> List[str]:
    """模块开关（§5.3 全量规则，含 customers）。"""
    modules = ["quote_editor", "quotes", "settings"]
    if answers.get("sell_mode", "device_with_consumable") != "service":
        modules.insert(0, "catalog")
    if int(signals.get("sales_count") or 0) > 1 or "sales" in (answers.get("roles") or []):
        modules.append("employees")
    pricing_mode = answers.get("pricing_mode", "floor_price")
    if pricing_mode != "floor_price" or answers.get("require_approval"):
        modules.append("approval")
    if float(signals.get("customer_repeat_rate") or 0) > 1.5:
        modules.append("customers")
    # 去重保序
    deduped: List[str] = []
    for name in modules:
        if name not in deduped:
            deduped.append(name)
    return deduped


def compile_wizard_to_spec(
    answers: Dict[str, Any],
    signals: Dict[str, Any],
    source_level: str = "database",
    provider: Any = None,
    digest: Dict[str, Any] | None = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """把向导答案 + 画像编译成 UiSpec。

    provider 为 None 时全程走规则（离线可用）；传入时模型只增强画像与术语，
    且必须通过三道门，否则有界自愈后退回规则 Spec。
    """
    digest = digest or {}
    spec = get_fallback_spec()
    issues: List[str] = []

    # 1. 风格与品牌色
    spec["style"]["preset_id"] = answers.get("preset_id") or spec["style"]["preset_id"]
    if answers.get("density"):
        spec["style"]["density"] = answers["density"]
    if answers.get("brand_color"):
        spec["style"].setdefault("tokens", {})["color.primary"] = answers["brand_color"]

    # 2. 模块、骨架、屏幕与导航
    # 屏幕与导航由 modules 确定性派生：开了哪些模块，就有哪些可点到的屏幕，
    # 不再出现"声明的 nav 与 screens 对不上"的情况（见 navigation.py 的不变量）。
    spec["modules"] = resolve_modules(answers, signals)
    skeleton = resolve_skeleton(answers, signals)
    primary_screen = {**spec["screens"][0], "id": "quote_editor", "skeleton": skeleton}
    rebuild_navigation(spec, primary_screen=primary_screen)

    # 3. 画像（规则）与字段术语（规则）
    base_profile = rule_based_profile(digest) if digest else {}
    base_profile.update(
        {
            "industry": answers.get("industry_code") or base_profile.get("industry", "medical"),
            "sell_mode": answers.get("sell_mode", base_profile.get("sell_mode", "device_with_consumable")),
            "scene": answers.get("scene", base_profile.get("scene", "on_site")),
            "pricing_mode": answers.get("pricing_mode", base_profile.get("pricing_mode", "floor_price")),
        }
    )
    spec["profile"] = {**spec.get("profile", {}), **base_profile}

    rule_labels = localize_field_labels(
        price_term=digest.get("price_term", ""),
        promo=bool(digest.get("promo")),
    )
    existing_labels = {
        entity: dict(config.get("labels") or {})
        for entity, config in (spec.get("entities") or {}).items()
    }
    spec["entities"] = spec.get("entities") or {}
    for entity, labels in merge_labels(rule_labels, existing_labels).items():
        spec["entities"].setdefault(entity, {})["labels"] = labels

    # 4. 规则（报价单号 / 审批）
    spec.setdefault("rules", {})
    spec["rules"].setdefault("approval_required", bool(answers.get("require_approval")))
    spec["rules"].setdefault("price_floor_guard", True)

    # 5. 元数据
    spec["meta"] = {
        "generator": "designer-wizard-compiler",
        "source_level": source_level,
        "skeleton": skeleton,
    }

    # 6. 模型增强（可选，带三道门与有界自愈）
    if provider is not None:
        spec, llm_issues, attempts = enrich_spec_with_llm(spec, digest, provider)
        issues.extend(llm_issues)
        spec.setdefault("meta", {})["llm_attempts"] = attempts

    # 7. 最终仍要过一遍三道门，保证"永远输出合法 Spec"
    repaired, gate_issues = validate_and_repair_spec(spec)
    issues.extend(gate_issues)
    return repaired, issues
