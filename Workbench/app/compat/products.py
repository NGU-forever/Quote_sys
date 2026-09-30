"""兼容层：产品（设备 + 耗材）增删改查 + 设备-耗材绑定 + 照片上传。

路径与响应结构均与旧 Node 后端 /api/products 保持一致。
"""
import time
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, require_user
from app.db.base import now_str
from app.models.device_binding import DeviceBinding
from app.models.product import Product
from app.models.user import User
from app.services.catalog_service import (
    bound_consumable_skus,
    bound_device_skus,
    map_product,
    next_sku_id,
    to_number,
)

router = APIRouter(prefix="/products")

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


@router.get("")
def list_products(
    category: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_user),
):
    stmt = select(Product)
    if category in ("device", "consumable"):
        stmt = stmt.where(Product.category == category)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                Product.name.like(like),
                Product.sku_id.like(like),
                Product.applicable_devices.like(like),
            )
        )
    products = db.scalars(stmt.order_by(Product.sku_id.asc())).all()
    return {"data": [map_product(db, p) for p in products]}


@router.post("", status_code=201)
def create_product(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_user),
):
    category = "device" if payload.get("category") == "device" else "consumable"
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="产品名称不能为空")

    sku_id = str(payload.get("sku_id") or "").strip() or next_sku_id(db, category)
    if db.scalar(select(Product).where(Product.sku_id == sku_id)):
        raise HTTPException(status_code=400, detail=f"SKU {sku_id} 已存在")

    product = Product(
        sku_id=sku_id,
        category=category,
        name=name,
        min_price=to_number(payload.get("min_price")),
        max_price=to_number(payload.get("max_price")),
        unit=str(payload.get("unit") or "").strip() or None,
        pieces_per_unit=to_number(payload.get("pieces_per_unit")),
        units_per_box=to_number(payload.get("units_per_box")),
        box_price=to_number(payload.get("box_price")),
        applicable_devices=str(payload.get("applicable_devices") or "").strip() or None,
        raw_price_desc=str(payload.get("raw_price_desc") or "").strip() or None,
        remark=str(payload.get("remark") or "").strip() or None,
        image=str(payload.get("image") or "").strip() or None,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return {"data": map_product(db, product)}


@router.put("/{product_id}")
def update_product(
    product_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_user),
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")

    name = str(payload.get("name") if payload.get("name") is not None else product.name).strip()
    if not name:
        raise HTTPException(status_code=400, detail="产品名称不能为空")

    raw_sku = payload.get("sku_id")
    sku_id = str(raw_sku if raw_sku is not None else product.sku_id).strip() or product.sku_id
    dup = db.scalar(select(Product).where(Product.sku_id == sku_id, Product.id != product_id))
    if dup:
        raise HTTPException(status_code=400, detail=f"SKU {sku_id} 已存在")

    def getv(key, fallback):
        return payload.get(key) if payload.get(key) is not None else fallback

    product.sku_id = sku_id
    product.name = name
    product.min_price = to_number(getv("min_price", product.min_price))
    product.max_price = to_number(getv("max_price", product.max_price))
    product.unit = str(getv("unit", product.unit) or "").strip() or None
    product.pieces_per_unit = to_number(getv("pieces_per_unit", product.pieces_per_unit))
    product.units_per_box = to_number(getv("units_per_box", product.units_per_box))
    product.box_price = to_number(getv("box_price", product.box_price))
    product.applicable_devices = str(getv("applicable_devices", product.applicable_devices) or "").strip() or None
    product.raw_price_desc = str(getv("raw_price_desc", product.raw_price_desc) or "").strip() or None
    product.remark = str(getv("remark", product.remark) or "").strip() or None
    product.image = str(getv("image", product.image) or "").strip() or None
    db.commit()
    db.refresh(product)
    return {"data": map_product(db, product)}


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_user),
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    sku_id = product.sku_id
    db.delete(product)
    db.execute(
        delete(DeviceBinding).where(
            or_(
                DeviceBinding.device_sku_id == sku_id,
                DeviceBinding.consumable_sku_id == sku_id,
            )
        )
    )
    db.commit()
    return {"ok": True}


@router.put("/{product_id}/bindings")
def update_bindings(
    product_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_user),
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")

    is_device = product.category == "device"
    field = "consumable_sku_ids" if is_device else "device_sku_ids"
    target_category = "consumable" if is_device else "device"

    raw = payload.get(field) if isinstance(payload, dict) else None
    requested = (
        list(dict.fromkeys(str(s).strip() for s in raw if str(s).strip()))
        if isinstance(raw, list)
        else []
    )

    if requested:
        valid = set(
            db.scalars(
                select(Product.sku_id).where(
                    Product.category == target_category,
                    Product.sku_id.in_(requested),
                )
            ).all()
        )
        invalid = [sku for sku in requested if sku not in valid]
        if invalid:
            label = "耗材" if is_device else "设备"
            raise HTTPException(status_code=400, detail=f"以下{label}不存在：{'、'.join(invalid)}")

    key_col = DeviceBinding.device_sku_id if is_device else DeviceBinding.consumable_sku_id
    db.execute(delete(DeviceBinding).where(key_col == product.sku_id))
    for sku in requested:
        db.add(
            DeviceBinding(
                device_sku_id=product.sku_id if is_device else sku,
                consumable_sku_id=sku if is_device else product.sku_id,
            )
        )
    db.commit()

    return {
        "data": {
            "sku_id": product.sku_id,
            "bound_consumables": bound_consumable_skus(db, product.sku_id) if is_device else [],
            "bound_devices": bound_device_skus(db, product.sku_id) if not is_device else [],
        }
    }


@router.post("/{product_id}/photo")
async def upload_photo(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_user),
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")

    ext = Path(file.filename or "").suffix.lower() or ".jpg"
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="仅支持 jpg / png / webp / gif 格式的图片")

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=400, detail="图片大小超过 5MB 限制")

    upload_dir = Path(settings.upload_dir) / "products"
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"p{int(time.time() * 1000)}{ext}"
    (upload_dir / filename).write_bytes(content)

    product.image = f"/uploads/products/{filename}"
    product.updated_at = now_str()
    db.commit()
    db.refresh(product)
    return {"data": map_product(db, product)}
