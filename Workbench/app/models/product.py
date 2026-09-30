"""通用商品模型。

支持任意通用字符串类目（硬件、耗材、服务、软件、配件等），
保留原有字段以兼容旧版本接口，同时扩展通用规格 (spec) 与启用状态 (is_active)。
"""
from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, now_str


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    min_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    spec: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_price_desc: Mapped[str | None] = mapped_column(String, nullable=True)
    image: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # 兼容字段
    pieces_per_unit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    units_per_box: Mapped[int | None] = mapped_column(Integer, nullable=True)
    box_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    applicable_devices: Mapped[str | None] = mapped_column(String, nullable=True)
    remark: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str)
    updated_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str, onupdate=now_str)
