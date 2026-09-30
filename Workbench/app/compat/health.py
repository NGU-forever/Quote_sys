"""兼容层：健康检查。"""
from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
@router.get("/api/health")
def health_check():
    return {
        "ok": True,
        "app": settings.app_name,
        "version": settings.app_version,
        "time": datetime.now(timezone.utc).isoformat(),
    }
