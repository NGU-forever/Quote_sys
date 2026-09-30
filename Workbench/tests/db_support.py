"""测试数据库支撑（PostgreSQL 专用）。

约定：
1. 测试只连 PostgreSQL，连接串来自 ``TEST_DATABASE_URL``；未设置时使用
   ``postgresql+psycopg://quotesys_user:quotesys_secret@127.0.0.1:5432/quotesys_test``
   （与仓库根目录 docker-compose.yml 的 postgres 服务一致）；
2. 测试库不存在时自动在目标实例上执行 ``CREATE DATABASE``（连维护库 postgres）；
3. 导入本模块会把 ``DATABASE_URL`` 强制指向测试库，保证测试永远不会误删开发/生产库。
   本模块刻意不在导入期 import 任何 ``app.*``：``app.core.config.settings`` 是模块级
   单例，过早导入会把 ASSETS_DIR / LLM_PROVIDER 等测试环境变量冻结在默认值上；
4. 测试库被所有测试模块共享，因此每个用到数据库的用例都必须显式
   ``reset_schema()``，不要依赖上一个用例留下的数据。

本机准备 PostgreSQL：
    docker compose up -d postgres
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://quotesys_user:quotesys_secret@127.0.0.1:5432/quotesys_test"
)

# 必须在任何 app.* 导入之前生效（settings 为模块级单例）。
# 使用 TEST_DATABASE_URL 可覆盖；绝不会读取 .env 里的 DATABASE_URL。
os.environ["DATABASE_URL"] = (
    os.environ.get("TEST_DATABASE_URL") or DEFAULT_TEST_DATABASE_URL
)


def test_database_url() -> str:
    """返回测试库连接串（TEST_DATABASE_URL 优先）。"""
    return os.environ.get("TEST_DATABASE_URL") or DEFAULT_TEST_DATABASE_URL


def _libpq_url(url_str: str, database: str | None = None) -> str:
    """把 SQLAlchemy 连接串转成 psycopg/libpq 可用形式（去掉 +psycopg 后缀）。"""
    url = make_url(url_str)
    if database is not None:
        url = url.set(database=database)
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def ensure_test_database() -> None:
    """确保测试库存在；不存在则创建。连接失败时给出可执行的排障提示。"""
    import psycopg

    target = make_url(test_database_url()).database
    if not target:
        raise RuntimeError(f"TEST_DATABASE_URL 缺少数据库名：{test_database_url()}")

    try:
        with psycopg.connect(_libpq_url(test_database_url()), connect_timeout=5):
            return
    except psycopg.OperationalError as exc:
        message = str(exc)
        if "does not exist" not in message:
            raise RuntimeError(
                f"无法连接测试库 {target}：{message}\n"
                "请先启动 PostgreSQL：docker compose up -d postgres"
            ) from exc

    with psycopg.connect(
        _libpq_url(test_database_url(), database="postgres"),
        autocommit=True,
        connect_timeout=5,
    ) as conn:
        conn.execute(f'CREATE DATABASE "{target}"')


def create_test_engine() -> Engine:
    """创建指向测试库的 Engine（测试库不存在时自动创建）。"""
    ensure_test_database()
    return create_engine(test_database_url(), pool_pre_ping=True, future=True)


def _metadata():
    """延迟导入，确保 Base.metadata 已注册全部模型。"""
    from app.db.base import Base
    import app.models  # noqa: F401

    return Base.metadata


def reset_schema(engine: Engine) -> None:
    """清空并重建全部表：共享测试库下每个用例开始前都要调用。

    使用 app.db.base 的全局 engine 时也走这里，因此必须顺带确保测试库存在
    （数据库可能尚未被 create_test_engine 创建过）。
    """
    ensure_test_database()
    metadata = _metadata()
    metadata.drop_all(bind=engine)
    metadata.create_all(bind=engine)


def make_session(engine: Engine):
    """基于给定 Engine 创建 Session（供节点级测试直接使用）。"""
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
