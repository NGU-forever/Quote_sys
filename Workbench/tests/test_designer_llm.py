"""M4 测试：业务画像、术语本地化与 LLM 有界自愈。

关键约束（设计文档 §2 D3）：
- 没有模型时必须完全可用（规则画像 + 规则术语）；
- 模型提案被三道门拒绝时回传错误自愈，最多 3 次；
- 3 次仍不通过 → 回退规则 Spec，且**不把错误抛给用户**；
- 模型调用失败 → 同样回退，不影响出结果。
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.llm_client import LLMResponse, ToolCall
from app.api.designer import router as designer_router
from app.db.base import Base
from app.designer.compiler import compile_wizard_to_spec, resolve_modules, resolve_skeleton
from app.designer.llm import enrich_spec_with_llm, is_violation, merge_enrichment
from app.designer.profiles import resolve_profile, rule_based_profile
from app.designer.schema import get_fallback_spec
from app.designer.terminology import (
    detect_price_term,
    detect_promo_tone,
    localize_field_labels,
    merge_labels,
)

TOOL_NAME = "submit_design_enrichment"


class FakeProvider:
    """按脚本返回 submit_design_enrichment 的假模型。"""

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def chat(self, messages, tool_schemas):
        self.calls.append({"messages": messages, "tools": tool_schemas})
        payload = self.payloads.pop(0) if self.payloads else {}
        if isinstance(payload, Exception):
            raise payload
        return LLMResponse(
            tool_calls=[ToolCall(TOOL_NAME, payload, call_id=TOOL_NAME)],
            summary="fake",
            model="fake",
        )


class NoToolProvider:
    def chat(self, messages, tool_schemas):
        return LLMResponse(tool_calls=[], summary="我不调用工具")


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
    yield session
    session.close()


# --------------------------------------------------------------------------
# 画像：规则优先、离线可用
# --------------------------------------------------------------------------


def test_rule_based_profile_offline(db):
    profile, issues, digest = resolve_profile(db, provider=None)
    assert issues == []
    assert profile["industry"] == "medical"
    assert profile["pricing_mode"] == "floor_price"
    assert profile["scene"] == "on_site"
    assert "signals" in digest


def test_rule_based_profile_reflects_signals():
    profile = rule_based_profile(
        {"signals": {"product_count": 100, "consumable_ratio": 0.95, "has_negotiable": True}}
    )
    assert profile["sell_mode"] == "consumable_only"
    assert profile["pricing_mode"] == "negotiable"

    device_heavy = rule_based_profile(
        {"signals": {"product_count": 50, "consumable_ratio": 0.02}}
    )
    assert device_heavy["sell_mode"] == "device_only"

    management = rule_based_profile(
        {"signals": {"product_count": 10, "quote_count": 500, "sales_count": 3}}
    )
    assert management["scene"] == "office"


def test_resolve_profile_with_model_merges_llm_judgement(db):
    provider = FakeProvider(
        [{"profile": {"industry": "industrial", "pricing_mode": "tiered"}}]
    )
    profile, issues, _ = resolve_profile(db, provider=provider)
    assert profile["industry"] == "industrial"
    assert profile["pricing_mode"] == "tiered"
    # 规则兜底的键仍然保留
    assert "roles" in profile and "output_targets" in profile


# --------------------------------------------------------------------------
# 术语本地化
# --------------------------------------------------------------------------


def test_price_term_detection_and_labels():
    texts = ["本表底价如下", "供货价：2500", "供货价 3000"]
    term, counts = detect_price_term(texts)
    assert term == "供货价"
    assert counts["供货价"] == 2

    labels = localize_field_labels(price_term="供货价", promo=True)
    assert labels["product"]["min_price"] == "供货价"
    assert labels["product"]["raw_price_desc"] == "促销口径"

    assert localize_field_labels("")["product"]["min_price"] == "最低底价"
    assert detect_promo_tone(["买赠活动，满赠耗材"]) is True
    assert detect_promo_tone(["标准价目表"]) is False


def test_merge_labels_llm_overrides_rules():
    merged = merge_labels(
        {"product": {"min_price": "最低底价"}},
        {"product": {"min_price": "同行价", "name": "产品名"}, "quote": {}},
    )
    assert merged["product"]["min_price"] == "同行价"
    assert merged["product"]["name"] == "产品名"
    assert merged["quote"] == {}


# --------------------------------------------------------------------------
# 有界自愈
# --------------------------------------------------------------------------


def test_is_violation_only_flags_rejections():
    assert is_violation("字段门：实体 'product' 包含非法字段 {'x'}，已被过滤")
    assert is_violation("结构门：Block 'x' 不在骨架 'y' 的兼容白名单内，已被剔除")
    # 良性修复不触发重试
    assert not is_violation("结构门：缺失 screens 定义，已回退到默认开单屏幕")
    assert not is_violation("枚举门：必须包含 'quote_editor' 模块，已自动补齐")


def test_merge_enrichment_applies_labels_and_columns():
    spec = get_fallback_spec()
    merged = merge_enrichment(
        spec,
        {
            "profile": {"industry": "retail"},
            "labels": {"product": {"min_price": "批发价"}},
            "list_columns": {"product": ["sku_id", "name"]},
            "issues": ["资料里没有套餐依据"],
        },
    )
    assert merged["profile"]["industry"] == "retail"
    assert merged["entities"]["product"]["labels"]["min_price"] == "批发价"
    assert merged["entities"]["product"]["list_columns"] == ["sku_id", "name"]
    assert merged["meta"]["llm_enriched"] is True
    assert merged["meta"]["llm_issues"] == ["资料里没有套餐依据"]
    # 原 spec 不被修改
    assert spec["entities"]["product"]["list_columns"] != ["sku_id", "name"]


def test_self_heal_recovers_on_third_attempt():
    provider = FakeProvider(
        [
            {"list_columns": {"product": ["不存在的字段", "name"]}},
            {"list_columns": {"product": ["还是不存在"]}},
            {"list_columns": {"product": ["sku_id", "name"]}, "profile": {"industry": "retail"}},
        ]
    )
    spec, issues, attempts = enrich_spec_with_llm(get_fallback_spec(), {}, provider, max_attempts=3)
    assert attempts == 3
    assert spec["entities"]["product"]["list_columns"] == ["sku_id", "name"]
    assert spec["profile"]["industry"] == "retail"
    assert not any("回退规则 Spec" in i for i in issues)
    # 第三轮必须看到前两轮的具体错误
    third_prompt = provider.calls[2]["messages"][-1]["content"]
    assert "previous_validation_errors" in third_prompt


def test_self_heal_gives_up_and_falls_back():
    provider = FakeProvider([{"list_columns": {"product": ["非法字段"]}}] * 5)
    spec, issues, attempts = enrich_spec_with_llm(get_fallback_spec(), {}, provider, max_attempts=3)
    assert attempts == 3
    assert any("回退规则 Spec" in i for i in issues)
    # 回退后仍是合法可渲染的 Spec
    assert spec["entities"]["product"]["list_columns"]


def test_provider_failure_falls_back_without_raising():
    provider = FakeProvider([RuntimeError("网关 502")])
    spec, issues, attempts = enrich_spec_with_llm(get_fallback_spec(), {}, provider, max_attempts=3)
    assert attempts == 1
    assert any("已回退规则方案" in i for i in issues)
    assert spec["spec_version"] == 1


def test_no_tool_call_falls_back():
    spec, issues, attempts = enrich_spec_with_llm(
        get_fallback_spec(), {}, NoToolProvider(), max_attempts=2
    )
    assert attempts == 2
    assert any("回退规则 Spec" in i for i in issues)


def test_provider_none_is_pure_rules():
    spec, issues, attempts = enrich_spec_with_llm(get_fallback_spec(), {}, None)
    assert attempts == 0
    assert issues == []


# --------------------------------------------------------------------------
# 编译器：骨架与模块全量可达
# --------------------------------------------------------------------------


def test_all_five_skeletons_reachable():
    assert resolve_skeleton({"view_mode": "management"}, {}) == "dashboard-grid"
    assert resolve_skeleton({"scene": "mobile"}, {}) == "mobile-single-column"
    assert resolve_skeleton({"require_approval": True}, {}) == "form-first-wizard"
    assert resolve_skeleton({"pricing_mode": "tiered"}, {}) == "form-first-wizard"
    assert resolve_skeleton({"scene": "office"}, {}) == "list-detail-split"
    assert resolve_skeleton({"scene": "on_site"}, {}) == "catalog-left-form-right"


def test_modules_include_customers_for_repeat_business():
    modules = resolve_modules({"roles": ["admin", "sales"]}, {"sales_count": 3, "customer_repeat_rate": 2.0})
    assert "employees" in modules
    assert "customers" in modules
    assert "catalog" in modules

    lean = resolve_modules({"roles": ["admin"], "sell_mode": "service"}, {"sales_count": 1})
    assert "catalog" not in lean
    assert "employees" not in lean


def test_compile_is_pure_rules_without_provider():
    spec, issues = compile_wizard_to_spec(
        {"preset_id": "industrial-dense", "pricing_mode": "tiered", "require_approval": True},
        {"sales_count": 2, "customer_repeat_rate": 3.0},
        source_level="sample",
        provider=None,
        digest={"price_term": "供货价", "promo": True, "signals": {"product_count": 30}},
    )
    assert spec["style"]["preset_id"] == "industrial-dense"
    assert spec["screens"][0]["skeleton"] == "form-first-wizard"
    assert "customers" in spec["modules"]
    assert spec["entities"]["product"]["labels"]["min_price"] == "供货价"
    assert spec["meta"]["source_level"] == "sample"
    assert not any("回退规则 Spec" in i for i in issues)


def test_compile_with_model_applies_enrichment_and_audits_attempts():
    provider = FakeProvider(
        [{"profile": {"industry": "retail"}, "labels": {"product": {"min_price": "批发价"}}}]
    )
    spec, issues = compile_wizard_to_spec(
        {"scene": "on_site"},
        {"sales_count": 1},
        provider=provider,
        digest={"price_term": "", "promo": False, "signals": {}},
    )
    assert spec["profile"]["industry"] == "retail"
    assert spec["entities"]["product"]["labels"]["min_price"] == "批发价"
    assert spec["meta"]["llm_attempts"] == 1
    assert not any("回退" in i for i in issues)


def test_compile_falls_back_when_model_unavailable():
    provider = FakeProvider([RuntimeError("connection refused")])
    spec, issues = compile_wizard_to_spec(
        {"scene": "on_site"}, {}, provider=provider, digest={"signals": {}}
    )
    assert any("已回退规则方案" in i for i in issues)
    assert spec["screens"][0]["skeleton"] == "catalog-left-form-right"


# --------------------------------------------------------------------------
# 路由
# --------------------------------------------------------------------------


def test_profile_route_registered():
    paths = {route.path for route in designer_router.routes}
    assert "/api/designer/profile" in paths
    assert "/api/designer/compile" in paths
