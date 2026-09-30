"""数据库连接与 ORM 基础类。

- 默认 SQLite（开发/现有库），通过 DATABASE_URL 可切换到 PostgreSQL。
- 不修改现有表：Base.metadata.create_all 仅在表缺失时创建（checkfirst=True），
  已存在的 users / products / packages / device_bindings 保持原样。
"""
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


def now_str() -> str:
    """返回与现有库 datetime('now','localtime') 一致的本地时间字符串。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# SQLite 需要额外连接参数（FastAPI 依赖注入会在不同线程使用同一连接池）
connect_args: dict = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """所有 ORM 模型的声明式基类。"""


def get_db():
    """FastAPI 依赖：请求级数据库会话，请求结束后自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
