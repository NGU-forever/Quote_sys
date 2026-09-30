"""数据库连接与 ORM 基础类。

- 仅使用 PostgreSQL（DATABASE_URL 为 postgresql+psycopg:// 连接串）。
- 不修改现有表：Base.metadata.create_all 仅在表缺失时创建（checkfirst=True），
  已存在的 users / products / packages / device_bindings 保持原样。
"""
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


def now_str() -> str:
    """返回本地时间字符串，作为各表 created_at / updated_at 的统一格式。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


engine = create_engine(
    settings.database_url,
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
