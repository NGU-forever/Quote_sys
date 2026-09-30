"""LangGraph 离线配置与 PostgreSQL checkpoint 测试。"""
import os
import unittest

from tests import db_support  # noqa: F401  # 统一测试库连接，必须在 app.* 之前导入

from sqlalchemy import text

from app.core.config import settings


class AgentGraphEnvironmentTests(unittest.TestCase):
    def test_offline_environment_disables_telemetry(self):
        from app.agent.graph.config import init_offline_env

        init_offline_env()

        self.assertEqual(os.environ.get("LANGSMITH_TRACING"), "false")
        self.assertEqual(os.environ.get("LANGCHAIN_TRACING_V2"), "false")

    def test_checkpoint_conn_string_normalizes_driver(self):
        from app.agent.graph.config import checkpoint_conn_string

        previous = settings.database_url
        try:
            settings.database_url = (
                "postgresql+psycopg://u:p@db.example:5433/quotesys?sslmode=disable"
            )
            conn_string = checkpoint_conn_string()
        finally:
            settings.database_url = previous

        self.assertTrue(conn_string.startswith("postgresql://"))
        self.assertNotIn("+psycopg", conn_string)
        self.assertIn("db.example:5433/quotesys", conn_string)
        self.assertIn("sslmode=disable", conn_string)

    def test_checkpointer_setup_creates_tables(self):
        from app.agent.graph.config import get_checkpointer

        engine = db_support.create_test_engine()
        try:
            with get_checkpointer() as checkpointer:
                self.assertIsNotNone(checkpointer)
                checkpointer.setup()  # 幂等：重复 setup 不应报错

            with engine.connect() as conn:
                tables = set(
                    conn.execute(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = current_schema()"
                        )
                    ).scalars()
                )
        finally:
            engine.dispose()

        self.assertIn("checkpoints", tables)
        self.assertIn("checkpoint_writes", tables)


if __name__ == "__main__":
    unittest.main()
