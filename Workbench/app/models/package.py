"""套餐模型。

兼容旧版字段与新版通用属性：
- package_code <-> package_id
- description <-> note
- bundle_price <-> std_price
- items_config (JSON/Text 存储配置)
- is_active (是否启用)
"""
from typing import Any

from sqlalchemy import Boolean, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, synonym

from app.db.base import Base, now_str


class Package(Base):
    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    sku_ids: Mapped[str | None] = mapped_column(String, nullable=True, default="[]")
    quantities: Mapped[str | None] = mapped_column(String, nullable=True, default="[]")
    std_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_rate: Mapped[str | None] = mapped_column(String, nullable=True)
    device_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consumable_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consumable_boxes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fixed_bundle: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    device_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    items_config: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str)
    updated_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str, onupdate=now_str)

    # 同义词别名映射，实现双向字段访问与查询支持
    package_code = synonym("package_id")
    description = synonym("note")
    bundle_price = synonym("std_price")
