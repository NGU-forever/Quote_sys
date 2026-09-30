"""FastAPI 依赖注入：数据库会话与当前登录用户。"""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.base import get_db
from app.models.user import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """从 Authorization: Bearer <token> 解析当前用户；无/无效令牌返回 None。"""
    header = request.headers.get("authorization", "")
    token = header[7:] if header.startswith("Bearer ") else ""
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    try:
        return db.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def require_user(user: User | None = Depends(get_current_user)) -> User:
    """要求已登录；未登录抛出 401（由全局异常处理器统一格式化响应）。"""
    if user is None:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return user
