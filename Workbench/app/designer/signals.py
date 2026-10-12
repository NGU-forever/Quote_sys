"""画像层指标计算模块。

通过纯 SQL 聚合直接查询数据库，无大模型参与，计算时延 <200ms。
输出的指标同时服务于第 0 屏预设排序与第 8 屏人话摘要。
"""
from typing import Any, Dict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.models.device_binding import DeviceBinding
from app.models.package import Package
from app.models.product import Product
from app.models.quote import Quote
from app.models.user import User


def compute_signals(db: Session) -> Dict[str, Any]:
    """通过纯 SQL 快速聚合画像指标。"""
    # 1. 商品与品类聚合
    total_products = db.scalar(select(func.count(Product.id))) or 0
    consumable_count = (
        db.scalar(
            select(func.count(Product.id)).where(Product.category == "consumable")
        )
        or 0
    )
    device_count = total_products - consumable_count
    consumable_ratio = (
        float(consumable_count) / float(total_products) if total_products > 0 else 0.0
    )

    # 2. 绑定聚合
    binding_count = (
        db.scalar(select(func.count(DeviceBinding.device_sku_id))) or 0
    )
    binding_density = (
        float(binding_count) / float(max(device_count, 1))
        if device_count > 0
        else 0.0
    )

    # 3. 套餐聚合
    package_count = db.scalar(select(func.count(Package.id))) or 0

    # 4. 单据与业务量聚合
    quote_count = db.scalar(select(func.count(Quote.id))) or 0
    distinct_customers = (
        db.scalar(select(func.count(func.distinct(Quote.customer_name)))) or 0
    )
    customer_repeat_rate = (
        float(distinct_customers) / float(quote_count) if quote_count > 0 else 1.0
    )

    # 5. 销售角色聚合
    sales_count = (
        db.scalar(select(func.count(User.id)).where(User.role == "sales")) or 0
    )

    # 6. 议价与包装特征
    raw_desc_count = (
        db.scalar(
            select(func.count(Product.id)).where(Product.raw_price_desc.isnot(None))
        )
        or 0
    )
    raw_desc_ratio = (
        float(raw_desc_count) / float(total_products) if total_products > 0 else 0.0
    )

    box_feature_count = (
        db.scalar(
            select(func.count(Product.id)).where(
                (Product.box_price.isnot(None)) | (Product.pieces_per_unit.isnot(None))
            )
        )
        or 0
    )
    box_feature_ratio = (
        float(box_feature_count) / float(total_products) if total_products > 0 else 0.0
    )

    has_negotiable = bool(
        db.scalar(
            select(func.count(Product.id)).where(Product.max_price.isnot(None))
        )
        or 0
    )

    # 7. 品牌与设置
    brand_setting = db.get(AppSetting, "company_brand")
    has_logo = False
    brand_color = None
    if brand_setting and brand_setting.value:
        has_logo = "logo" in brand_setting.value
        if "color" in brand_setting.value:
            brand_color = "#0B5FA5"

    return {
        "product_count": total_products,
        "consumable_count": consumable_count,
        "device_count": device_count,
        "consumable_ratio": consumable_ratio,
        "binding_count": binding_count,
        "binding_density": binding_density,
        "package_count": package_count,
        "quote_count": quote_count,
        "distinct_customers": distinct_customers,
        "customer_repeat_rate": customer_repeat_rate,
        "sales_count": sales_count,
        "raw_desc_ratio": raw_desc_ratio,
        "box_feature_ratio": box_feature_ratio,
        "has_negotiable": has_negotiable,
        "has_logo": has_logo,
        "brand_color": brand_color,
    }
