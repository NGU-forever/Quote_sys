"""现有 products 表模型（= 商品表：设备 + 耗材统一一张表，用 category 区分）。

字段与数据库完全一致：没有成本价(cost)、库存(stock)等字段，按实际字段建模。
"""
from sqlalchemy import CheckConstraint, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, now_str


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("category IN ('device', 'consumable')", name="products_category_check"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    min_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    pieces_per_unit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    units_per_box: Mapped[int | None] = mapped_column(Integer, nullable=True)
    box_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    applicable_devices: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_price_desc: Mapped[str | None] = mapped_column(String, nullable=True)
    remark: Mapped[str | None] = mapped_column(String, nullable=True)
    image: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str)
    updated_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str, onupdate=now_str)
