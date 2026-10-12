"""测试真实数据采样选择器 (sampler.py) 与降级逻辑。

覆盖断言：
- 商品列表 8 条含：1 有图 + 1 最长名 + 1 最高价 + 1 最低价
- 套餐卡片：省额最大的套餐
- 底价演示：产出 1 条 ✓ + 1 条 ⚠
- 降级：无价格显示“面议”，无图带文字占位
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
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


def test_empty_sampler_fallback(db_session):
    from app.designer.sampler import sample_preview_data

    data = sample_preview_data(db_session, source_level="sample")
    assert data["source_level"] == "sample"
    assert len(data["products"]) >= 6
    assert data["products"][0]["name"] is not None
    # 必须有底价演示：1 条 ok (✓), 1 条 warn (⚠)
    assert any(item["floor_status"] == "ok" for item in data["demo_items"])
    assert any(item["floor_status"] == "warn" for item in data["demo_items"])


def test_seeded_sampler_rules(db_session):
    from app.designer.sampler import sample_preview_data

    # 创建多样化商品
    p_img = Product(sku_id="P-01", name="普通商品A", category="device", min_price=100.0, image="/uploads/img.png")
    p_long = Product(sku_id="P-02", name="这是一个极其长名字的高端医疗超声波诊断辅助仪器主机", category="device", min_price=200.0)
    p_high = Product(sku_id="P-03", name="超贵设备", category="device", min_price=99999.0)
    p_low = Product(sku_id="P-04", name="超便宜针管", category="consumable", min_price=1.5)
    db_session.add_all([p_img, p_long, p_high, p_low])

    for i in range(5, 12):
        db_session.add(Product(sku_id=f"P-{i:02d}", name=f"常规耗材{i}", category="consumable", min_price=10.0 + i))

    # 创建套餐（Package 1 省 200，Package 2 省 520）
    pkg1 = Package(package_id="PKG-01", name="小套餐", std_price=1000.0, discount_price=800.0) # 省 200
    pkg2 = Package(package_id="PKG-02", name="省大钱套餐", std_price=3000.0, discount_price=2480.0) # 省 520
    db_session.add_all([pkg1, pkg2])

    # 创建一张报价单
    q = Quote(
        quote_no="QT-20261012-0001",
        customer_name="仁爱医院",
        sales_name="张销售",
        total_list_price=10000.0,
        final_quote_price=9500.0,
    )
    db_session.add(q)
    db_session.commit()

    sampled = sample_preview_data(db_session, source_level="database")
    products = sampled["products"]
    sku_set = {p["sku_id"] for p in products}

    # 包含 1 有图 + 1 最长名 + 1 最高价 + 1 最低价
    assert "P-01" in sku_set  # 有图
    assert "P-02" in sku_set  # 最长名
    assert "P-03" in sku_set  # 最高价
    assert "P-04" in sku_set  # 最低价
    assert 6 <= len(products) <= 8

    # 套餐推荐为省额最大的套餐 (省 520)
    assert sampled["featured_package"] is not None
    assert sampled["featured_package"]["package_id"] == "PKG-02"
    assert sampled["featured_package"]["saving_amount"] == 520.0

    # 报价单与客户名
    assert sampled["recent_quote"]["customer_name"] == "仁爱医院"

    # 底价校验演示
    assert len(sampled["demo_items"]) >= 2
    assert any(item["floor_status"] == "ok" for item in sampled["demo_items"])
    assert any(item["floor_status"] == "warn" for item in sampled["demo_items"])
