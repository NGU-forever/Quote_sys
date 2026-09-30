"""现有 users 表模型（字段与 Node 后端建表语句完全一致，不修改表结构）。"""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, now_str


# 内置应急管理员账号名：登录页不展示、普通注册不可占用。
RESERVED_ADMIN_USERNAME = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    salt: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str)
