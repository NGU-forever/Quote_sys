"""现有 device_bindings 表模型（设备-耗材绑定，复合主键）。"""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, now_str


class DeviceBinding(Base):
    __tablename__ = "device_bindings"

    device_sku_id: Mapped[str] = mapped_column(String, primary_key=True)
    consumable_sku_id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str)
