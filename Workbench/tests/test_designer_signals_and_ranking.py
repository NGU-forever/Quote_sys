"""测试画像指标计算 (signals.py) 与预设排序规则 (ranking.py)。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.device_binding import DeviceBinding
from app.models.package import Package
from app.models.product import Product
from app.models.quote import Quote
from app.models.user import User


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_empty_db_signals_and_ranking(db_session):
    from app.designer.signals import compute_signals
    from app.designer.ranking import rank_preview_presets, determine_source_level

    signals = compute_signals(db_session)
    assert signals["product_count"] == 0
    assert signals["quote_count"] == 0
    assert signals["sales_count"] == 0
    assert signals["consumable_ratio"] == 0.0

    source_level = determine_source_level(signals)
    assert source_level == "sample"

    ranking = rank_preview_presets(signals)
    assert ranking == ["order-entry", "wholesale", "management"]


def test_seeded_signals_and_ranking(db_session):
    from app.designer.signals import compute_signals
    from app.designer.ranking import rank_preview_presets, determine_source_level

    # 1. 创建用户：2 个销售
    db_session.add(User(username="sales1", password_hash="x", salt="y", role="sales"))
    db_session.add(User(username="sales2", password_hash="x", salt="y", role="sales"))

    # 2. 创建商品：30 个（20 耗材，10 设备）
    for i in range(20):
        db_session.add(
            Product(
                sku_id=f"HC-{i:03d}",
                category="consumable",
                name=f"耗材商品_{i}",
                min_price=10.0 + i,
            )
        )
    for i in range(10):
        db_session.add(
            Product(
                sku_id=f"SB-{i:03d}",
                category="device",
                name=f"设备商品_{i}",
                min_price=1000.0 + i * 100,
            )
        )

    # 3. 创建绑定：12 条
    for i in range(10):
        db_session.add(
            DeviceBinding(device_sku_id="SB-000", consumable_sku_id=f"HC-{i:03d}")
        )
    db_session.add(DeviceBinding(device_sku_id="SB-001", consumable_sku_id="HC-010"))
    db_session.add(DeviceBinding(device_sku_id="SB-001", consumable_sku_id="HC-011"))

    # 4. 创建套餐：2 个
    db_session.add(
        Package(package_id="PKG-01", name="套餐A", std_price=1500.0, discount_price=1200.0)
    )
    db_session.add(
        Package(package_id="PKG-02", name="套餐B", std_price=3000.0, discount_price=2480.0)
    )

    # 5. 创建单据：15 张
    for i in range(15):
        db_session.add(
            Quote(
                quote_no=f"QT-20261012-{i:04d}",
                customer_name=f"客户_{i % 5}",
                total_list_price=2000.0,
                final_quote_price=1800.0,
            )
        )

    db_session.commit()

    signals = compute_signals(db_session)
    assert signals["product_count"] == 30
    assert signals["quote_count"] == 15
    assert signals["sales_count"] == 2
    assert signals["consumable_ratio"] == pytest.approx(20 / 30, 0.01)
    assert signals["binding_density"] == pytest.approx(12 / 10, 0.01)

    source_level = determine_source_level(signals)
    assert source_level == "database"

    # 条件 2: consumable_ratio > 0.6 -> wholesale (②) 排第一
    ranking = rank_preview_presets(signals)
    assert ranking == ["wholesale", "order-entry", "management"]


def test_ranking_conditions():
    from app.designer.ranking import rank_preview_presets

    # 条件 1: quote_count > 200 且 sales_count > 1 -> management (③) 排第一
    sig1 = {
        "product_count": 50,
        "quote_count": 250,
        "sales_count": 3,
        "consumable_ratio": 0.2,
        "binding_density": 0.1,
    }
    assert rank_preview_presets(sig1) == ["management", "order-entry", "wholesale"]

    # 条件 3: binding_density > 0.8 且 consumable_ratio <= 0.6 -> order-entry (①) 排第一
    sig3 = {
        "product_count": 50,
        "quote_count": 50,
        "sales_count": 1,
        "consumable_ratio": 0.3,
        "binding_density": 1.5,
    }
    assert rank_preview_presets(sig3) == ["order-entry", "wholesale", "management"]
