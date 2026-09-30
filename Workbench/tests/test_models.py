import json
import sys
import unittest
from pathlib import Path

# Ensure Workbench directory is in sys.path
workbench_dir = Path(__file__).resolve().parent.parent
if str(workbench_dir) not in sys.path:
    sys.path.insert(0, str(workbench_dir))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import (
    AppSetting,
    DeviceBinding,
    ImportRun,
    ImportRunEvent,
    ItemRelation,
    Package,
    Product,
    Quote,
    User,
)
from app.db.init_db import init_db
from app.db.seed import seed_reserved_admin


class TestModels(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_user_model_defaults_and_fields(self):
        with self.Session() as db:
            user = User(
                username="sales_rep",
                password_hash="fake_hash",
                salt="fake_salt",
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            self.assertIsNotNone(user.id)
            self.assertEqual(user.username, "sales_rep")
            self.assertEqual(user.role, "sales")
            self.assertTrue(user.is_active)
            self.assertIsNone(user.real_name)
            self.assertIsNone(user.phone)
            self.assertIsNotNone(user.created_at)
            self.assertIsNotNone(user.updated_at)

            # Test updating custom fields
            user.real_name = "张三"
            user.phone = "13800138000"
            user.role = "manager"
            user.is_active = False
            db.commit()
            db.refresh(user)

            self.assertEqual(user.real_name, "张三")
            self.assertEqual(user.phone, "13800138000")
            self.assertEqual(user.role, "manager")
            self.assertFalse(user.is_active)

    def test_product_generic_categories_and_spec(self):
        with self.Session() as db:
            # Should allow arbitrary generic categories without CheckConstraint failure
            p1 = Product(
                sku_id="HW-IOT-001",
                category="hardware",
                name="智能网关终端",
                spec="4核/8G/双网口",
                unit="台",
                min_price=1200.0,
                max_price=1500.0,
                is_active=True,
            )
            p2 = Product(
                sku_id="SVC-DEP-001",
                category="service",
                name="现场部署与技术支持服务",
                spec="标准人天",
                unit="人天",
                min_price=800.0,
                max_price=1000.0,
                is_active=True,
            )
            p3 = Product(
                sku_id="SEN-TMP-001",
                category="sensor",
                name="无线温湿度传感器",
                spec="LoRaWAN协议",
                unit="个",
                min_price=150.0,
                max_price=200.0,
                applicable_devices="HW-IOT-001",
                pieces_per_unit=1,
                raw_price_desc="含税出厂价",
                is_active=True,
            )
            db.add_all([p1, p2, p3])
            db.commit()

            products = db.scalars(select(Product).order_by(Product.id.asc())).all()
            self.assertEqual(len(products), 3)
            self.assertEqual(products[0].category, "hardware")
            self.assertEqual(products[0].spec, "4核/8G/双网口")
            self.assertTrue(products[0].is_active)
            self.assertEqual(products[1].category, "service")
            self.assertEqual(products[2].applicable_devices, "HW-IOT-001")
            self.assertEqual(products[2].raw_price_desc, "含税出厂价")

    def test_quote_model_creation_and_snapshot(self):
        with self.Session() as db:
            user = User(
                username="seller_01",
                password_hash="pwd",
                salt="slt",
                real_name="李四",
                phone="13911112222",
                role="sales",
            )
            db.add(user)
            db.commit()

            items = [
                {"sku_id": "HW-IOT-001", "name": "智能网关终端", "quantity": 2, "price": 1300.0},
                {"sku_id": "SVC-DEP-001", "name": "现场部署", "quantity": 1, "price": 800.0},
            ]
            quote = Quote(
                quote_no="Q20260930-0001",
                user_id=user.id,
                sales_name=user.real_name,
                sales_phone=user.phone,
                customer_name="未来科技有限责任公司",
                customer_contact="王总",
                customer_phone="13700000000",
                status="draft",
                total_list_price=3400.0,
                discount_rate=0.9,
                final_quote_price=3060.0,
                valid_days=30,
                remark="请于10月前确认",
                items_snapshot=items,
            )
            db.add(quote)
            db.commit()
            db.refresh(quote)

            self.assertIsNotNone(quote.id)
            self.assertEqual(quote.quote_no, "Q20260930-0001")
            self.assertEqual(quote.user_id, user.id)
            self.assertEqual(quote.sales_name, "李四")
            self.assertEqual(quote.customer_name, "未来科技有限责任公司")
            self.assertEqual(quote.final_quote_price, 3060.0)
            self.assertEqual(quote.valid_days, 30)
            self.assertIsNotNone(quote.created_at)
            self.assertIsNotNone(quote.updated_at)

            # Check snapshot JSON retrieval
            queried = db.scalar(select(Quote).where(Quote.quote_no == "Q20260930-0001"))
            self.assertIsNotNone(queried)
            self.assertEqual(len(queried.items_snapshot), 2)
            self.assertEqual(queried.items_snapshot[0]["sku_id"], "HW-IOT-001")

            # Check user relationship
            self.assertEqual(queried.user.username, "seller_01")

    def test_package_generic_and_legacy_fields(self):
        with self.Session() as db:
            # Test generic package instantiation with new attributes and synonyms
            pkg1 = Package(
                package_code="PKG-STD-IOT",
                name="物联网标准入门套餐",
                description="含网关及2只传感器",
                bundle_price=1600.0,
                items_config=[
                    {"sku_id": "HW-IOT-001", "quantity": 1},
                    {"sku_id": "SEN-TMP-001", "quantity": 2},
                ],
                is_active=True,
            )
            db.add(pkg1)
            db.commit()
            db.refresh(pkg1)

            # Check synonym access: package_id <-> package_code
            self.assertEqual(pkg1.package_id, "PKG-STD-IOT")
            self.assertEqual(pkg1.package_code, "PKG-STD-IOT")
            self.assertEqual(pkg1.description, "含网关及2只传感器")
            self.assertEqual(pkg1.note, "含网关及2只传感器")
            self.assertEqual(pkg1.bundle_price, 1600.0)
            self.assertEqual(pkg1.std_price, 1600.0)
            self.assertTrue(pkg1.is_active)
            self.assertEqual(len(pkg1.items_config), 2)

            # Query using package_code
            found = db.scalar(select(Package).where(Package.package_code == "PKG-STD-IOT"))
            self.assertIsNotNone(found)
            self.assertEqual(found.id, pkg1.id)

            # Test legacy package backward compatibility
            pkg2 = Package(
                package_id="PKG-LEGACY-01",
                name="传统医疗耗材包",
                sku_ids=json.dumps(["DEV01", "CSM01"]),
                quantities=json.dumps([1, 10]),
                std_price=999.0,
                note="旧系统套餐",
            )
            db.add(pkg2)
            db.commit()
            db.refresh(pkg2)

            self.assertEqual(pkg2.package_code, "PKG-LEGACY-01")
            self.assertEqual(pkg2.description, "旧系统套餐")
            self.assertEqual(pkg2.bundle_price, 999.0)
            self.assertTrue(pkg2.is_active)

    def test_item_relation_model(self):
        with self.Session() as db:
            parent = Product(
                sku_id="DEV-MAIN-01",
                category="hardware",
                name="主控制器",
                min_price=2000.0,
                max_price=2200.0,
            )
            child1 = Product(
                sku_id="ACC-CABLE-01",
                category="accessory",
                name="高屏蔽工业通信线缆",
                min_price=50.0,
                max_price=60.0,
            )
            child2 = Product(
                sku_id="ACC-PWR-01",
                category="accessory",
                name="工业导轨电源模块",
                min_price=120.0,
                max_price=150.0,
            )
            db.add_all([parent, child1, child2])
            db.commit()

            rel1 = ItemRelation(
                parent_product_id=parent.id,
                child_product_id=child1.id,
                relation_type="accessory",
            )
            rel2 = ItemRelation(
                parent_product_id=parent.id,
                child_product_id=child2.id,
                relation_type="accessory",
            )
            db.add_all([rel1, rel2])
            db.commit()

            relations = db.scalars(
                select(ItemRelation).where(ItemRelation.parent_product_id == parent.id)
            ).all()
            self.assertEqual(len(relations), 2)
            self.assertEqual(relations[0].parent_product.sku_id, "DEV-MAIN-01")
            self.assertEqual(relations[0].child_product.name, "高屏蔽工业通信线缆")
            self.assertEqual(relations[1].child_product.name, "工业导轨电源模块")

    def test_init_db_and_seed_reserved_admin(self):
        with self.Session() as db:
            seed_reserved_admin(db)
            admin = db.scalar(select(User).where(User.username == "admin"))
            self.assertIsNotNone(admin)
            self.assertEqual(admin.role, "admin")
            self.assertTrue(admin.is_active)
            self.assertIsNotNone(admin.real_name)

        # Test init_db with sample data option
        engine_sample = create_engine("sqlite:///:memory:", future=True)
        init_db(engine=engine_sample, seed_sample_data=True)
        SessionSample = sessionmaker(bind=engine_sample, future=True)
        with SessionSample() as db:
            admin = db.scalar(select(User).where(User.username == "admin"))
            self.assertIsNotNone(admin)
            self.assertEqual(admin.role, "admin")

            # Verify sample products were seeded
            products = db.scalars(select(Product)).all()
            self.assertGreaterEqual(len(products), 3)

            # Verify sample relations
            relations = db.scalars(select(ItemRelation)).all()
            self.assertGreaterEqual(len(relations), 1)


# Standalone functions for pytest compatibility
def test_pytest_models_lifecycle():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as db:
        user = User(username="u1", password_hash="p", salt="s", real_name="测试用户", role="sales")
        prod = Product(sku_id="P1", category="custom_cat", name="测试产品", spec="默认规格")
        db.add_all([user, prod])
        db.commit()

        q = Quote(
            quote_no="Q-TEST-001",
            user_id=user.id,
            customer_name="测试客户",
            items_snapshot=[{"sku_id": "P1", "qty": 1}],
        )
        pkg = Package(
            package_code="PKG-01",
            name="套餐一",
            description="描述",
            bundle_price=100.0,
            items_config=[{"sku_id": "P1", "qty": 1}],
        )
        db.add_all([q, pkg])
        db.commit()

        assert q.id is not None
        assert q.user.real_name == "测试用户"
        assert pkg.package_id == "PKG-01"
        assert pkg.description == "描述"


if __name__ == "__main__":
    unittest.main()
