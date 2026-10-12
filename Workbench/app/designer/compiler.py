"""向导答案编译器与人话摘要生成模块。

将向导问卷答案 + 画像 Signals 确定性编译为正式 UiSpec，
并通过三道门校验输出规范草稿。
"""
from typing import Any, Dict, List, Tuple

from app.designer.schema import get_fallback_spec
from app.designer.validator import validate_and_repair_spec


def generate_summary_text(data: Dict[str, Any]) -> str:
    """根据向导答案生成第 8 屏的一句话人话理解摘要。

    模板：
    我理解你是：向{客户群}销售{主营品类}{，配套耗材}，{销售角色}在{场景}开单，
    {定价方式}{，破价需要审批}，报价单{输出方式}给客户，主色用{品牌色}。
    """
    customer_group = data.get("industry") or "客户"
    category_name = data.get("category_name") or "主要商品"
    has_consumables = data.get("has_consumables", False)
    consumable_text = "、配套耗材" if has_consumables else ""
    roles_text = data.get("roles") or "销售"
    scene_text = data.get("scene") or "客户现场"
    pricing_mode = data.get("pricing_mode") or "按底价卖不议价"
    approval_text = "、破价需要审批" if data.get("require_approval", True) else ""
    output_target = data.get("output_target") or "打印 A4"
    brand_color = data.get("brand_color_name") or "你的品牌蓝"

    return (
        f"我理解你是：向{customer_group}销售{category_name}{consumable_text}，"
        f"{roles_text}在{scene_text}开单，{pricing_mode}{approval_text}，"
        f"报价单{output_target}给客户，主色用{brand_color}。"
    )


def compile_wizard_to_spec(
    answers: Dict[str, Any],
    signals: Dict[str, Any],
    source_level: str = "database",
) -> Tuple[Dict[str, Any], List[str]]:
    """将向导答案与画像指标编译为 UiSpec 并经三道门校验返回。"""
    spec = get_fallback_spec()

    # 1. 样式与颜色
    preset_id = answers.get("preset_id") or "medical-clean"
    spec["style"]["preset_id"] = preset_id
    if answers.get("density"):
        spec["style"]["density"] = answers["density"]

    primary_color = answers.get("brand_color")
    if primary_color:
        spec["style"]["tokens"]["color.primary"] = primary_color

    # 2. 模块控制 (§5.3)
    modules = ["quote_editor", "quotes", "settings"]
    sell_mode = answers.get("sell_mode", "device_with_consumable")
    if sell_mode != "service":
        modules.insert(0, "catalog")

    sales_count = signals.get("sales_count", 0)
    if sales_count > 1 or "sales" in answers.get("roles", []):
        modules.append("employees")

    pricing_mode = answers.get("pricing_mode", "floor_price")
    if pricing_mode != "floor_price" or answers.get("require_approval"):
        modules.append("approval")

    spec["modules"] = modules

    # 3. 屏幕与骨架映射
    scene = answers.get("scene", "on_site")
    if scene == "mobile":
        skeleton = "mobile-single-column"
    elif scene == "office":
        skeleton = "list-detail-split"
    else:
        skeleton = "catalog-left-form-right"

    spec["screens"][0]["skeleton"] = skeleton

    # 4. 元数据
    spec["meta"] = {
        "generator": "designer-wizard-compiler",
        "source_level": source_level,
    }

    # 5. 走三道门防御校验
    repaired_spec, issues = validate_and_repair_spec(spec)
    return repaired_spec, issues
