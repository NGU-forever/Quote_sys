"""QuoteSys Task 4 业务 API 与 Redis 缓存端点测试。

涵盖：
1. 单号原子生成（Redis 模式与数据库当日降级模式）
2. 报价单创建、明细快照持久化、列表筛选/分页与销售人员隔离
3. 单张报价单明细按 quote_no 查询
4. 员工账号管理（管理员创建销售/管理账号、分页筛选列表、密码哈希安全脱敏）
5. /api/catalog 通用类目支持、Redis 缓存与优雅降级、主动失效
"""
import asyncio
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Ensure Workbench directory is in sys.path
workbench_dir = Path(__file__).resolve().parent.parent
if str(workbench_dir) not in sys.path:
    sys.path.insert(0, str(workbench_dir))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.deps import get_db
from app.core.security import create_access_token, hash_password
from app.db.base import Base

from app.main import app
from app.models.product import Product
from app.models.quote import Quote
from app.models.user import RESERVED_ADMIN_USERNAME, User
from app.schemas.employee_schemas import EmployeeCreate, EmployeeListResponse, EmployeeOut
from app.schemas.quote_schemas import (
    QuoteCreate,
    QuoteItemSnapshot,
    QuoteListResponse,
    QuoteOut,
)
from app.services.catalog_service import (
    CATALOG_CACHE_KEY,
    get_cached_catalog,
    invalidate_catalog_cache,
)
from app.services.quote_service import (
    create_quote,
    generate_quote_no,
    get_quote_by_no,
    get_quotes,
)


