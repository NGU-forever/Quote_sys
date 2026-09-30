"""数据库初始化与建表脚本。"""
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base, engine as default_engine
from app.db.seed import seed_app_settings, seed_reserved_admin, seed_sample_products
# 导入所有模型以确保注册在 Base.metadata 中
from app.models import *  # noqa: F401,F403


def init_db(engine: Engine | None = None, seed_sample_data: bool = False) -> None:
    """初始化数据库表并执行基础播种。

    :param engine: 可选 SQLAlchemy Engine，缺省使用默认 engine
    :param seed_sample_data: 是否注入通用示例商品与套餐数据
    """
    target_engine = engine or default_engine
    Base.metadata.create_all(bind=target_engine)

    SessionMaker = sessionmaker(bind=target_engine, future=True)
    with SessionMaker() as db:
        seed_reserved_admin(db)
        seed_app_settings(db)
        if seed_sample_data:
            seed_sample_products(db)


if __name__ == "__main__":
    init_db(seed_sample_data=True)
    print("Database initialized successfully with sample data.")
