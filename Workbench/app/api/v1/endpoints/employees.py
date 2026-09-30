"""员工账号管理路由端点。

包含：
- GET /api/admin/employees: 员工列表管理（支持分页/筛选，不暴露密码哈希与 salt）
- POST /api/admin/employees: 创建销售/管理员账号
- PUT /api/admin/employees/{user_id}: 更新员工基本信息或重置密码
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_user
from app.core.security import hash_password
from app.models.user import RESERVED_ADMIN_USERNAME, User
from app.schemas.employee_schemas import (
    EmployeeCreate,
    EmployeeListResponse,
    EmployeeOut,
    EmployeeUpdate,
)

router = APIRouter(prefix="/admin/employees", tags=["admin-employees"])


def require_admin_role(user: User = Depends(require_user)) -> User:
    """仅具有 admin/manager 角色或内置 admin 账号可执行员工管理操作。"""
    if user.role not in ("admin", "manager") and user.username != RESERVED_ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


@router.get("", response_model=EmployeeListResponse, summary="查询员工账号列表")
def list_employees(
    keyword: Optional[str] = Query(None, description="搜索用户名/姓名/电话"),
    role: Optional[str] = Query(None, description="角色筛选（sales, manager, admin）"),
    is_active: Optional[bool] = Query(None, description="账号启用状态"),
    page: int = Query(1, ge=1, description="当前页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_role),
):
    """查询员工账号列表（支持按角色/关键字/状态筛选与分页，密码已脱敏）。"""
    stmt = select(User)

    if keyword:
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                User.username.like(kw),
                User.real_name.like(kw),
                User.phone.like(kw),
            )
        )

    if role:
        stmt = stmt.where(User.role == role.strip())

    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    offset = max(0, (page - 1) * page_size)
    users = list(db.scalars(stmt.order_by(User.id.asc()).offset(offset).limit(page_size)).all())

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": users,
    }


@router.post("", response_model=EmployeeOut, status_code=201, summary="创建员工账号")
def create_employee(
    payload: EmployeeCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_role),
):
    """创建新的销售或管理人员账号。"""
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")

    if db.scalar(select(User).where(User.username == username)) is not None:
        raise HTTPException(status_code=409, detail=f"用户名 {username} 已存在")

    hashed = hash_password(payload.password)
    user = User(
        username=username,
        password_hash=hashed["hash"],
        salt=hashed["salt"],
        real_name=payload.real_name.strip() if payload.real_name else None,
        phone=payload.phone.strip() if payload.phone else None,
        role=payload.role.strip() if payload.role else "sales",
        is_active=payload.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=EmployeeOut, summary="更新员工账号信息")
def update_employee(
    user_id: int,
    payload: EmployeeUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_role),
):
    """更新员工真实姓名、联系电话、角色、启用状态或重置密码。"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="员工账号不存在")

    if payload.real_name is not None:
        user.real_name = payload.real_name.strip() or None
    if payload.phone is not None:
        user.phone = payload.phone.strip() or None
    if payload.role is not None:
        user.role = payload.role.strip()
    if payload.is_active is not None:
        if user.username == RESERVED_ADMIN_USERNAME and payload.is_active is False:
            raise HTTPException(status_code=400, detail="内置应急管理员账号不可停用")
        user.is_active = payload.is_active
    if payload.password:

        hashed = hash_password(payload.password)
        user.password_hash = hashed["hash"]
        user.salt = hashed["salt"]

    db.commit()
    db.refresh(user)
    return user
