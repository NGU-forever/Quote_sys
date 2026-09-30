"""报价单 Pydantic 数据模式。"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class QuoteItemSnapshot(BaseModel):
    """报价单中固化的商品快照项。"""
    sku_id: str
    name: str
    category: Optional[str] = None
    spec: Optional[str] = None
    unit: Optional[str] = None
    quantity: int = 1
    price: float = 0.0
    subtotal: Optional[float] = None
    remark: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class QuoteCreate(BaseModel):
    """创建报价单请求体。"""
    customer_name: str = Field(..., description="客户单位/名称")
    customer_contact: Optional[str] = Field(None, description="客户联系人")
    customer_phone: Optional[str] = Field(None, description="客户联系电话")
    sales_name: Optional[str] = Field(None, description="销售人员姓名")
    sales_phone: Optional[str] = Field(None, description="销售人员电话")
    status: str = Field("draft", description="状态：draft, submitted, approved, rejected, expired")
    total_list_price: float = Field(0.0, description="目录指导总价")
    discount_rate: Optional[float] = Field(None, description="整体折扣率")
    final_quote_price: float = Field(0.0, description="最终总报价")
    valid_days: int = Field(30, description="报价有效天数")
    remark: Optional[str] = Field(None, description="备注说明")
    items_snapshot: list[Any] = Field(default_factory=list, description="固化商品与套餐明细快照")

    model_config = ConfigDict(extra="allow")


class QuoteOut(BaseModel):
    """报价单详情与响应输出。"""
    id: int
    quote_no: str
    user_id: Optional[int] = None
    sales_name: Optional[str] = None
    sales_phone: Optional[str] = None
    customer_name: str
    customer_contact: Optional[str] = None
    customer_phone: Optional[str] = None
    status: str
    total_list_price: float
    discount_rate: Optional[float] = None
    final_quote_price: float
    valid_days: int
    remark: Optional[str] = None
    items_snapshot: list[Any] = Field(default_factory=list)
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True, extra="allow")


class QuoteListResponse(BaseModel):
    """报价单分页列表响应。"""
    total: int
    page: int
    page_size: int
    items: list[QuoteOut]

    model_config = ConfigDict(from_attributes=True)
