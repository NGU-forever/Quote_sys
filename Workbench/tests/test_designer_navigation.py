"""M5 测试：模块 → 屏幕 → 导航的确定性映射与导航门。

关键不变量（此前 nav 完全没有校验、运行时也从不消费）：
- nav[].id 与 screens[].id 一一对应：不存在点不动的死链，也不存在点不到的屏幕
- 只有启用了的模块才产出屏幕与导航项
- 每个模块蓝图的骨架 + 区块必须落在 SKELETON_BLOCK_MATRIX 兼容白名单内
"""
from app.designer.compiler import compile_wizard_to_spec, resolve_modules
from app.designer.navigation import build_module_screens, build_nav, rebuild_navigation
from app.designer.presets import build_preview_spec_draft
from app.designer.schema import (
    MODULE_NAV,
    MODULE_SCREEN_BLUEPRINTS,
    SKELETON_BLOCK_MATRIX,
    get_fallback_spec,
)
from app.designer.validator import validate_and_repair_spec


def _ids(items):
    return [item["id"] for item in items]


# --------------------------------------------------------------------------
# 映射本身
# --------------------------------------------------------------------------


def test_module_screens_keeps_editor_first_and_uses_registry_order():
    primary = {"id": "quote_editor", "skeleton": "form-first-wizard", "blocks": []}
    modules = ["customers", "catalog", "quote_editor", "quotes", "approval"]
    screens = build_module_screens(modules, primary_screen=primary)

    assert screens[0] is primary
    # 顺序由 MODULE_NAV 登记顺序决定，不随传入的 modules 顺序漂移
    assert _ids(screens) == ["quote_editor", "quotes", "approval", "catalog", "customers"]


def test_modules_without_blueprint_produce_no_screen():
    screens = build_module_screens(
        ["quote_editor", "settings", "employees"],
        primary_screen={"id": "quote_editor", "skeleton": "catalog-left-form-right", "blocks": []},
    )
    # settings / employees 属管理工作台范畴，没有员工端屏幕
    assert _ids(screens) == ["quote_editor"]


def test_nav_derives_from_screens_without_dead_links():
    primary = {"id": "quote_editor", "skeleton": "catalog-left-form-right", "blocks": []}
    screens = build_module_screens(["quote_editor", "quotes", "settings"], primary_screen=primary)
    nav = build_nav(screens)

    assert _ids(nav) == _ids(screens)
    assert {n["id"] for n in nav} <= {s["id"] for s in screens}
    assert nav[0]["label"] == "开单" and nav[0]["route"] == "/quote/new"
    assert nav[1]["label"] == "报价单" and nav[1]["route"] == "/quotes"


def test_every_blueprint_is_skeleton_compatible():
    """蓝图里写死的骨架 + 区块必须都在兼容矩阵内，否则会被结构门剔除。"""
    for module, blueprint in MODULE_SCREEN_BLUEPRINTS.items():
        allowed = SKELETON_BLOCK_MATRIX[blueprint["skeleton"]]
        for block_type, _props in blueprint["blocks"]:
            assert block_type in allowed, f"模块 {module} 的 {block_type} 不在 {blueprint['skeleton']} 白名单内"


def test_blueprint_screens_survive_validation_untouched():
    modules = list(MODULE_NAV.keys())
    screens = build_module_screens(
        modules, primary_screen=get_fallback_spec()["screens"][0]
    )
    spec = {
        "spec_version": 1,
        "style": {"preset_id": "medical-clean", "density": "comfortable"},
        "modules": modules,
        "screens": screens,
        "nav": build_nav(screens),
    }
    repaired, issues = validate_and_repair_spec(spec)

    assert not any("不兼容" in i for i in issues), issues
    for screen in repaired["screens"]:
        blueprint = MODULE_SCREEN_BLUEPRINTS.get(screen["id"])
        if not blueprint:
            continue
        expected = [block_type for block_type, _ in blueprint["blocks"]]
        assert [b["type"] for b in screen["blocks"]] == expected, screen["id"]


# --------------------------------------------------------------------------
# 导航门
# --------------------------------------------------------------------------


def test_nav_gate_drops_items_without_screen():
    spec = get_fallback_spec()
    spec["nav"] = [
        {"id": "quote_editor", "label": "开单", "route": "/quote/new", "icon": "edit"},
        {"id": "quotes", "label": "报价单", "route": "/quotes", "icon": "file"},
    ]
    repaired, issues = validate_and_repair_spec(spec)

    assert _ids(repaired["nav"]) == ["quote_editor"]
    assert any("没有对应屏幕" in i for i in issues)


