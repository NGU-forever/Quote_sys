"""现有 packages 表模型（套餐定义表）。

sku_ids / quantities 为 JSON 数组的文本存储，读取时由业务层 json.loads 解析。
"""
from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, now_str


class Package(Base):
    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    sku_ids: Mapped[str] = mapped_column(String, nullable=False)  # JSON 数组，如 ["P001","C004"]
    quantities: Mapped[str] = mapped_column(String, nullable=False)  # JSON 数组，与 sku_ids 一一对应
    std_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_rate: Mapped[str | None] = mapped_column(String, nullable=True)
    device_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consumable_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consumable_boxes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fixed_bundle: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    device_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str)
    updated_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str, onupdate=now_str)
