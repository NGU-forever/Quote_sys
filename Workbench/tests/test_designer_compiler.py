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


def test_generate_summary_text_localizes_enum_codes():
    """向导传的是枚举码，摘要必须是中文人话（回归：曾直出现 on_site/print_a4）。"""
    answers = {
        "industry": "医疗设备",
        "category_name": "主要设备与配件",
        "has_consumables": True,
        "roles": ["admin", "sales"],
        "scene": "on_site",
        "pricing_mode": "floor_price",
        "require_approval": False,
        "output_target": "print_a4",
        "brand_color_name": "品牌科技蓝",
    }
    summary = generate_summary_text(answers)
    assert "老板、销售" in summary
    assert "客户现场" in summary
    assert "按底价卖不议价" in summary
    assert "打印 A4" in summary
    assert "破价需要审批" not in summary
    for code in ("on_site", "floor_price", "print_a4", "admin", "sales"):
        assert code not in summary


def test_generate_summary_text_falls_back_to_profile():
    """只给画像（无向导答案）也要出通顺句子，而不是落到默认值。"""
    profile = {
        "industry": "industrial",
        "sell_mode": "consumable_only",
        "scene": "office",
        "pricing_mode": "tiered",
        "roles": ["admin", "sales"],
        "output_targets": ["pdf"],
        "category_name": "耗材配件",
    }
    summary = generate_summary_text({}, profile)
    assert "工业制造" in summary
    assert "耗材配件" in summary
    assert "办公室电脑" in summary
    assert "按批发数量自动阶梯价" in summary
    assert "高品质 PDF" in summary
    assert "industrial" not in summary
    assert "tiered" not in summary


def test_generate_summary_text_does_not_assume_approval():
    """require_approval 缺省时不得凭空写"需要审批"。"""
    assert "破价需要审批" not in generate_summary_text({})
    assert "破价需要审批" in generate_summary_text({"require_approval": True})