def test_nav_gate_drops_items_outside_modules():
    spec = get_fallback_spec()
    spec["screens"].append(
        {"id": "quotes", "skeleton": "dashboard-grid", "blocks": [{"type": "stats_cards", "props": {}}]}
    )
    spec["modules"] = ["quote_editor"]  # 未启用 quotes
    spec["nav"] = [{"id": "quotes", "label": "报价单"}]
    repaired, issues = validate_and_repair_spec(spec)

    assert _ids(repaired["nav"]) == ["quote_editor"]
    assert any("不在 modules 内" in i for i in issues)


def test_nav_gate_fills_missing_entry_for_screen():
    spec = get_fallback_spec()
    spec["modules"] = ["quote_editor", "quotes"]
    spec["screens"].append(
        {"id": "quotes", "skeleton": "dashboard-grid", "blocks": [{"type": "stats_cards", "props": {}}]}
    )
    spec["nav"] = []  # 屏幕有但导航漏了
    repaired, issues = validate_and_repair_spec(spec)

    assert _ids(repaired["nav"]) == ["quote_editor", "quotes"]
    assert any("缺少导航项" in i for i in issues)


def test_fallback_spec_stays_clean():
    """兜底 Spec 必须自洽：nav 与 screens 一一对应，校验零 issue。"""
    repaired, issues = validate_and_repair_spec(get_fallback_spec())
    assert issues == []
    assert {n["id"] for n in repaired["nav"]} == {s["id"] for s in repaired["screens"]}


# --------------------------------------------------------------------------
# 端到端：编译器 / 预览都要保持一致
# --------------------------------------------------------------------------


def test_compiler_expands_screens_and_nav_from_modules():
    answers = {
        "preset_id": "industrial-dense",
        "pricing_mode": "tiered",
        "require_approval": True,
        "scene": "office",
        "sell_mode": "device_with_consumable",
        "roles": ["admin", "sales"],
    }
    spec, issues = compile_wizard_to_spec(
        answers,
        {"sales_count": 3, "customer_repeat_rate": 2.0},
        source_level="assets",
        provider=None,
        digest={"signals": {}},
    )

    assert issues == []
    assert set(_ids(spec["nav"])) == set(_ids(spec["screens"]))
    assert _ids(spec["screens"])[0] == "quote_editor"
    # 启用了的模块都要有屏幕（settings/employees 无蓝图，本就不该有屏）
    enabled = set(spec["modules"])
    with_screen = enabled & set(MODULE_SCREEN_BLUEPRINTS)
    assert with_screen <= set(_ids(spec["screens"]))
    # 未启用的模块不得出现屏幕
    assert "customers" in with_screen  # 复购率高，本用例应启用
    assert set(_ids(spec["screens"])) - {"quote_editor"} == with_screen


def test_compiler_respects_disabled_modules():
    answers = {"sell_mode": "service", "pricing_mode": "floor_price", "roles": ["admin"]}
    modules = resolve_modules(answers, {"sales_count": 1})
    assert "catalog" not in modules and "employees" not in modules

    spec, _ = compile_wizard_to_spec(answers, {"sales_count": 1}, provider=None, digest={"signals": {}})
    assert set(_ids(spec["nav"])) == set(_ids(spec["screens"]))
    assert "catalog" not in _ids(spec["screens"])


def test_preview_spec_nav_matches_screens():
    for preset_id in ("order-entry", "wholesale", "management"):
        spec = build_preview_spec_draft(preset_id, source_level="sample")
        assert set(_ids(spec["nav"])) == set(_ids(spec["screens"]))
        assert _ids(spec["screens"])[0] == "quote_editor"


def test_rebuild_navigation_is_idempotent():
    primary = {"id": "quote_editor", "skeleton": "catalog-left-form-right", "blocks": []}
    spec = {"modules": ["quote_editor", "quotes"], "screens": [], "nav": []}
    rebuild_navigation(spec, primary_screen=primary)
    first = ([s["id"] for s in spec["screens"]], [n["id"] for n in spec["nav"]])
    rebuild_navigation(spec, primary_screen=primary)
    second = ([s["id"] for s in spec["screens"]], [n["id"] for n in spec["nav"]])
    assert first == second
