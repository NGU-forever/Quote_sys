"""启动播种：内置应急 admin 账号 + app_settings 初始数据，不动现有业务表。"""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.app_setting import AppSetting
from app.models.user import RESERVED_ADMIN_USERNAME, User
from app.services.settings_service import DEFAULT_COMPANY, DEFAULT_PRICING

DEFAULT_ADMIN_PASSWORD = "admin123"


def seed_reserved_admin(db: Session) -> None:
    """确保数据库保留内置应急账号 admin/admin123（仅缺省时创建，不覆盖已有记录）。

    users 表为空的新环境同样会在这里自动创建默认账号；已有正式账号但缺少
    内置 admin 时也会补齐，避免把应急账号逻辑和首启播种写成两套。
    """
    if db.scalar(select(User).where(User.username == RESERVED_ADMIN_USERNAME)) is not None:
        return
    hashed = hash_password(DEFAULT_ADMIN_PASSWORD)
    db.add(
        User(
            username=RESERVED_ADMIN_USERNAME,
            password_hash=hashed["hash"],
            salt=hashed["salt"],
        )
    )
    db.commit()


def seed_app_settings(db: Session) -> None:
    """app_settings 缺失时写入默认值（幂等）。"""
    existing = {s.key for s in db.scalars(select(AppSetting)).all()}
    if "company" not in existing:
        db.add(AppSetting(key="company", value=json.dumps(DEFAULT_COMPANY, ensure_ascii=False)))
    if "pricing" not in existing:
        db.add(AppSetting(key="pricing", value=json.dumps(DEFAULT_PRICING, ensure_ascii=False)))
    db.commit()
