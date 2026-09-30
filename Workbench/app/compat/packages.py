"""兼容层：套餐增删改查（与旧 Node 后端 /api/packages 一致）。"""
import json

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_user
from app.models.package import Package
from app.models.user import User
from app.services.catalog_service import (
    map_package,
    next_package_id,
    normalize_package_body,
    validate_package_bindings,
)

router = APIRouter(prefix="/packages")


@router.get("")
def list_packages(db: Session = Depends(get_db), _: User = Depends(require_user)):
    packages = db.scalars(select(Package).order_by(Package.package_id.asc())).all()
    return {"data": [map_package(p) for p in packages]}


@router.post("", status_code=201)
def create_package(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_user),
):
    body = normalize_package_body(db, payload)
    if not body["name"]:
        raise HTTPException(status_code=400, detail="套餐名称不能为空")
    if not body["sku_ids"]:
        raise HTTPException(status_code=400, detail="请至少选择一个 SKU")
    binding_error = validate_package_bindings(db, body["sku_ids"])
    if binding_error:
        raise HTTPException(status_code=400, detail=binding_error)

    package_id = str(payload.get("package_id") or "").strip() or next_package_id(db)
    if db.scalar(select(Package).where(Package.package_id == package_id)):
        raise HTTPException(status_code=400, detail=f"套餐 {package_id} 已存在")

    pkg = Package(
        package_id=package_id,
        name=body["name"],
        sku_ids=json.dumps(body["sku_ids"]),
        quantities=json.dumps(body["quantities"]),
        std_price=body["std_price"],
        discount_price=body["discount_price"],
        discount_rate=body["discount_rate"],
        device_qty=body["device_qty"],
        consumable_qty=body["consumable_qty"],
        consumable_boxes=body["consumable_boxes"],
        fixed_bundle=body["fixed_bundle"],
        device_price=body["device_price"],
        note=body["note"],
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return {"data": map_package(pkg)}


@router.put("/{package_id}")
def update_package(
    package_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_user),
):
    existing = db.get(Package, package_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="套餐不存在")

    body = normalize_package_body(db, payload)
    if not body["name"]:
        raise HTTPException(status_code=400, detail="套餐名称不能为空")
    if not body["sku_ids"]:
        raise HTTPException(status_code=400, detail="请至少选择一个 SKU")
    binding_error = validate_package_bindings(db, body["sku_ids"])
    if binding_error:
        raise HTTPException(status_code=400, detail=binding_error)

    raw_pid = payload.get("package_id")
    new_pid = str(raw_pid if raw_pid is not None else existing.package_id).strip() or existing.package_id
    dup = db.scalar(select(Package).where(Package.package_id == new_pid, Package.id != package_id))
    if dup:
        raise HTTPException(status_code=400, detail=f"套餐 {new_pid} 已存在")

    existing.package_id = new_pid
    existing.name = body["name"]
    existing.sku_ids = json.dumps(body["sku_ids"])
    existing.quantities = json.dumps(body["quantities"])
    existing.std_price = body["std_price"]
    existing.discount_price = body["discount_price"]
    existing.discount_rate = body["discount_rate"]
    existing.device_qty = body["device_qty"]
    existing.consumable_qty = body["consumable_qty"]
    existing.consumable_boxes = body["consumable_boxes"]
    existing.fixed_bundle = body["fixed_bundle"]
    existing.device_price = body["device_price"]
    existing.note = body["note"]
    db.commit()
    db.refresh(existing)
    return {"data": map_package(existing)}


@router.delete("/{package_id}")
def delete_package(
    package_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_user),
):
    pkg = db.get(Package, package_id)
    if pkg is None:
        raise HTTPException(status_code=404, detail="套餐不存在")
    db.delete(pkg)
    db.commit()
    return {"ok": True}
