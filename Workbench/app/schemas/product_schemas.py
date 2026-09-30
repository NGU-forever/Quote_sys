"""通用商品 Pydantic 数据模式。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    sku_id: Optional[str] = Field(None, description="SKU 编码")
    category: str = Field(..., description="通用类目：hardware, software, consumable, service, accessory 等")
    name: str = Field(..., description="商品名称")
    unit: Optional[str] = Field(None, description="计量单位")
    min_price: Optional[float] = Field(None, description="最低限价/指导单价")
    max_price: Optional[float] = Field(None, description="最高限价/官方目录价")
    spec: Optional[str] = Field(None, description="规格型号/技术参数")
    raw_price_desc: Optional[str] = Field(None, description="价格说明/计价方式")
    image: Optional[str] = Field(None, description="商品图片 URL")
    is_active: bool = Field(True, description="是否在售/启用")

    # 兼容历史医用字段
    pieces_per_unit: Optional[int] = None
    units_per_box: Optional[int] = None
    box_price: Optional[float] = None
    applicable_devices: Optional[str] = None
    remark: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    sku_id: Optional[str] = None
    category: Optional[str] = None
    name: Optional[str] = None
    unit: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    spec: Optional[str] = None
    raw_price_desc: Optional[str] = None
    image: Optional[str] = None
    is_active: Optional[bool] = None
    pieces_per_unit: Optional[int] = None
    units_per_box: Optional[int] = None
    box_price: Optional[float] = None
    applicable_devices: Optional[str] = None
    remark: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class ProductOut(ProductBase):
    id: int
    created_at: str
    updated_at: str
    bound_consumables: list[str] = Field(default_factory=list)
    bound_devices: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, extra="allow")


class ProductListResponse(BaseModel):
    total: int
    items: list[ProductOut]

    model_config = ConfigDict(from_attributes=True)
