"""断点续跑（PostgresSaver checkpoint resume）测试。

验证：节点异常中断后检查点仍保留已完成的状态，用 ``graph.stream(None, ...)``
可以从断点继续，而不是从头重跑。
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import db_support  # noqa: F401  # 统一测试库连接，必须在 app.* 之前导入

from sqlalchemy.orm import sessionmaker

from app.agent.graph.builder import build_import_graph
from app.agent.graph.config import get_checkpointer
from app.agent.graph.runtime import GraphRuntime
from app.agent.mock_provider import DEMO_PACKAGES, DEMO_PRODUCTS, MockProvider
from app.core.config import settings


class FlakyProvider:
    """第 1 次调用抛错（模拟进程/网络中断），之后委托离线 Mock。"""

    def __init__(self):
        self.calls = 0
        self.delegate = MockProvider()

    def chat(self, messages, tool_schemas):
        self.calls += 1
        if self.calls == 1:
            raise ValueError("simulated crash")
        return self.delegate.chat(messages, tool_schemas)


def _write_assets(root: Path) -> None:
    import openpyxl

    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "SKU主表"
    ws1.append(["sku_id", "产品名称", "最低价", "单位", "适用设备", "包装规格", "备注"])
    for product in DEMO_PRODUCTS:
        ws1.append(
            [
                product["sku_id"],
                product["name"],
                product["min_price"],
                product["unit"],
                product.get("applicable_devices") or "",
                "",
                product.get("raw_price_desc") or "",
            ]
        )
    ws2 = wb.create_sheet("套餐定义表")
    ws2.append(["套餐编号", "套餐名称", "商品组合", "套餐售价", "备注"])
    for package in DEMO_PACKAGES:
        ws2.append(
            [
                package["package_id"],
                package["name"],
                ",".join(package["sku_ids"]),
                package["std_price"],
                package.get("note") or "",
            ]
        )
    wb.save(root / "产品最低价格.xlsx")
    (root / "notes.md").write_text("# 兼容说明\nC001 适用于 P001。\n", encoding="utf-8")


def _initial_state() -> dict:
    return {
        "run_id": 1,
        "mode": "dry-run",
        "manifest": {},
        "db_stats": {},
        "sources_plan": {},
        "products_extracted": [],
        "packages_extracted": [],
        "bindings_extracted": [],
        "issues": [],
        "candidates": None,
        "validation_errors": [],
        "retry_count": 0,
        "status": "running",
        "apply_result": {},
        "report": {},
    }


class GraphResumeTests(unittest.TestCase):
    def setUp(self):
        self.engine = db_support.create_test_engine()
        db_support.reset_schema(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)

    def tearDown(self):
        self.engine.dispose()

    def test_resume_after_node_failure_does_not_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_assets(root)
            db = self.Session()
            provider = FlakyProvider()
            runtime = GraphRuntime(
                provider=provider,
                provider_name="mock",
                db=db,
                cancel_check=lambda: False,
                max_steps=5,
            )
            config = {"configurable": {"thread_id": "resume-case-1"}}

            with patch.object(settings, "assets_dir", str(root)):
                with get_checkpointer() as checkpointer:
                    graph = build_import_graph(runtime, checkpointer)

                    with self.assertRaises(RuntimeError) as crashed:
                        for _ in graph.stream(
                            _initial_state(), config=config, stream_mode="updates"
                        ):
                            pass
                    self.assertIn("simulated crash", str(crashed.exception))

                    broken = graph.get_state(config)
                    # 中断时：已完成节点的状态仍在检查点里，且仍有待续跑节点
                    self.assertTrue(broken.values.get("sources_plan"))
                    self.assertTrue(broken.next, "应存在待续跑的节点")

                    for _ in graph.stream(None, config=config, stream_mode="updates"):
                        pass

                    finished = graph.get_state(config)

            try:
                self.assertEqual(finished.values.get("status"), "succeeded")
                self.assertFalse(finished.next, "续跑后不应还有待执行节点")
                self.assertTrue(finished.values.get("products_extracted"))
            finally:
                db.close()

    def test_stream_none_on_completed_thread_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_assets(root)
            db = self.Session()
            runtime = GraphRuntime(
                provider=MockProvider(),
                provider_name="mock",
                db=db,
                cancel_check=lambda: False,
            )
            config = {"configurable": {"thread_id": "resume-case-2"}}
            with patch.object(settings, "assets_dir", str(root)):
                with get_checkpointer() as checkpointer:
                    graph = build_import_graph(runtime, checkpointer)
                    for _ in graph.stream(_initial_state(), config=config, stream_mode="updates"):
                        pass
                    self.assertFalse(graph.get_state(config).next)
                    # 已完成的 thread 再续跑：没有待执行节点，不应产生新的 chunk
                    self.assertEqual(
                        list(graph.stream(None, config=config, stream_mode="updates")), []
                    )
            db.close()


class ResumeServiceTests(unittest.TestCase):
    def test_resume_without_checkpoint_fails_cleanly(self):
        from app.agent import agent_service
        from app.db.base import SessionLocal
        from app.models.import_run import ImportRun

        engine = db_support.create_test_engine()
        db_support.reset_schema(engine)
        engine.dispose()

        with SessionLocal() as db:
            # 用一个不可能与既有 checkpoint 冲突的 run_id（thread_id == str(run_id)）
            run = ImportRun(id=987654321, mode="dry-run", status="failed", stage="failed")
            db.add(run)
            db.commit()
            run_id = run.id

        with patch.object(settings, "llm_provider", "mock"):
            agent_service.execute_run(run_id, resume=True)

        with SessionLocal() as db:
            stored = db.get(ImportRun, run_id)
            self.assertEqual(stored.status, "failed")
            self.assertIn("没有可续跑的检查点", stored.error or "")


class ResumeApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient

        from app.db.seed import seed_reserved_admin
        from app.main import app

        cls.engine = db_support.create_test_engine()
        db_support.reset_schema(cls.engine)
        from app.db.base import SessionLocal

        with SessionLocal() as db:
            seed_reserved_admin(db)

        cls.client = TestClient(app)
        response = cls.client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        assert response.status_code == 200, response.text
        cls.headers = {"Authorization": f"Bearer {response.json()['token']}"}

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def test_resume_unknown_run_returns_404(self):
        response = self.client.post("/api/agent/runs/987654321/resume", headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_resume_running_run_returns_409(self):
        from app.db.base import SessionLocal
        from app.models.import_run import ImportRun

        with SessionLocal() as db:
            run = ImportRun(mode="dry-run", status="running", stage="inventory")
            db.add(run)
            db.commit()
            run_id = run.id

        response = self.client.post(f"/api/agent/runs/{run_id}/resume", headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertIn("仍在运行", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
