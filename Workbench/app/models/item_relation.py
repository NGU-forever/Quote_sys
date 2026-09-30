"""商品关联关系模型（配套推荐、配件、服务等）。"""
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, now_str
from app.models.product import Product


class ItemRelation(Base):
    __tablename__ = "item_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), index=True, nullable=False
    )
    child_product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), index=True, nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String, nullable=False, default="accessory")
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str)

    parent_product: Mapped[Product] = relationship("Product", foreign_keys=[parent_product_id])
    child_product: Mapped[Product] = relationship("Product", foreign_keys=[child_product_id])
