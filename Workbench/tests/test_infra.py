import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure Workbench directory is in sys.path
workbench_dir = Path(__file__).resolve().parent.parent
if str(workbench_dir) not in sys.path:
    sys.path.insert(0, str(workbench_dir))

from tests import db_support  # noqa: E402,F401  # 统一测试库连接，必须在 app.* 之前导入

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings
from app.core import redis_client


class TestInfra(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # TestClient(app) 会触发 lifespan 建表，先确保测试库存在
        db_support.ensure_test_database()

    def test_health_check_quote_service(self):
        client = TestClient(app)
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("app"), "quote-service")
        self.assertEqual(data.get("version"), "2.0.0")
        self.assertIn("time", data)

    def test_settings_app_name(self):
        settings = get_settings()
        self.assertEqual(settings.app_name, "quote-service")
        self.assertEqual(settings.auth_secret, "quotesys-auth-secret-key")
        self.assertEqual(settings.redis_url, "redis://localhost:6379/0")

    def test_redis_client_graceful_degradation(self):
        asyncio.run(redis_client.close_redis())
        with patch.object(get_settings(), "redis_url", "redis://127.0.0.1:59999/0"):
            client = asyncio.run(redis_client.get_redis())
            self.assertIsNone(client)
        asyncio.run(redis_client.close_redis())


# Standalone functions for pytest compatibility
def test_health_check_quote_service():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["app"] == "quote-service"
    assert "version" in data


def test_settings_app_name():
    settings = get_settings()
    assert settings.app_name == "quote-service"
    assert settings.auth_secret == "quotesys-auth-secret-key"
    assert settings.redis_url == "redis://localhost:6379/0"


def test_redis_graceful_degradation():
    asyncio.run(redis_client.close_redis())
    with patch.object(get_settings(), "redis_url", "redis://127.0.0.1:59999/0"):
        client = asyncio.run(redis_client.get_redis())
        assert client is None
    asyncio.run(redis_client.close_redis())


if __name__ == "__main__":
    unittest.main()
