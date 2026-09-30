"""员工与用户管理 Pydantic 数据模式。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EmployeeCreate(BaseModel):
    """创建员工账号请求体。"""
    username: str = Field(..., min_length=1, max_length=64, description="用户名/工号")
    password: str = Field(..., min_length=6, max_length=128, description="登录密码")
    real_name: Optional[str] = Field(None, max_length=64, description="真实姓名")
    phone: Optional[str] = Field(None, max_length=32, description="手机电话")
    role: str = Field("sales", description="角色：sales, manager, admin")
    is_active: bool = Field(True, description="是否启用")


class EmployeeUpdate(BaseModel):
    """更新员工信息请求体。"""
    real_name: Optional[str] = Field(None, max_length=64)
    phone: Optional[str] = Field(None, max_length=32)
    role: Optional[str] = Field(None)
    is_active: Optional[bool] = Field(None)
    password: Optional[str] = Field(None, min_length=6, max_length=128)


class EmployeeOut(BaseModel):
    """员工信息安全响应（不暴露 password_hash 与 salt）。"""
    id: int
    username: str
    real_name: Optional[str] = None
    phone: Optional[str] = None
    role: str
    is_active: bool
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class EmployeeListResponse(BaseModel):
    """员工列表分页响应。"""
    total: int
    page: int
    page_size: int
    items: list[EmployeeOut]

    model_config = ConfigDict(from_attributes=True)
