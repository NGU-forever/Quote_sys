"""报价单持久化模型。"""
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, now_str
from app.models.user import User


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quote_no: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    sales_name: Mapped[str | None] = mapped_column(String, nullable=True)
    sales_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_name: Mapped[str] = mapped_column(String, nullable=False)
    customer_contact: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    total_list_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    discount_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_quote_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    valid_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    remark: Mapped[str | None] = mapped_column(String, nullable=True)
    items_snapshot: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str)
    updated_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str, onupdate=now_str)

    user: Mapped[User | None] = relationship("User", foreign_keys=[user_id])
