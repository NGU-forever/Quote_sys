"""LangGraph 离线配置与 SQLite checkpoint 测试。"""
import os
import tempfile
import unittest
from pathlib import Path

from app.core.config import settings


class AgentGraphEnvironmentTests(unittest.TestCase):
    def test_offline_environment_disables_telemetry(self):
        from app.agent.graph.config import init_offline_env

        init_offline_env()

        self.assertEqual(os.environ.get("LANGSMITH_TRACING"), "false")
        self.assertEqual(os.environ.get("LANGCHAIN_TRACING_V2"), "false")

    def test_checkpoint_path_follows_sqlite_database_directory(self):
        from app.agent.graph.config import checkpoint_db_path

        previous = settings.database_url
        try:
            with tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "workbench.db"
                settings.database_url = f"sqlite:///{db_path}"
                self.assertEqual(
                    checkpoint_db_path(),
                    (db_path.parent / "agent_checkpoints.db").resolve(),
                )
        finally:
            settings.database_url = previous

    def test_checkpointer_initializes_sqlite_file(self):
        from app.agent.graph.config import checkpoint_db_path, get_checkpointer

        previous = settings.database_url
        try:
            with tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "workbench.db"
                settings.database_url = f"sqlite:///{db_path}"
                expected = checkpoint_db_path()
                with get_checkpointer() as checkpointer:
                    self.assertIsNotNone(checkpointer)
                    checkpointer.setup()
                self.assertTrue(expected.is_file())
        finally:
            settings.database_url = previous


if __name__ == "__main__":
    unittest.main()
