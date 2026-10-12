"""真实数据采样选择器与三级来源降级处理。

根据 §7.4 与 §7.5：
- 商品列表：包含 1 有图 + 1 最长名 + 1 最高价 + 1 最低价，稳定排序列 6-8 条
- 套餐卡片：选择差额最大（省额最多）的套餐
- 报价单：真实单据或显式标注的样例单据
- 底价演示：同时演示 1 条 ✓ 与 1 条 ⚠
- 优雅降级：无图生成首字色彩占位、无价格显示“面议”
"""
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.package import Package
from app.models.product import Product
from app.models.quote import Quote
from app.models.user import User


# 内置行业演示样例数据包（第 ③ 级兜底）
SAMPLE_PACK_PRODUCTS = [
    {
        "sku_id": "SMP-001",
        "name": "超声波数字化彩色成像诊断系统",
        "category": "device",
        "unit": "台",
        "min_price": 68000.0,
        "max_price": 85000.0,
        "image": "/uploads/products/sample_ultrasound.png",
        "has_image": True,
    },
    {
        "sku_id": "SMP-002",
        "name": "医用高频电刀多功能手术切割主机配备双脚踏开关控制器",
        "category": "device",
        "unit": "套",
        "min_price": 42000.0,
        "max_price": 50000.0,
        "image": None,
        "has_image": False,
    },
    {
        "sku_id": "SMP-003",
        "name": "便携式心电监护仪(八导联)",
        "category": "device",
        "unit": "台",
        "min_price": 12800.0,
        "max_price": 16000.0,
        "image": None,
        "has_image": False,
    },
    {
        "sku_id": "SMP-004",
        "name": "一次性医用高分子导丝耗材",
        "category": "consumable",
        "unit": "根",
        "min_price": 25.0,
        "max_price": 45.0,
        "image": None,
        "has_image": False,
    },
    {
        "sku_id": "SMP-005",
        "name": "灭菌医用电极导片(10片装)",
        "category": "consumable",
        "unit": "包",
        "min_price": 18.0,
        "max_price": 30.0,
        "image": None,
        "has_image": False,
    },
    {
        "sku_id": "SMP-006",
        "name": "高压连接输液管",
        "category": "consumable",
        "unit": "条",
        "min_price": 8.5,
        "max_price": 15.0,
        "image": None,
        "has_image": False,
    },
]

SAMPLE_FEATURED_PACKAGE = {
    "package_id": "SMP-PKG-01",
    "name": "超声开业全套配置套餐",
    "std_price": 82000.0,
    "discount_price": 76800.0,
    "saving_amount": 5200.0,
    "note": "主机配探头与 50 包耗材",
}

SAMPLE_RECENT_QUOTE = {
    "quote_no": "QT-DEMO-20261012-001",
    "customer_name": "华东中心医院",
    "sales_name": "王销售",
    "total_list_price": 86800.0,
    "final_quote_price": 79800.0,
    "is_sample": True,
}


def _format_product(p: Product) -> Dict[str, Any]:
    return {
        "sku_id": p.sku_id,
        "name": p.name,
        "category": p.category,
        "unit": p.unit or "件",
        "min_price": p.min_price,
        "price_display": f"¥{p.min_price:,.2f}" if p.min_price is not None else "面议",
        "max_price": p.max_price,
        "image": p.image,
        "has_image": bool(p.image),
        "spec": p.spec or "",
    }


