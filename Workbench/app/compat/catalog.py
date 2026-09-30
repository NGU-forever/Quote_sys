"""兼容层：公开目录（落地页报价计算器读取，无需登录）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.services.catalog_service import build_catalog

router = APIRouter()


@router.get("/catalog")
def get_catalog(db: Session = Depends(get_db)):
    return {"data": build_catalog(db)}
