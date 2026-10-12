"""测试 UiSpec 校验器与三道门守卫。

验证：
1. 第一道门（枚举门）：非法 skeleton/density/preset/block.type 被捕获并修复回退默认
2. 第二道门（字段门）：entities 中未在后端登记的字段被剔除，空列表回退默认字段
3. 第三道门（结构门）：block 与 skeleton 槽位/兼容矩阵校验，非法 block 剔除，缺失核心 block 自动补齐
4. 兜底保障：严重损坏的 spec 可一键回退到安全保底 spec
"""
import pytest

from app.designer.schema import (
    ALLOWED_SKELETONS,
    ALLOWED_DENSITIES,
    ALLOWED_PRESETS,
    ALLOWED_BLOCKS,
    ALLOWED_MODULES,
    SKELETON_BLOCK_MATRIX,
    get_db_fields_registry,
    get_fallback_spec,
)
from app.designer.validator import validate_and_repair_spec


def test_schema_constants():
    assert "catalog-left-form-right" in ALLOWED_SKELETONS
    assert "comfortable" in ALLOWED_DENSITIES
    assert "medical-clean" in ALLOWED_PRESETS
    assert "customer_info" in ALLOWED_BLOCKS
    assert "quote_editor" in ALLOWED_MODULES
    assert len(ALLOWED_BLOCKS) == 16
    assert len(ALLOWED_SKELETONS) == 5


def test_db_fields_registry():
    registry = get_db_fields_registry()
    assert "product" in registry
    assert "sku_id" in registry["product"]
    assert "name" in registry["product"]
    assert "min_price" in registry["product"]


def test_gate1_enum_repair():
    bad_spec = {
        "spec_version": 1,
        "style": {
            "preset_id": "invalid-preset-xyz",
            "density": "super-compact",
        },
        "modules": ["quote_editor", "unknown_module"],
        "screens": [
            {
                "id": "quote_editor",
                "skeleton": "nonexistent-skeleton",
                "blocks": [{"type": "customer_info", "props": {}}],
            }
        ],
    }

    repaired, issues = validate_and_repair_spec(bad_spec)
    assert repaired["style"]["preset_id"] == "medical-clean"
    assert repaired["style"]["density"] == "comfortable"
    assert "unknown_module" not in repaired["modules"]
    assert repaired["screens"][0]["skeleton"] == "catalog-left-form-right"
    assert any("枚举门" in i or "Enum" in i for i in issues)


def test_gate2_field_repair():
    registry = {"product": ["sku_id", "name", "min_price"]}
    spec = {
        "spec_version": 1,
        "style": {"preset_id": "medical-clean", "density": "comfortable"},
        "modules": ["quote_editor"],
        "screens": [
            {
                "id": "quote_editor",
                "skeleton": "catalog-left-form-right",
                "blocks": [{"type": "item_picker", "props": {}}],
            }
        ],
        "entities": {
            "product": {
                "list_columns": ["sku_id", "illegal_hacked_field", "name"],
                "fields": ["unknown_field_123"],
            }
        },
    }

    repaired, issues = validate_and_repair_spec(spec, db_fields_registry=registry)
    assert "illegal_hacked_field" not in repaired["entities"]["product"]["list_columns"]
    assert repaired["entities"]["product"]["list_columns"] == ["sku_id", "name"]
    # unknown_field_123 剔除后为空，回退到默认字段
    assert len(repaired["entities"]["product"]["fields"]) > 0
    assert any("字段门" in i or "Field" in i for i in issues)


def test_gate3_structure_matrix_repair():
    # stats_cards 只允许在 ④ dashboard-grid，不能出现在 ① catalog-left-form-right
    spec = {
        "spec_version": 1,
        "style": {"preset_id": "medical-clean", "density": "comfortable"},
        "modules": ["quote_editor"],
        "screens": [
            {
                "id": "quote_editor",
                "skeleton": "catalog-left-form-right",
                "blocks": [
                    {"type": "stats_cards", "props": {}},  # 不允许在此骨架
                    {"type": "customer_info", "props": {}},
                ],
            }
        ],
    }

    repaired, issues = validate_and_repair_spec(spec)
    block_types = [b["type"] for b in repaired["screens"][0]["blocks"]]
    assert "stats_cards" not in block_types
    assert "customer_info" in block_types
    assert any("结构门" in i or "Structure" in i for i in issues)


def test_fallback_spec_validity():
    fallback = get_fallback_spec()
    repaired, issues = validate_and_repair_spec(fallback)
    assert len(issues) == 0
    assert repaired["spec_version"] == 1
    assert "quote_editor" in repaired["modules"]
