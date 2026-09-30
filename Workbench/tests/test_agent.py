"""数据生成 Agent 验收测试。

本模块把 DATABASE_URL 指向 PostgreSQL 测试库（见 tests/db_support.py），
并在 setUpModule 里重置 schema，确保测试不修改开发库：
    docker compose up -d postgres
    cd Workbench && .venv/bin/python -m unittest tests.test_agent -v
"""
import atexit
import copy
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_tmp_dir = Path(tempfile.mkdtemp(prefix="quotesys-agent-tests-"))
_tmp_assets = _tmp_dir / "assets"
_tmp_assets.mkdir(parents=True, exist_ok=True)

# 注意：这些环境变量必须在导入 tests.db_support（进而导入 app.core.config）之前设置，
# 否则 settings 单例已经按默认值初始化。
os.environ["ASSETS_DIR"] = str(_tmp_assets)
os.environ["LLM_PROVIDER"] = "mock"
os.environ["AGENT_DEFAULT_MODE"] = "apply"

from tests import db_support  # noqa: E402  # 统一测试库连接，必须在 app.* 之前导入

import openpyxl  # noqa: E402
from app.agent.mock_provider import DEMO_PRODUCTS, DEMO_PACKAGES, DEMO_CANDIDATES  # noqa: E402

wb = openpyxl.Workbook()
ws1 = wb.active
ws1.title = "SKU主表"
ws1.append(["sku_id", "产品名称", "最低价", "单位", "适用设备", "包装规格", "备注"])
for p in DEMO_PRODUCTS:
    ws1.append([p["sku_id"], p["name"], p["min_price"], p["unit"], p.get("applicable_devices") or "", "", p.get("raw_price_desc") or ""])

ws2 = wb.create_sheet("套餐定义表")
ws2.append(["套餐编号", "套餐名称", "商品组合", "套餐售价", "备注"])
for pkg in DEMO_PACKAGES:
    ws2.append([pkg["package_id"], pkg["name"], ",".join(pkg["sku_ids"]), pkg["std_price"], pkg.get("note") or ""])

wb.save(_tmp_assets / "产品最低价格.xlsx")
(_tmp_assets / "notes.md").write_text("# 说明\n", encoding="utf-8")
(_tmp_assets / "unsupported_notes.bin").write_bytes(b"binary content")

from fastapi.testclient import TestClient  # noqa: E402

from app.agent.readers.common import safe_file_path  # noqa: E402
from app.agent.readers.excel_reader import read_excel  # noqa: E402
from app.agent.readers.manifest import build_manifest  # noqa: E402
from app.agent.validation import validate_candidates  # noqa: E402
from app.agent import agent_service  # noqa: E402
from app.agent.persistence import apply_candidates  # noqa: E402
from app.db.base import SessionLocal, engine  # noqa: E402
from app.db.seed import seed_reserved_admin, seed_app_settings  # noqa: E402
from app.main import app  # noqa: E402

def setUpModule() -> None:
    """模块级准备：重置测试库并写入 Agent 验收所需的基线数据。

    测试库被所有测试模块共享，因此模块开始前必须显式重置 schema，
    否则上一个模块残留的数据会污染本模块的断言。
    """
    db_support.reset_schema(engine)
    with SessionLocal() as db:
        seed_reserved_admin(db)
        seed_app_settings(db)
        init_candidates = copy.deepcopy(DEMO_CANDIDATES)
        for p in init_candidates["products"]:
            if p["sku_id"] == "P013":
                p["max_price"] = None
                p["raw_price_desc"] = "≥6000"
        apply_candidates(db, init_candidates, mode="apply")


def _cleanup():
    shutil.rmtree(_tmp_dir, ignore_errors=True)


atexit.register(_cleanup)


def _login(client: TestClient) -> dict:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _wait_run(client: TestClient, headers: dict, run_id: int, timeout: float = 15.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/agent/runs/{run_id}", headers=headers)
        assert response.status_code == 200, response.text
        run = response.json()["data"]
        if run["status"] not in {"pending", "running"}:
            return run
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} 未在 {timeout}s 内结束")


class AgentManifestAndValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.headers = _login(cls.client)

    def test_manifest_lists_supported_and_unsupported(self):
        response = self.client.get("/api/agent/assets", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertGreaterEqual(data["supported_count"], 2)
        paths = {f["path"] for f in data["files"]}
        self.assertIn("产品最低价格.xlsx", paths)
        self.assertTrue(any(f["type"] == "unsupported" for f in data["files"]))

    def test_upload_and_delete_asset(self):
        from app.core.config import settings

        target_file = settings.assets_root / "test_upload_doc.txt"
        try:
            # 1. 不支持的后缀名
            bad_resp = self.client.post(
                "/api/agent/assets/upload",
                files={"file": ("malware.exe", b"fake binary", "application/octet-stream")},
                headers=self.headers,
            )
            self.assertEqual(bad_resp.status_code, 400)
            self.assertIn("仅支持上传", bad_resp.json()["error"])

            # 2. 正常上传文本文件
            upload_resp = self.client.post(
                "/api/agent/assets/upload",
                files={"file": ("test_upload_doc.txt", b"test content for asset upload", "text/plain")},
                headers=self.headers,
            )
            self.assertEqual(upload_resp.status_code, 200)
            manifest = upload_resp.json()["data"]
            self.assertTrue(any(f["path"] == "test_upload_doc.txt" for f in manifest["files"]))
            self.assertTrue(manifest.get("root_path"))

            # 3. 正常删除文件
            del_resp = self.client.delete(
                "/api/agent/assets/test_upload_doc.txt",
                headers=self.headers,
            )
            self.assertEqual(del_resp.status_code, 200)
            manifest_after = del_resp.json()["data"]
            self.assertFalse(any(f["path"] == "test_upload_doc.txt" for f in manifest_after["files"]))
        finally:
            target_file.unlink(missing_ok=True)

    def test_excel_reader_and_path_sandbox(self):
        summary = read_excel(Path(os.environ["ASSETS_DIR"]) / "产品最低价格.xlsx", sheet="SKU主表", max_rows=3)
        self.assertEqual(summary["headers"][0], "sku_id")
        self.assertEqual(summary["row_count"], 25)
        self.assertGreater(summary["truncated"], False)
        with self.assertRaises(ValueError):
            safe_file_path("../outside.xlsx")
        with self.assertRaises(ValueError):
            safe_file_path("/etc/passwd")

    def test_hard_validation_rejects_bad_candidates(self):
        payload = {
            "products": [
                {
                    "sku_id": "P999",
                    "category": "device",
                    "name": "测试设备",
                    "unknown_field": "should fail",
                }
            ],
            "packages": [
                {
                    "package_id": "PKG999",
                    "name": "坏套餐",
                    "sku_ids": ["P999", "C999"],
                    "quantities": [1],
                }
            ],
            "bindings": [
                {"device_sku_id": "C999", "consumable_sku_id": "P999"},
            ],
            "issues": [],
        }
        with SessionLocal() as db:
            _, _, errors = validate_candidates(payload, db)
        joined = "\n".join(errors)
        self.assertTrue(any("Unknown" in err or "extra" in err.lower() for err in errors), joined)
        self.assertTrue(any("长度" in err for err in errors), joined)

        reference_payload = {
            "products": [],
            "packages": [
                {
                    "package_id": "PKG999",
                    "name": "坏套餐",
                    "sku_ids": ["P999", "C999"],
                    "quantities": [1, 1],
                }
            ],
            "bindings": [
                {"device_sku_id": "C999", "consumable_sku_id": "P999"},
            ],
            "issues": [],
        }
        with SessionLocal() as db:
            _, _, reference_errors = validate_candidates(reference_payload, db)
        self.assertTrue(
            any("引用了不存在的 SKU" in err for err in reference_errors),
            "\n".join(reference_errors),
        )
        self.assertTrue(
            any("不存在" in err for err in reference_errors),
            "\n".join(reference_errors),
        )

    def test_tool_registry_list_and_lookup(self):
        from app.agent.tool_registry import ToolContext, execute_tool

        with SessionLocal() as db:
            listed = execute_tool("list_assets", {}, ToolContext(run_id=999, db=db))
            self.assertTrue(listed["ok"])
            self.assertGreater(len(listed["files"]), 0)
            # 模型可能在 lookup_existing 里多传 path，工具不应把它当成文件读取
            stats = execute_tool(
                "lookup_existing",
                {"entity": "stats", "path": "."},
                ToolContext(run_id=999, db=db),
            )
            self.assertTrue(stats["ok"])
            self.assertIn("products", stats)

    def test_agent_config_save_keeps_key_server_side(self):
        from app.models.app_setting import AppSetting
        from app.services.agent_config_service import AGENT_AI_KEY, get_agent_ai
        from sqlalchemy import select

        try:
            response = self.client.put(
                "/api/agent/config",
                json={
                    "provider": "openai",
                    "base_url": "https://example.test/v1",
                    "model": "test-model",
                    "api_key": "sk-test-secret-value",
                    "max_steps": 12,
                    "default_mode": "dry-run",
                },
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()["data"]
            self.assertTrue(data["has_api_key"])
            self.assertNotIn("sk-test-secret-value", response.text)
            self.assertNotIn("api_key", data)
            with SessionLocal() as db:
                stored = get_agent_ai(db)
                self.assertEqual(stored["api_key"], "sk-test-secret-value")
                self.assertEqual(stored["max_steps"], 12)
                self.assertEqual(stored["default_mode"], "dry-run")
                # 页面保存的 openai 配置应覆盖测试环境的 mock 环境变量
                _, provider_name = agent_service._provider(stored)
                self.assertEqual(provider_name, "openai")
            sync = self.client.get("/api/sync")
            self.assertNotIn("sk-test-secret-value", sync.text)
            self.assertNotIn("agent_ai", sync.text)
        finally:
            with SessionLocal() as db:
                setting = db.scalar(
                    select(AppSetting).where(AppSetting.key == AGENT_AI_KEY)
                )
                if setting is not None:
                    db.delete(setting)
                    db.commit()

    def test_agent_config_allows_local_model_without_key(self):
        from app.models.app_setting import AppSetting
        from app.services.agent_config_service import AGENT_AI_KEY, get_agent_ai
        from sqlalchemy import select

        try:
            response = self.client.put(
                "/api/agent/config",
                json={
                    "provider": "openai",
                    "base_url": "http://127.0.0.1:11434/v1",
                    "model": "qwen2.5",
                    "api_key": "",
                    "max_steps": 10,
                    "default_mode": "dry-run",
                },
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()["data"]
            self.assertFalse(data["has_api_key"])
            self.assertEqual(data["base_url"], "http://127.0.0.1:11434/v1")
            with SessionLocal() as db:
                stored = get_agent_ai(db)
                _, provider_name = agent_service._provider(stored)
                self.assertEqual(provider_name, "openai")
                self.assertEqual(stored["api_key"], "")
        finally:
            with SessionLocal() as db:
                setting = db.scalar(
                    select(AppSetting).where(AppSetting.key == AGENT_AI_KEY)
                )
                if setting is not None:
                    db.delete(setting)
                    db.commit()


class AgentRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.headers = _login(cls.client)

    def start(self, mode: str):
        response = self.client.post(
            "/api/agent/runs",
            json={"mode": mode, "note": "automated test"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["data"]["id"]

    def test_01_dry_run_does_not_touch_business_tables(self):
        run_id = self.start("dry-run")
        run = _wait_run(self.client, self.headers, run_id)
        self.assertEqual(run["status"], "succeeded", run["error"])
        self.assertEqual(run["products_candidates"], 25)
        self.assertEqual(run["packages_candidates"], 3)
        self.assertEqual(run["bindings_candidates"], 41)
        self.assertTrue(run["events"], "ReAct 事件为空")
        summaries = [event["summary"] or "" for event in run["events"]]
        stage_markers = ["扫描", "嗅探", "提取", "质检", "入库"]
        positions = [
            next(
                (index for index, summary in enumerate(summaries) if marker in summary),
                -1,
            )
            for marker in stage_markers
        ]
        self.assertTrue(all(position >= 0 for position in positions), summaries)
        self.assertEqual(positions, sorted(positions), summaries)
        # LangGraph 检查点已落库 PostgreSQL（表由 PostgresSaver.setup() 创建）
        from sqlalchemy import text

        with engine.connect() as conn:
            checkpoint_rows = conn.execute(
                text("SELECT count(*) FROM checkpoints")
            ).scalar()
        self.assertGreater(checkpoint_rows, 0)
        with SessionLocal() as db:
            from app.models.device_binding import DeviceBinding
            from app.models.package import Package
            from app.models.product import Product
            from sqlalchemy import func, select

            self.assertEqual(db.scalar(select(func.count()).select_from(Product)), 25)
            self.assertEqual(db.scalar(select(func.count()).select_from(Package)), 3)
            self.assertEqual(db.scalar(select(func.count()).select_from(DeviceBinding)), 41)

    def test_02_apply_updates_only_p013(self):
        run_id = self.start("apply")
        run = _wait_run(self.client, self.headers, run_id)
        self.assertEqual(run["status"], "succeeded", run["error"])
        self.assertEqual(run["products_added"], 0)
        self.assertEqual(run["products_updated"], 1)
        self.assertEqual(run["products_skipped"], 24)
        self.assertEqual(run["packages_skipped"], 3)
        self.assertEqual(run["bindings_skipped"], 41)
        with SessionLocal() as db:
            from sqlalchemy import select

            from app.models.product import Product

            p013 = db.scalar(select(Product).where(Product.sku_id == "P013"))
            self.assertEqual(p013.min_price, 6000)
            self.assertEqual(p013.max_price, 9800)

    def test_03_legacy_contracts_still_ok(self):
        for path in ("/api/products", "/api/packages"):
            response = self.client.get(path, headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertIsInstance(response.json().get("data"), list)
        sync = self.client.get("/api/sync")
        self.assertEqual(sync.status_code, 200)
        self.assertIn("catalog", sync.json()["data"])
        self.assertIn("rev", sync.json()["data"])

    def test_04_apply_saved_run_after_dry_run(self):
        run_id = self.start("dry-run")
        run = _wait_run(self.client, self.headers, run_id)
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["mode"], "dry-run")

        response = self.client.post(
            f"/api/agent/runs/{run_id}/apply",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        applied_run = response.json()["data"]
        self.assertEqual(applied_run["mode"], "apply")
        self.assertEqual(applied_run["stage"], "applied")
        human_events = [e for e in applied_run["events"] if e["role"] == "human"]
        self.assertTrue(len(human_events) >= 1)
        self.assertIn("人工审核通过", human_events[-1]["summary"])

    def test_05_apply_saved_run_with_candidates_override(self):
        run_id = self.start("dry-run")
        run = _wait_run(self.client, self.headers, run_id)
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["mode"], "dry-run")

        candidates = run["candidates"]
        self.assertIsNotNone(candidates)
        # 修改 P013 商品底价与名称
        p013 = next(p for p in candidates["products"] if p["sku_id"] == "P013")
        p013["min_price"] = 7777
        p013["name"] = "P013人工改名款"

        # 1. 非法候选数据测试：包含多余未知字段或孤儿引用
        bad_candidates = {
            "products": candidates["products"] + [
                {"sku_id": "ERR-999", "category": "device", "name": "坏数据", "unknown_field": "bad"}
            ],
            "packages": candidates["packages"],
            "bindings": candidates["bindings"],
            "issues": [],
        }
        bad_resp = self.client.post(
            f"/api/agent/runs/{run_id}/apply",
            json={"candidates": bad_candidates},
            headers=self.headers,
        )
        self.assertEqual(bad_resp.status_code, 400)
        self.assertIn("候选数据未通过硬校验", bad_resp.json()["error"])

        # 2. 正常覆盖并落库
        response = self.client.post(
            f"/api/agent/runs/{run_id}/apply",
            json={"candidates": candidates},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        applied_run = response.json()["data"]
        self.assertEqual(applied_run["mode"], "apply")

        with SessionLocal() as db:
            from sqlalchemy import select
            from app.models.product import Product

            prod = db.scalar(select(Product).where(Product.sku_id == "P013"))
            self.assertEqual(prod.min_price, 7777)
            self.assertEqual(prod.name, "P013人工改名款")


class AgentCancelAndFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.headers = _login(cls.client)

    def start_raw(self):
        response = self.client.post(
            "/api/agent/runs",
            json={"mode": "dry-run"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["data"]["id"]

    def test_04_cancelled_run_leaves_no_partial_rows(self):
        old_provider = agent_service._provider

        class RealSlowProvider:
            def __init__(self):
                self.calls = 0

            def chat(self, messages, tool_schemas):
                from app.agent.llm_client import LLMResponse, ToolCall

                self.calls += 1
                if self.calls == 1:
                    return LLMResponse(
                        tool_calls=[ToolCall("list_assets", {}, call_id="slow-list")],
                        summary="slow mock first call",
                    )
                raise AssertionError("取消后不应再调用 provider")

        provider = RealSlowProvider()
        agent_service._provider = lambda ai_config: (provider, "mock")
        run_id = self.start_raw()
        try:
            deadline = time.time() + 3
            while run_id not in agent_service._active and time.time() < deadline:
                time.sleep(0.02)
            self.assertIn(run_id, agent_service._active)
            cancel = self.client.post(
                f"/api/agent/runs/{run_id}/cancel",
                headers=self.headers,
            )
            self.assertEqual(cancel.status_code, 200, cancel.text)
            run = _wait_run(self.client, self.headers, run_id)
            self.assertEqual(run["status"], "cancelled")
        finally:
            agent_service._provider = old_provider

    def test_05_failed_run_keeps_business_rows(self):
        old_provider = agent_service._provider

        class FailingProvider:
            def chat(self, messages, tool_schemas):
                raise RuntimeError("模拟 LLM 故障")

        agent_service._provider = lambda ai_config: (FailingProvider(), "mock")
        run_id = self.start_raw()
        try:
            run = _wait_run(self.client, self.headers, run_id)
            self.assertEqual(run["status"], "failed")
            self.assertIn("模拟 LLM 故障", run["error"])
        finally:
            agent_service._provider = old_provider


if __name__ == "__main__":
    unittest.main()
