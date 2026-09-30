"""新增 app_settings 表（key-value，存公司信息与报价参数，只增表不改旧表）。"""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, now_str


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)  # JSON 字符串
    updated_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str, onupdate=now_str)
