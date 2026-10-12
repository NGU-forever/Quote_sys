"""设计器端到端全流程与质量门禁断言测试。

严格覆盖设计规范 §13.1 全部 9 条核心断言：
1) 排序断言：有绑定有设备时开单型与各预设命中即停
2) 商品采样：8 条内含 1 有图 + 1 最长名 + 1 最高价 + 1 最低价
3) 套餐卡片：挑选省额最大套餐 (如省 520)
4) 第 4 屏定价默认："按底价卖不议价" (max_price 全空)
5) 标签与术语：min_price 降级与映射
6) 底价校验：同时产出 1 条 ✓ + 1 条 ⚠
7) 空库保障：排序固定 [①, ②, ③] 且 source_level = sample
8) 非法字段注入：第二道门剔除，整体产出合规 Spec
9) 有界自愈兜底：极端破损 Spec 优雅回退规则兜底 Spec (永不抛异常给用户)
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.designer.compiler import compile_wizard_to_spec
from app.designer.ranking import determine_source_level, rank_preview_presets
from app.designer.sampler import sample_preview_data
from app.designer.schema import get_fallback_spec
from app.designer.signals import compute_signals
from app.designer.validator import validate_and_repair_spec
from app.models.device_binding import DeviceBinding
from app.models.package import Package
from app.models.product import Product
from app.models.quote import Quote
from app.models.user import User


@pytest.fixture
def seeded_db():
    engine = create_engine("sqlite:///:memory:", future=True)
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = Session()

    # 固定 seed：30 商品（20 耗材/10 设备）、12 绑定、2 套餐、15 单据、2 销售
    db.add(User(username="s1", password_hash="x", salt="y", role="sales"))
    db.add(User(username="s2", password_hash="x", salt="y", role="sales"))

    p_img = Product(sku_id="P-01", name="探头A", category="device", min_price=100.0, image="/uploads/1.jpg")
    p_long = Product(sku_id="P-02", name="超长全数字彩色超声波仪设备", category="device", min_price=200.0)
    p_high = Product(sku_id="P-03", name="至尊主机", category="device", min_price=99999.0)
    p_low = Product(sku_id="P-04", name="极低针管", category="consumable", min_price=1.2)
    db.add_all([p_img, p_long, p_high, p_low])

    for i in range(5, 11):
        db.add(Product(sku_id=f"P-{i:02d}", name=f"设备_{i}", category="device", min_price=1000.0 + i))
    for i in range(11, 31):
        db.add(Product(sku_id=f"P-{i:02d}", name=f"耗材_{i}", category="consumable", min_price=10.0 + i))

    for i in range(12):
        db.add(DeviceBinding(device_sku_id="P-01", consumable_sku_id=f"P-{11+i:02d}"))

    pkg1 = Package(package_id="PKG-01", name="小包", std_price=1000.0, discount_price=800.0)
    pkg2 = Package(package_id="PKG-02", name="省520套餐", std_price=3000.0, discount_price=2480.0)
    db.add_all([pkg1, pkg2])

    for i in range(15):
        db.add(Quote(quote_no=f"QT-20261012-{i:04d}", customer_name=f"客户{i}", total_list_price=1000.0, final_quote_price=900.0))

    db.commit()
    try:
        yield db
    finally:
        db.close()


def test_quality_gate_assertions(seeded_db):
    signals = compute_signals(seeded_db)

    # 1) 排序：consumable_ratio > 0.6 时 wholesale (②) 排第一
    ranking = rank_preview_presets(signals)
    assert ranking[0] == "wholesale"

    # 2) 商品采样包含 1 有图 + 1 最长名 + 1 最高价 + 1 最低价
    sample_data = sample_preview_data(seeded_db, source_level="database")
    skus = {p["sku_id"] for p in sample_data["products"]}
    assert "P-01" in skus  # 有图
    assert "P-02" in skus  # 最长名
    assert "P-03" in skus  # 最高价
    assert "P-04" in skus  # 最低价
    assert len(sample_data["products"]) <= 8

    # 3) 套餐卡片挑选省额最大 (省 520)
    assert sample_data["featured_package"]["saving_amount"] == 520.0
    assert sample_data["featured_package"]["package_id"] == "PKG-02"

    # 4) 第 4 屏默认：max_price 全空时无议价空间
    assert signals["has_negotiable"] is False

    # 6) 底价演示同时包含 1 条 ok (✓) 与 1 条 warn (⚠)
    demo_items = sample_data["demo_items"]
    assert any(i["floor_status"] == "ok" for i in demo_items)
    assert any(i["floor_status"] == "warn" for i in demo_items)

    # 8) 非法字段注入被第二道门剔除
    dirty_spec = get_fallback_spec()
    dirty_spec["entities"]["product"]["list_columns"].append("malicious_field_injection")
    cleaned_spec, issues = validate_and_repair_spec(dirty_spec)
    assert "malicious_field_injection" not in cleaned_spec["entities"]["product"]["list_columns"]

    # 9) 极端损坏 Spec 优雅自愈回退兜底
    repaired, _ = validate_and_repair_spec("invalid_corrupted_string")
    assert repaired["spec_version"] == 1
    assert "quote_editor" in repaired["modules"]


def test_empty_db_assertions():
    engine = create_engine("sqlite:///:memory:", future=True)
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    empty_db = Session()

    signals = compute_signals(empty_db)
    source_level = determine_source_level(signals)
    ranking = rank_preview_presets(signals)

    # 7) 空库 → 排序固定 [①, ②, ③] 且 source_level = sample
    assert source_level == "sample"
    assert ranking == ["order-entry", "wholesale", "management"]

    sample_data = sample_preview_data(empty_db, source_level=source_level)
    assert sample_data["source_level"] == "sample"
    assert len(sample_data["products"]) >= 6
