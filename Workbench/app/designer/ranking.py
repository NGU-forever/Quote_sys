"""预设排序与数据来源等级推断模块。

根据 §7.2 与 §7.3 规则进行确定性状态推导：
- 数据来源分级：database / assets / sample
- 命中即停的三张预览排序：order-entry / wholesale / management
"""
from typing import Any, Dict, List


def determine_source_level(signals: Dict[str, Any]) -> str:
    """根据指标判断当前数据来源级别（三级优先）。

    - database: 库里已有商品且已有真实单据
    - assets: 库里有商品（可能来自资料解析上传）但尚无正式业务单据
    - sample: 空库或商品为 0，走行业样例演示
    """
    product_count = signals.get("product_count", 0)
    quote_count = signals.get("quote_count", 0)

    if product_count > 0 and quote_count > 0:
        return "database"
    if product_count > 0:
        return "assets"
    return "sample"


def rank_preview_presets(
    signals: Dict[str, Any], user_preference: str | None = None
) -> List[str]:
    """根据命中即停规则计算三套预设的排序。

    预设定义：
    - order-entry (① 开单型: catalog-left-form-right, comfortable, medical-clean)
    - wholesale   (② 批发型: list-detail-split, compact, industrial-dense)
    - management  (③ 管理型: dashboard-grid, spacious, brand-premium)
    """
    quote_count = signals.get("quote_count", 0)
    sales_count = signals.get("sales_count", 0)
    product_count = signals.get("product_count", 0)
    consumable_ratio = signals.get("consumable_ratio", 0.0)
    binding_density = signals.get("binding_density", 0.0)

    # 条件 1: quote_count > 200 且 sales_count > 1，或选了管理视角 -> ③ -> ① -> ②
    if (quote_count > 200 and sales_count > 1) or user_preference == "management":
        return ["management", "order-entry", "wholesale"]

    # 条件 2: product_count > 200 或 consumable_ratio > 0.6 -> ② -> ① -> ③
    if product_count > 200 or consumable_ratio > 0.6 or user_preference == "wholesale":
        return ["wholesale", "order-entry", "management"]

    # 条件 3: binding_density > 0.8，或选了现场开单 -> ① -> ② -> ③
    if binding_density > 0.8 or user_preference == "order_entry":
        return ["order-entry", "wholesale", "management"]

    # 条件 4: 空库 / 兜底 -> ① -> ② -> ③
    return ["order-entry", "wholesale", "management"]
