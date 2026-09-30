"""用户与员工表模型。"""
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, now_str


# 内置应急管理员账号名：登录页不展示、普通注册不可占用。
RESERVED_ADMIN_USERNAME = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    salt: Mapped[str] = mapped_column(String, nullable=False)
    real_name: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, nullable=False, default="sales")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str)
    updated_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str, onupdate=now_str)
