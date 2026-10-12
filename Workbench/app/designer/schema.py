"""UiSpec 数据规范定义与白名单常量。

定义了：
- 5 个骨架 (Skeletons)
- 3 种密度 (Densities)
- 3 套风格预设 (Presets)
- 7 种模块 (Modules)
- 16 种标准化 Block 与骨架支持矩阵
- 后端字段注册表反射
- 规则保底 Spec
"""
from typing import Any, Dict, List, Set

from app.models.package import Package
from app.models.product import Product
from app.models.quote import Quote
from app.models.user import User

ALLOWED_SKELETONS: Set[str] = {
    "catalog-left-form-right",
    "form-first-wizard",
    "list-detail-split",
    "dashboard-grid",
    "mobile-single-column",
}

DEFAULT_SKELETON = "catalog-left-form-right"

ALLOWED_DENSITIES: Set[str] = {
    "comfortable",
    "compact",
    "spacious",
}

DEFAULT_DENSITY = "comfortable"

ALLOWED_PRESETS: Set[str] = {
    "medical-clean",
    "industrial-dense",
    "brand-premium",
}

DEFAULT_PRESET = "medical-clean"

ALLOWED_MODULES: Set[str] = {
    "catalog",
    "quote_editor",
    "quotes",
    "employees",
    "settings",
    "approval",
    "customers",
}

# 16 种 Block 白名单以及对应的骨架兼容性矩阵
# 骨架代号映射：
# 1: catalog-left-form-right
# 2: form-first-wizard
# 3: list-detail-split
# 4: dashboard-grid
# 5: mobile-single-column
SKELETON_BLOCK_MATRIX: Dict[str, Set[str]] = {
    "catalog-left-form-right": {
        "customer_info",
        "item_picker",
        "item_table_editable",
        "price_summary",
        "floor_price_alert",
        "bundle_suggestion",
        "quote_meta",
        "export_actions",
    },
    "form-first-wizard": {
        "customer_info",
        "item_picker",
        "item_table_editable",
        "price_summary",
        "floor_price_alert",
        "bundle_suggestion",
        "discount_panel",
        "notes_and_terms",
        "attachment_upload",
        "approval_status",
        "export_actions",
    },
    "list-detail-split": {
        "customer_info",
        "item_table_readonly",
        "price_summary",
        "discount_panel",
        "quote_meta",
        "notes_and_terms",
        "attachment_upload",
        "approval_status",
        "activity_timeline",
        "export_actions",
    },
    "dashboard-grid": {
        "approval_status",
        "activity_timeline",
        "stats_cards",
        "recent_quotes",
    },
    "mobile-single-column": {
        "customer_info",
        "item_picker",
        "item_table_editable",
        "price_summary",
        "floor_price_alert",
    },
}

ALLOWED_BLOCKS: Set[str] = {
    block for blocks in SKELETON_BLOCK_MATRIX.values() for block in blocks
}


def get_db_fields_registry() -> Dict[str, List[str]]:
    """从已定义的 ORM 模型推导字段白名单注册表。"""
    def _model_columns(model) -> List[str]:
        return [c.name for c in model.__table__.columns]

    return {
        "product": _model_columns(Product),
        "package": _model_columns(Package),
        "quote": _model_columns(Quote),
        "user": _model_columns(User),
    }


def get_fallback_spec() -> Dict[str, Any]:
    """返回保底规则 UiSpec（永远合法、永远可用）。"""
    return {
        "spec_version": 1,
        "meta": {
            "generator": "fallback-rule-engine",
            "source_level": "sample",
        },
        "profile": {
            "industry": "medical",
            "sell_mode": "device_with_consumable",
            "scene": "on_site",
            "roles": ["admin", "sales"],
            "pricing_mode": "floor_price",
            "output_targets": ["print_a4"],
        },
        "style": {
            "preset_id": "medical-clean",
            "density": "comfortable",
            "tokens": {"color.primary": "#0B5FA5"},
        },
        "modules": ["catalog", "quote_editor", "quotes", "settings"],
        "nav": [
            {"id": "quote_editor", "label": "开单", "route": "/quote/new", "icon": "edit"},
            {"id": "quotes", "label": "报价单", "route": "/quotes", "icon": "file"},
            {"id": "catalog", "label": "商品管理", "route": "/catalog", "icon": "box"},
            {"id": "settings", "label": "系统设置", "route": "/settings", "icon": "settings"},
        ],
        "screens": [
            {
                "id": "quote_editor",
                "skeleton": "catalog-left-form-right",
                "blocks": [
                    {"type": "customer_info", "props": {"fields": ["customer_name", "customer_phone"]}},
                    {"type": "item_picker", "props": {"filters": ["category"], "show_floor_price": False}},
                    {"type": "item_table_editable", "props": {"columns": ["name", "unit_price", "qty", "subtotal", "floor_check"]}},
                    {"type": "floor_price_alert", "props": {"blocking": True, "require_approval": True}},
                    {"type": "price_summary", "props": {"show_tax": False}},
                    {"type": "export_actions", "props": {"actions": ["save_draft", "print_a4"]}},
                ],
            }
        ],
        "entities": {
            "product": {
                "list_columns": ["sku_id", "name", "category", "min_price", "unit"],
                "filters": ["category", "name"],
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
        "rules": {
            "price_floor_guard": True,
            "bundle_validation": True,
            "quote_no_pattern": "QT-{YYYYMMDD}-{0001}",
        },
    }
