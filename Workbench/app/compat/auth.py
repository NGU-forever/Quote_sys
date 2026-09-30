"""兼容层：首次注册、登录 / 当前用户（与旧前端 localStorage + Bearer token 流程一致）。

首次使用时仅允许注册一个正式账号；内置 admin/admin123 作为隐藏应急账号保留，
不展示在登录页，但始终可用于找回登录。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import RESERVED_ADMIN_USERNAME, User
from app.schemas.auth import LoginRequest, RegisterRequest, ResetPasswordRequest

router = APIRouter(prefix="/auth")


def has_registered_user(db: Session) -> bool:
    """是否存在除内置 admin 之外的正式工作台账号。"""
    count = db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.username != RESERVED_ADMIN_USERNAME)
    )
    return bool(count)


def auth_response(user: User) -> dict:
    return {
        "token": create_access_token(user.id, user.username),
        "user": {"id": user.id, "username": user.username},
    }


@router.get("/status", summary="首次使用状态：是否已注册正式账号")
def auth_status(db: Session = Depends(get_db)):
    return {"registered": has_registered_user(db)}


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    username = payload.username.strip()
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(payload.password, user.salt, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return auth_response(user)


@router.post("/register", summary="首次使用注册正式工作台账号（仅限未注册状态）")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if has_registered_user(db):
        raise HTTPException(status_code=403, detail="已注册工作台账号，不能重复注册")

    username = payload.username.strip()
    if not username or len(username) > 32:
        raise HTTPException(status_code=400, detail="用户名长度需为 1-32 个字符")
    if username == RESERVED_ADMIN_USERNAME:
        raise HTTPException(status_code=400, detail="该用户名已被系统保留")
    if db.scalar(select(User).where(User.username == username)) is not None:
        raise HTTPException(status_code=409, detail="该用户名已被使用")
    if len(payload.password) < 6 or len(payload.password) > 128:
        raise HTTPException(status_code=400, detail="密码长度需为 6-128 个字符")

    hashed = hash_password(payload.password)
    user = User(
        username=username,
        password_hash=hashed["hash"],
        salt=hashed["salt"],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return auth_response(user)


def require_admin(user: User = Depends(require_user)) -> User:
    """仅内置 admin 应急账号可调用：账号恢复 / 重置正式账号密码。"""
    if user.username != RESERVED_ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="仅内置管理员可执行此操作")
    return user


@router.get("/accounts", summary="内置 admin 查看正式账号列表")
def list_accounts(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.scalars(select(User).where(User.username != RESERVED_ADMIN_USERNAME)).all()
    return {"users": [{"id": u.id, "username": u.username} for u in users]}


@router.post("/reset-password", summary="内置 admin 重置正式账号密码")
def reset_password(
    payload: ResetPasswordRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    username = payload.username.strip()
    if username == RESERVED_ADMIN_USERNAME:
        raise HTTPException(status_code=400, detail="内置应急账号密码不可修改")
    if len(payload.new_password) < 6 or len(payload.new_password) > 128:
        raise HTTPException(status_code=400, detail="新密码长度需为 6-128 个字符")

    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise HTTPException(status_code=404, detail="账号不存在")

    hashed = hash_password(payload.new_password)
    user.password_hash = hashed["hash"]
    user.salt = hashed["salt"]
    db.commit()
    return {"ok": True, "username": user.username}


@router.get("/me")
def me(user: User = Depends(require_user)):
    return {"user": {"id": user.id, "username": user.username}}
