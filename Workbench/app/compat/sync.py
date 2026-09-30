"""同步接口：/api/sync（公开，客户机单向拉取）+ /api/settings（登录读写）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_user
from app.models.user import User
from app.services.settings_service import build_sync_payload, get_settings_dict, put_settings

router = APIRouter()


@router.get("/sync")
def sync(db: Session = Depends(get_db)):
    return {"data": build_sync_payload(db)}


@router.get("/settings")
def read_settings(db: Session = Depends(get_db), _: User = Depends(require_user)):
    return {"data": get_settings_dict(db)}


@router.put("/settings")
def write_settings(payload: dict, db: Session = Depends(get_db), _: User = Depends(require_user)):
    company = payload.get("company") if isinstance(payload.get("company"), dict) else None
    pricing = payload.get("pricing") if isinstance(payload.get("pricing"), dict) else None
    if company is None and pricing is None:
        raise HTTPException(status_code=400, detail="company 或 pricing 至少提供一个")
    return {"data": put_settings(db, company, pricing)}
