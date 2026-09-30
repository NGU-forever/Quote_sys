"""兼容层：健康检查。"""
from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True, "app": "hhz-data-service", "time": datetime.now(timezone.utc).isoformat()}