class TestQuoteAPI(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)


        def _get_test_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _get_test_db
        self.client = TestClient(app)

        # 种子数据
        with self.Session() as db:
            # 内置管理员
            admin_pwd = hash_password("admin123")
            self.admin_user = User(
                username="admin",
                password_hash=admin_pwd["hash"],
                salt=admin_pwd["salt"],
                real_name="系统管理员",
                phone="13800000000",
                role="admin",
                is_active=True,
            )
            # 销售员工 A
            sales_a_pwd = hash_password("sales123")
            self.sales_user_a = User(
                username="sales_a",
                password_hash=sales_a_pwd["hash"],
                salt=sales_a_pwd["salt"],
                real_name="销售员A",
                phone="13800000001",
                role="sales",
                is_active=True,
            )
            # 销售员工 B
            sales_b_pwd = hash_password("sales123")
            self.sales_user_b = User(
                username="sales_b",
                password_hash=sales_b_pwd["hash"],
                salt=sales_b_pwd["salt"],
                real_name="销售员B",
                phone="13800000002",
                role="sales",
                is_active=True,
            )
            # 通用商品：包含硬件、耗材、服务、传感器
            self.p_hw = Product(
                sku_id="HW-001",
                category="hardware",
                name="智能工作站终端",
                spec="4核/16G/512G",
                min_price=5000.0,
                max_price=6000.0,
                unit="台",
                is_active=True,
            )
            self.p_svc = Product(
                sku_id="SVC-001",
                category="service",
                name="专家现场安装培训服务",
                spec="标准人天",
                min_price=1200.0,
                max_price=1500.0,
                unit="人天",
                is_active=True,
            )
            self.p_csm = Product(
                sku_id="CSM-001",
                category="consumable",
                name="专用医用耦合剂",
                spec="250g/支",
                min_price=25.0,
                max_price=30.0,
                unit="支",
                units_per_box=20,
                pieces_per_unit=1,
                is_active=True,
            )
            db.add_all([self.admin_user, self.sales_user_a, self.sales_user_b, self.p_hw, self.p_svc, self.p_csm])
            db.commit()
            db.refresh(self.admin_user)
            db.refresh(self.sales_user_a)
            db.refresh(self.sales_user_b)

        self.admin_token = create_access_token(self.admin_user.id, self.admin_user.username)
        self.sales_a_token = create_access_token(self.sales_user_a.id, self.sales_user_a.username)
        self.sales_b_token = create_access_token(self.sales_user_b.id, self.sales_user_b.username)

    def tearDown(self):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    # ---------- 1. 单号生成测试 ----------
    def test_quote_no_generation_db_fallback(self):
        """测试 Redis 不可用时，基于数据库当日序号降级生成 QT-YYYYMMDD-0001。"""
        with self.Session() as db:
            today_str = datetime.now().strftime("%Y%m%d")
            # 初始为空时降级生成 0001
            no1 = asyncio.run(generate_quote_no(db))
            self.assertEqual(no1, f"QT-{today_str}-0001")

            # 插入已有记录后再生成应自增为 0002
            q1 = Quote(
                quote_no=no1,
                customer_name="测试客户1",
                items_snapshot=[],
            )
            db.add(q1)
            db.commit()

            no2 = asyncio.run(generate_quote_no(db))
            self.assertEqual(no2, f"QT-{today_str}-0002")

    def test_quote_no_generation_with_redis(self):
        """测试 Redis 可用时使用 INCR 生成递增单号。"""
        fake_redis = AsyncMock()
        fake_redis.set = AsyncMock()
        fake_redis.incr = AsyncMock(side_effect=[1, 2, 3])
        fake_redis.expire = AsyncMock()

        with patch("app.services.quote_service.get_redis", return_value=fake_redis):
            with self.Session() as db:
                today_str = datetime.now().strftime("%Y%m%d")
                no1 = asyncio.run(generate_quote_no(db))
                self.assertEqual(no1, f"QT-{today_str}-0001")
                fake_redis.incr.assert_called_with(f"quote:seq:QT-{today_str}")

                no2 = asyncio.run(generate_quote_no(db))
                self.assertEqual(no2, f"QT-{today_str}-0002")

    def test_quote_no_redis_restart_collision_prevention(self):
        """测试 Redis 重启或键丢失后，能够基于 DB 最大序号初始化 Redis 键，防止单号碰撞。"""
        with self.Session() as db:
            today_str = datetime.now().strftime("%Y%m%d")
            # 数据库中已存在 0005 号单据
            q = Quote(
                quote_no=f"QT-{today_str}-0005",
                customer_name="历史客户",
                items_snapshot=[],
            )
            db.add(q)
            db.commit()

            fake_redis = AsyncMock()
            fake_redis.set = AsyncMock()
            fake_redis.incr = AsyncMock(return_value=6)
            fake_redis.expire = AsyncMock()

            with patch("app.services.quote_service.get_redis", return_value=fake_redis):
                new_no = asyncio.run(generate_quote_no(db))
                self.assertEqual(new_no, f"QT-{today_str}-0006")
                fake_redis.set.assert_called_with(f"quote:seq:QT-{today_str}", 5, nx=True, ex=86400 * 2)


    # ---------- 2. 报价单创建与快照持久化 ----------
    def test_create_quote_api_authenticated(self):
        """销售人员创建报价单，验证单号生成、快照存储与销售信息自动填充。"""
        payload = {
            "customer_name": "华东联合医院",
            "customer_contact": "周主任",
            "customer_phone": "13912345678",
            "total_list_price": 6200.0,
            "discount_rate": 0.95,
            "final_quote_price": 5890.0,
            "valid_days": 15,
            "remark": "包含首次现场培训",
            "items_snapshot": [
                {
                    "sku_id": "HW-001",
                    "name": "智能工作站终端",
                    "spec": "4核/16G/512G",
                    "unit": "台",
                    "quantity": 1,
                    "price": 5000.0,
                    "subtotal": 5000.0,
                },
                {
                    "sku_id": "SVC-001",
                    "name": "专家现场安装培训服务",
                    "unit": "人天",
                    "quantity": 1,
                    "price": 1200.0,
                    "subtotal": 1200.0,
                },
            ],
        }

        resp = self.client.post(
            "/api/quotes",
            json=payload,
            headers={"Authorization": f"Bearer {self.sales_a_token}"},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        today_str = datetime.now().strftime("%Y%m%d")
        self.assertTrue(data["quote_no"].startswith(f"QT-{today_str}-"))
        self.assertEqual(data["customer_name"], "华东联合医院")
        self.assertEqual(data["sales_name"], "销售员A")
        self.assertEqual(data["sales_phone"], "13800000001")
        self.assertEqual(data["user_id"], self.sales_user_a.id)
        self.assertEqual(data["final_quote_price"], 5890.0)
        self.assertEqual(len(data["items_snapshot"]), 2)
        self.assertEqual(data["items_snapshot"][0]["sku_id"], "HW-001")

        # 检查数据库落地
        with self.Session() as db:
            saved = db.scalar(select(Quote).where(Quote.quote_no == data["quote_no"]))
            self.assertIsNotNone(saved)
            self.assertEqual(saved.customer_contact, "周主任")
            self.assertEqual(len(saved.items_snapshot), 2)

    # ---------- 3. 报价单列表查询与销售隔离 ----------
    def test_quote_list_and_sales_isolation(self):
        """测试报价单列表查询：销售只能看自己，管理员全量查看，支持 keyword 筛选。"""
        # 销售 A 创建两单，销售 B 创建一单
        with self.Session() as db:
            q_a1 = Quote(
                quote_no="QT-20260930-0001",
                user_id=self.sales_user_a.id,
                sales_name=self.sales_user_a.real_name,
                sales_phone=self.sales_user_a.phone,
                customer_name="甲客户",
                status="draft",
                total_list_price=1000.0,
                final_quote_price=1000.0,
                items_snapshot=[],
            )
            q_a2 = Quote(
                quote_no="QT-20260930-0002",
                user_id=self.sales_user_a.id,
                sales_name=self.sales_user_a.real_name,
                sales_phone=self.sales_user_a.phone,
                customer_name="乙客户综合门诊",
                status="submitted",
                total_list_price=2000.0,
                final_quote_price=1800.0,
                items_snapshot=[],
            )
            q_b1 = Quote(
                quote_no="QT-20260930-0003",
                user_id=self.sales_user_b.id,
                sales_name=self.sales_user_b.real_name,
                sales_phone=self.sales_user_b.phone,
                customer_name="丙客户诊所",
                status="draft",
                total_list_price=3000.0,
                final_quote_price=3000.0,
                items_snapshot=[],
            )
            db.add_all([q_a1, q_a2, q_b1])
            db.commit()

        # 1. 销售 A 查询：只能查到 A 的 2 单
        resp_a = self.client.get(
            "/api/quotes",
            headers={"Authorization": f"Bearer {self.sales_a_token}"},
        )
        self.assertEqual(resp_a.status_code, 200)
        data_a = resp_a.json()
        self.assertEqual(data_a["total"], 2)
        self.assertEqual(len(data_a["items"]), 2)
        quote_nos_a = {item["quote_no"] for item in data_a["items"]}
        self.assertEqual(quote_nos_a, {"QT-20260930-0001", "QT-20260930-0002"})

        # 2. 销售 B 查询：只能查到 B 的 1 单
        resp_b = self.client.get(
            "/api/quotes",
            headers={"Authorization": f"Bearer {self.sales_b_token}"},
        )
        self.assertEqual(resp_b.status_code, 200)
        data_b = resp_b.json()
        self.assertEqual(data_b["total"], 1)
        self.assertEqual(data_b["items"][0]["quote_no"], "QT-20260930-0003")

        # 3. 管理员查询：查到全部 3 单
        resp_admin = self.client.get(
            "/api/quotes",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(resp_admin.status_code, 200)
        data_admin = resp_admin.json()
        self.assertEqual(data_admin["total"], 3)

        # 4. 管理员按关键字筛选 "综合门诊"
        resp_kw = self.client.get(
            "/api/quotes?keyword=综合门诊",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(resp_kw.status_code, 200)
        data_kw = resp_kw.json()
        self.assertEqual(data_kw["total"], 1)
        self.assertEqual(data_kw["items"][0]["quote_no"], "QT-20260930-0002")

        # 5. 管理员按 status 筛选 "draft"
        resp_status = self.client.get(
            "/api/quotes?status=draft",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(resp_status.status_code, 200)
        data_status = resp_status.json()
        self.assertEqual(data_status["total"], 2)

    # ---------- 4. 单张报价单明细查询 ----------
    def test_get_quote_by_quote_no(self):
        """测试根据 quote_no 调取单张报价单明细快照。"""
        with self.Session() as db:
            q = Quote(
                quote_no="QT-20260930-9999",
                user_id=self.sales_user_a.id,
                sales_name=self.sales_user_a.real_name,
                customer_name="专科检验中心",
                total_list_price=5000.0,
                final_quote_price=4500.0,
                items_snapshot=[
                    {"sku_id": "HW-001", "name": "智能工作站终端", "price": 4500.0, "quantity": 1}
                ],
            )
            db.add(q)
            db.commit()

        # 销售 A 查询详情成功
        resp = self.client.get(
            "/api/quotes/QT-20260930-9999",
            headers={"Authorization": f"Bearer {self.sales_a_token}"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["quote_no"], "QT-20260930-9999")
        self.assertEqual(data["customer_name"], "专科检验中心")
        self.assertEqual(len(data["items_snapshot"]), 1)
        self.assertEqual(data["items_snapshot"][0]["sku_id"], "HW-001")

        # 不存在的 quote_no 返回 404
        resp_404 = self.client.get(
            "/api/quotes/QT-NOT-EXIST",
            headers={"Authorization": f"Bearer {self.sales_a_token}"},
        )
        self.assertEqual(resp_404.status_code, 404)

    def test_unauthenticated_quote_access(self):
        """未携带 Token 访问报价单列表应返回 401 Unauthorized。"""
        resp = self.client.get("/api/quotes")
        self.assertEqual(resp.status_code, 401)

    def test_unauthenticated_quote_detail(self):
        """未携带 Token 访问单张报价单详情应返回 401 Unauthorized。"""
        resp = self.client.get("/api/quotes/QT-20260930-0001")
        self.assertEqual(resp.status_code, 401)

    def test_cross_sales_quote_detail_forbidden(self):
        """销售人员 B 访问销售人员 A 的报价单明细应返回 403 Forbidden。"""
        with self.Session() as db:
            q = Quote(
                quote_no="QT-20260930-7777",
                user_id=self.sales_user_a.id,
                sales_name=self.sales_user_a.real_name,
                customer_name="销售A独占客户",
                total_list_price=8000.0,
                final_quote_price=7500.0,
                items_snapshot=[],
            )
            db.add(q)
            db.commit()

        # 销售 B 访问应该被拒绝 (403)
        resp = self.client.get(
            "/api/quotes/QT-20260930-7777",
            headers={"Authorization": f"Bearer {self.sales_b_token}"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("无权查看", resp.json().get("detail", ""))

        # 销售 A 自身访问成功 (200)
        resp_a = self.client.get(
            "/api/quotes/QT-20260930-7777",
            headers={"Authorization": f"Bearer {self.sales_a_token}"},
        )
        self.assertEqual(resp_a.status_code, 200)

    def test_create_quote_empty_customer_name_validation(self):
        """创建报价单时客户名称为空应触发 422 校验失败。"""
        payload = {
            "customer_name": "",
            "final_quote_price": 100.0,
            "items_snapshot": [],
        }
        resp = self.client.post(
            "/api/quotes",
            json=payload,
            headers={"Authorization": f"Bearer {self.sales_a_token}"},
        )
        self.assertEqual(resp.status_code, 422)

    # ---------- 5. 员工管理 API ----------

    def test_employee_management_crud(self):
        """管理员创建员工账号与分页查询，验证密码安全脱敏。"""
        # 1. 非管理员访问应该被禁止 (403)
        resp_forbidden = self.client.get(
            "/api/admin/employees",
            headers={"Authorization": f"Bearer {self.sales_a_token}"},
        )
        self.assertEqual(resp_forbidden.status_code, 403)

        # 2. 管理员创建新销售员工
        new_emp = {
            "username": "sales_c",
            "password": "password123",
            "real_name": "销售员C",
            "phone": "13800000003",
            "role": "sales",
            "is_active": True,
        }
        resp_create = self.client.post(
            "/api/admin/employees",
            json=new_emp,
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(resp_create.status_code, 201)
        created_data = resp_create.json()
        self.assertEqual(created_data["username"], "sales_c")
        self.assertEqual(created_data["real_name"], "销售员C")
        self.assertEqual(created_data["phone"], "13800000003")
        self.assertEqual(created_data["role"], "sales")
        # 严格检查：不可暴露 password_hash 和 salt
        self.assertNotIn("password_hash", created_data)
        self.assertNotIn("salt", created_data)

        # 3. 重复用户名创建返回 400 或 409
        resp_dup = self.client.post(
            "/api/admin/employees",
            json=new_emp,
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertIn(resp_dup.status_code, (400, 409))

        # 4. 管理员获取员工列表
        resp_list = self.client.get(
            "/api/admin/employees",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(resp_list.status_code, 200)
        list_data = resp_list.json()
        self.assertGreaterEqual(list_data["total"], 4)  # admin + sales_a + sales_b + sales_c
        usernames = [u["username"] for u in list_data["items"]]
        self.assertIn("sales_c", usernames)
        for emp in list_data["items"]:
            self.assertNotIn("password_hash", emp)
            self.assertNotIn("salt", emp)

    def test_prevent_deactivating_reserved_admin(self):
        """更新员工信息时尝试停用内置 admin 应急账号应返回 400。"""
        resp = self.client.put(
            f"/api/admin/employees/{self.admin_user.id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("内置应急管理员账号不可停用", resp.json().get("detail", ""))

    # ---------- 6. /api/catalog Redis 缓存与通用类目 ----------

    def test_catalog_endpoint_with_generic_categories(self):
        """测试 /api/catalog 包含所有类目产品，支持 Redis 缓存命中与失效。"""
        resp = self.client.get("/api/catalog")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        product_skus = {p["sku"] for p in data["products"]}
        # 应包含硬件、服务、耗材
        self.assertIn("HW-001", product_skus)
        self.assertIn("SVC-001", product_skus)
        self.assertIn("CSM-001", product_skus)

    def test_catalog_redis_caching_and_invalidation(self):
        """测试 Redis 缓存读写与主动失效。"""
        mock_cache_store = {}

        fake_redis = AsyncMock()

        async def _get(key):
            return mock_cache_store.get(key)

        async def _set(key, val, ex=None):
            mock_cache_store[key] = val

        async def _delete(key):
            mock_cache_store.pop(key, None)

        fake_redis.get = AsyncMock(side_effect=_get)
        fake_redis.set = AsyncMock(side_effect=_set)
        fake_redis.delete = AsyncMock(side_effect=_delete)

        with patch("app.services.catalog_service.get_redis", return_value=fake_redis):
            with self.Session() as db:
                # 第一次读取：写缓存
                c1 = asyncio.run(get_cached_catalog(db))
                self.assertIn(CATALOG_CACHE_KEY, mock_cache_store)
                self.assertEqual(len(c1["products"]), 3)

                # 手动修改缓存数据以测试缓存命中
                cached_obj = json.loads(mock_cache_store[CATALOG_CACHE_KEY])
                cached_obj["test_flag"] = "cached_hit"
                mock_cache_store[CATALOG_CACHE_KEY] = json.dumps(cached_obj)

                # 第二次读取：应当直接从 Redis 缓存中获取
                c2 = asyncio.run(get_cached_catalog(db))
                self.assertEqual(c2.get("test_flag"), "cached_hit")

                # 调用主动失效辅助函数
                asyncio.run(invalidate_catalog_cache())
                self.assertNotIn(CATALOG_CACHE_KEY, mock_cache_store)

                # 失效后再次读取：重新从数据库构建并写回缓存
                c3 = asyncio.run(get_cached_catalog(db))
                self.assertNotIn("test_flag", c3)
                self.assertIn(CATALOG_CACHE_KEY, mock_cache_store)


# Standalone functions for pytest compatibility
def test_pytest_quote_api_flow():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestQuoteAPI)
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    assert result.wasSuccessful()


if __name__ == "__main__":
    unittest.main()
