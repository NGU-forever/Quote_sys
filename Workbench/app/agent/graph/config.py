"""Offline LangGraph configuration and local SQLite checkpoint lifecycle."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core.config import settings


def init_offline_env() -> None:
    """Disable LangSmith/LangChain telemetry before importing LangGraph."""
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"


init_offline_env()

from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: E402


def checkpoint_db_path() -> Path:
    """Return the checkpoint file beside the configured SQLite database."""
    prefix = "sqlite:///"
    if settings.database_url.startswith(prefix):
        raw = settings.database_url[len(prefix) :]
        if raw and raw != ":memory:":
            return Path(raw).resolve().parent / "agent_checkpoints.db"
    return Path("data/agent_checkpoints.db").resolve()


@contextmanager
def get_checkpointer() -> Iterator[SqliteSaver]:
    """Open a short-lived SQLite checkpointer owned by the current run."""
    init_offline_env()
    db_path = checkpoint_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path), check_same_thread=False)
    try:
        yield SqliteSaver(connection)
    finally:
        connection.close()
