"""启动播种：内置应急 admin 账号 + app_settings 初始数据 + 可选通用示例商品。"""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.app_setting import AppSetting
from app.models.item_relation import ItemRelation
from app.models.package import Package
from app.models.product import Product
from app.models.user import RESERVED_ADMIN_USERNAME, User
from app.services.settings_service import DEFAULT_COMPANY, DEFAULT_PRICING

DEFAULT_ADMIN_PASSWORD = "admin123"


def seed_reserved_admin(db: Session) -> None:
    """确保数据库保留内置应急账号 admin/admin123（仅缺省时创建，不覆盖已有记录）。"""
    admin = db.scalar(select(User).where(User.username == RESERVED_ADMIN_USERNAME))
    if admin is not None:
        if admin.role != "admin" or not admin.real_name:
            admin.role = "admin"
            if not admin.real_name:
                admin.real_name = "系统管理员"
            db.commit()
        return
    hashed = hash_password(DEFAULT_ADMIN_PASSWORD)
    db.add(
        User(
            username=RESERVED_ADMIN_USERNAME,
            password_hash=hashed["hash"],
            salt=hashed["salt"],
            real_name="系统管理员",
            role="admin",
            is_active=True,
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


def seed_sample_products(db: Session) -> None:
    """写入通用商业演示商品数据（硬件终端、传感器附件、技术支持服务等）及套餐与关联。"""
    samples = [
        Product(
            sku_id="HW-GW-001",
            category="hardware",
            name="工业边缘计算网关",
            spec="4核CPU/8G内存/双千兆网口",
            unit="台",
            min_price=1200.0,
            max_price=1600.0,
            is_active=True,
        ),
        Product(
            sku_id="SEN-TH-001",
            category="sensor",
            name="高精度温湿度传感器",
            spec="RS485/Modbus-RTU工业级",
            unit="个",
            min_price=120.0,
            max_price=180.0,
            is_active=True,
        ),
        Product(
            sku_id="SVC-DEP-001",
            category="service",
            name="现场系统部署与交付技术支持",
            spec="高级工程师上门人天",
            unit="人天",
            min_price=1000.0,
            max_price=1500.0,
            is_active=True,
        ),
    ]

    for p in samples:
        if not db.scalar(select(Product).where(Product.sku_id == p.sku_id)):
            db.add(p)
    db.commit()

    # 添加配件配套关联
    gw = db.scalar(select(Product).where(Product.sku_id == "HW-GW-001"))
    sen = db.scalar(select(Product).where(Product.sku_id == "SEN-TH-001"))
    if gw and sen:
        existing_rel = db.scalar(
            select(ItemRelation).where(
                ItemRelation.parent_product_id == gw.id,
                ItemRelation.child_product_id == sen.id,
            )
        )
        if not existing_rel:
            db.add(
                ItemRelation(
                    parent_product_id=gw.id,
                    child_product_id=sen.id,
                    relation_type="accessory",
                )
            )
            db.commit()

    # 添加标准物联采集套餐
    pkg_code = "PKG-IOT-STD"
    if not db.scalar(select(Package).where(Package.package_code == pkg_code)):
        db.add(
            Package(
                package_code=pkg_code,
                name="智能物联标准采集套餐",
                description="含网关终端1台、温湿度传感器2只及现场部署服务",
                bundle_price=2300.0,
                items_config=[
                    {"sku_id": "HW-GW-001", "name": "工业边缘计算网关", "quantity": 1},
                    {"sku_id": "SEN-TH-001", "name": "高精度温湿度传感器", "quantity": 2},
                    {"sku_id": "SVC-DEP-001", "name": "现场系统部署与交付技术支持", "quantity": 1},
                ],
                is_active=True,
            )
        )
        db.commit()
