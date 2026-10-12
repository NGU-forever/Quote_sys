"""测试预设包构建 (presets.py) 与向导编译器 (compiler.py)。"""
import pytest

from app.designer.presets import get_preset_meta, build_preview_spec_draft
from app.designer.compiler import compile_wizard_to_spec, generate_summary_text


def test_presets_meta_and_definitions():
    meta = get_preset_meta()
    assert "order-entry" in meta
    assert "wholesale" in meta
    assert "management" in meta

    assert meta["order-entry"]["skeleton"] == "catalog-left-form-right"
    assert meta["wholesale"]["skeleton"] == "list-detail-split"
    assert meta["management"]["skeleton"] == "dashboard-grid"


def test_build_preview_spec_draft():
    draft = build_preview_spec_draft("order-entry", source_level="sample")
    assert draft["spec_version"] == 1
    assert draft["style"]["preset_id"] == "medical-clean"
    assert draft["style"]["density"] == "comfortable"
    assert draft["screens"][0]["skeleton"] == "catalog-left-form-right"


def test_compile_wizard_to_spec():
    answers = {
        "sell_mode": "consumable_only",
        "roles": ["admin", "sales"],
        "scene": "office",
        "pricing_mode": "negotiable",
        "output_targets": ["print_a4"],
        "brand_color": "#175C8C",
        "preset_id": "industrial-dense",
    }
    signals = {"sales_count": 2, "consumable_ratio": 0.8}

    spec, issues = compile_wizard_to_spec(answers, signals, source_level="database")
    assert spec["style"]["preset_id"] == "industrial-dense"
    assert spec["style"]["tokens"]["color.primary"] == "#175C8C"
    # 当有多个销售时，自动开启 employees 模块
    assert "employees" in spec["modules"]
    assert "quote_editor" in spec["modules"]


def test_generate_summary_text():
    answers = {
        "industry": "医疗",
        "category_name": "超声设备",
        "has_consumables": True,
        "scene": "客户现场",
        "roles": "销售",
        "pricing_mode": "按底价卖不议价",
        "require_approval": True,
        "output_target": "打印 A4",
        "brand_color_name": "品牌蓝",
    }
    summary = generate_summary_text(answers)
    assert "客户现场" in summary
    assert "按底价卖不议价" in summary
    assert "打印 A4" in summary
