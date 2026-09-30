"""Offline LangGraph configuration and PostgreSQL checkpoint lifecycle."""
import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.engine import make_url

from app.core.config import settings


def init_offline_env() -> None:
    """Disable LangSmith/LangChain telemetry before importing LangGraph."""
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"


init_offline_env()

from langgraph.checkpoint.postgres import PostgresSaver  # noqa: E402


def checkpoint_conn_string() -> str:
    """Return a libpq connection string for LangGraph's Postgres checkpointer.

    LangGraph 使用 psycopg 直连，不接受 SQLAlchemy 的 ``+psycopg`` 驱动后缀，
    因此这里把 ``postgresql+psycopg://`` 规范化成 ``postgresql://``。
    """
    url = make_url(settings.database_url)
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


@contextmanager
def get_checkpointer() -> Iterator[PostgresSaver]:
    """Open a short-lived PostgreSQL checkpointer owned by the current run.

    ``setup()`` 会幂等地创建 checkpoint 元数据表（langgraph 迁移表控制），
    首次运行后为无操作。
    """
    init_offline_env()
    with PostgresSaver.from_conn_string(checkpoint_conn_string()) as checkpointer:
        checkpointer.setup()
        yield checkpointer