def sample_preview_data(
    db: Session,
    source_level: str = "sample",
) -> Dict[str, Any]:
    """采样并构造用于第 0 屏可点原型与实时计算的真实业务数据片段。"""
    if source_level == "sample":
        return {
            "source_level": "sample",
            "source_label": "以下用行业样例演示，导入数据后会替换",
            "products": SAMPLE_PACK_PRODUCTS,
            "featured_package": SAMPLE_FEATURED_PACKAGE,
            "recent_quote": SAMPLE_RECENT_QUOTE,
            "demo_items": [
                {
                    "sku_id": "SMP-001",
                    "name": "超声波数字化彩色成像诊断系统",
                    "unit_price": 75000.0,
                    "floor_price": 68000.0,
                    "qty": 1,
                    "floor_status": "ok",  # ✓ 高于底价
                },
                {
                    "sku_id": "SMP-004",
                    "name": "一次性医用高分子导丝耗材",
                    "unit_price": 20.0,
                    "floor_price": 25.0,
                    "qty": 100,
                    "floor_status": "warn",  # ⚠ 破底价报警
                },
            ],
        }

    # 真实数据库采样
    all_products = db.scalars(select(Product).order_by(Product.id.asc())).all()
    if not all_products:
        return sample_preview_data(db, source_level="sample")

    # 1. 挑选商品 (目标 6-8 条)
    # 有图 1 条
    p_img = next((p for p in all_products if p.image), None)
    # 最长名称 1 条
    p_long = max(all_products, key=lambda p: len(p.name or ""))
    # 价格最高与最低
    priced_products = [p for p in all_products if p.min_price is not None]
    p_high = max(priced_products, key=lambda p: p.min_price) if priced_products else None
    p_low = min(priced_products, key=lambda p: p.min_price) if priced_products else None

    chosen_set = set()
    chosen_products: List[Product] = []

    def _add(p: Optional[Product]):
        if p and p.sku_id not in chosen_set:
            chosen_set.add(p.sku_id)
            chosen_products.append(p)

    _add(p_img)
    _add(p_long)
    _add(p_high)
    _add(p_low)

    # 补齐至 6-8 条
    for p in all_products:
        if len(chosen_products) >= 8:
            break
        _add(p)

    formatted_products = [_format_product(p) for p in chosen_products]

    # 2. 套餐卡片：选择省额最大的套餐
    all_packages = db.scalars(select(Package).order_by(Package.id.asc())).all()
    featured_package = None
    best_saving = -1.0
    for pkg in all_packages:
        if pkg.std_price is not None and pkg.discount_price is not None:
            saving = pkg.std_price - pkg.discount_price
            if saving > best_saving:
                best_saving = saving
                featured_package = {
                    "package_id": pkg.package_id,
                    "name": pkg.name,
                    "std_price": pkg.std_price,
                    "discount_price": pkg.discount_price,
                    "saving_amount": saving,
                    "note": pkg.note or "",
                }

    # 3. 最近报价单
    last_quote = db.scalar(select(Quote).order_by(Quote.id.desc()).limit(1))
    if last_quote:
        recent_quote = {
            "quote_no": last_quote.quote_no,
            "customer_name": last_quote.customer_name,
            "sales_name": last_quote.sales_name or "主账号销售",
            "total_list_price": last_quote.total_list_price,
            "final_quote_price": last_quote.final_quote_price,
            "is_sample": False,
        }
    else:
        recent_quote = SAMPLE_RECENT_QUOTE

    # 4. 底价校验演示数据 (必须包含 1 条 ok 和 1 条 warn)
    demo_items = []
    if len(formatted_products) >= 2:
        prod_ok = formatted_products[0]
        floor1 = prod_ok["min_price"] or 100.0
        demo_items.append({
            "sku_id": prod_ok["sku_id"],
            "name": prod_ok["name"],
            "unit_price": floor1 * 1.15,
            "floor_price": floor1,
            "qty": 1,
            "floor_status": "ok",
        })

        prod_warn = formatted_products[1]
        floor2 = prod_warn["min_price"] or 200.0
        demo_items.append({
            "sku_id": prod_warn["sku_id"],
            "name": prod_warn["name"],
            "unit_price": max(floor2 * 0.85, 1.0),
            "floor_price": floor2,
            "qty": 2,
            "floor_status": "warn",
        })
    else:
        demo_items = [
            {"sku_id": "P-DEMO-1", "name": "演示品A", "unit_price": 100.0, "floor_price": 90.0, "qty": 1, "floor_status": "ok"},
            {"sku_id": "P-DEMO-2", "name": "演示品B", "unit_price": 80.0, "floor_price": 95.0, "qty": 1, "floor_status": "warn"},
        ]

    label = (
        "以下是你库里的真实数据"
        if source_level == "database"
        else "以下用你上传的资料解析渲染"
    )

    return {
        "source_level": source_level,
        "source_label": label,
        "products": formatted_products,
        "featured_package": featured_package,
        "recent_quote": recent_quote,
        "demo_items": demo_items,
    }
