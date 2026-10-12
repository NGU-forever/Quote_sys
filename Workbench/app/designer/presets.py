"""三套预设答案包与预览 Spec 生成模块。

定义：
1. order-entry (① 开单型): catalog-left-form-right / comfortable / medical-clean
2. wholesale   (② 批发型): list-detail-split / compact / industrial-dense
3. management  (③ 管理型): dashboard-grid / spacious / brand-premium
"""
from typing import Any, Dict


PRESET_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "order-entry": {
        "id": "order-entry",
        "name": "开单型",
        "skeleton": "catalog-left-form-right",
        "density": "comfortable",
        "preset_id": "medical-clean",
        "primary_color": "#0B5FA5",
        "pitch": "适合在客户现场开单：左边挑货，右边出单",
        "preset_answers": {
            "sell_mode": "device_with_consumable",
            "scene": "on_site",
            "pricing_mode": "floor_price",
            "preset_id": "medical-clean",
        },
        "screens": [
            {
                "id": "quote_editor",
                "skeleton": "catalog-left-form-right",
                "blocks": [
                    {"type": "customer_info", "props": {"fields": ["customer_name", "customer_phone"]}},
                    {"type": "item_picker", "props": {"filters": ["category"], "show_floor_price": False}},
                    {"type": "item_table_editable", "props": {"columns": ["name", "unit_price", "qty", "subtotal", "floor_check"]}},
                    {"type": "bundle_suggestion", "props": {"max_items": 2, "show_saving": True}},
                    {"type": "floor_price_alert", "props": {"blocking": True, "require_approval": True}},
                    {"type": "price_summary", "props": {"show_tax": False}},
                    {"type": "export_actions", "props": {"actions": ["save_draft", "print_a4"]}},
                ],
            }
        ],
    },
    "wholesale": {
        "id": "wholesale",
        "name": "批发型",
        "skeleton": "list-detail-split",
        "density": "compact",
        "preset_id": "industrial-dense",
        "primary_color": "#175C8C",
        "pitch": "一屏看 20 个商品：适合商品多、走量",
        "preset_answers": {
            "sell_mode": "consumable_only",
            "scene": "office",
            "pricing_mode": "tiered",
            "preset_id": "industrial-dense",
        },
        "screens": [
            {
                "id": "quote_editor",
                "skeleton": "list-detail-split",
                "blocks": [
                    {"type": "customer_info", "props": {"fields": ["customer_name"]}},
                    {"type": "item_table_readonly", "props": {"columns": ["sku_id", "name", "category", "unit_price"]}},
                    {"type": "discount_panel", "props": {"max_discount": 0.2}},
                    {"type": "price_summary", "props": {"show_tax": True}},
                    {"type": "export_actions", "props": {"actions": ["save_draft", "print_a4"]}},
                ],
            }
        ],
    },
    "management": {
        "id": "management",
        "name": "管理型",
        "skeleton": "dashboard-grid",
        "density": "spacious",
        "preset_id": "brand-premium",
        "primary_color": "#14532D",
        "pitch": "先看今天卖了多少，再点进去看单据",
        "preset_answers": {
            "sell_mode": "mixed",
            "scene": "office",
            "pricing_mode": "negotiable",
            "preset_id": "brand-premium",
        },
        "screens": [
            {
                "id": "quote_editor",
                "skeleton": "dashboard-grid",
                "blocks": [
                    {"type": "stats_cards", "props": {"metrics": ["today_sales", "pending_approvals"]}},
                    {"type": "recent_quotes", "props": {"max_items": 10}},
                    {"type": "approval_status", "props": {"show_history": True}},
                ],
            }
        ],
    },
}


def get_preset_meta() -> Dict[str, Dict[str, Any]]:
    """返回三套预设的展示元数据。"""
    return {
        k: {
            "id": v["id"],
            "name": v["name"],
            "skeleton": v["skeleton"],
            "density": v["density"],
            "preset_id": v["preset_id"],
            "pitch": v["pitch"],
            "primary_color": v["primary_color"],
            "preset_answers": v["preset_answers"],
        }
        for k, v in PRESET_DEFINITIONS.items()
    }


def build_preview_spec_draft(
    preset_id: str, source_level: str = "sample"
) -> Dict[str, Any]:
    """为第 0 屏可点原型构建完整的预览 UiSpec 草稿。"""
    cfg = PRESET_DEFINITIONS.get(preset_id, PRESET_DEFINITIONS["order-entry"])
    return {
        "spec_version": 1,
        "meta": {
            "generator": f"preview-preset-{preset_id}",
            "source_level": source_level,
        },
        "profile": {
            "industry": "medical",
            "sell_mode": cfg["preset_answers"].get("sell_mode", "device_with_consumable"),
            "scene": cfg["preset_answers"].get("scene", "on_site"),
            "pricing_mode": cfg["preset_answers"].get("pricing_mode", "floor_price"),
        },
        "style": {
            "preset_id": cfg["preset_id"],
            "density": cfg["density"],
            "tokens": {"color.primary": cfg["primary_color"]},
        },
        "modules": ["catalog", "quote_editor", "quotes", "settings"],
        "screens": cfg["screens"],
        "entities": {
            "product": {
                "list_columns": ["sku_id", "name", "category", "min_price", "unit"],
                "fields": ["sku_id", "category", "name", "unit", "min_price"],
            }
        },
        "output": {
            "quote_pdf": {
                "paper": "A4",
                "header_style": "logo_left_company_right",
                "table_style": "bordered",
                "show_floor_price": False,
            }
        },
    }
