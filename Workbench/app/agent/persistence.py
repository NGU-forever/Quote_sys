"""候选暂存、冲突判定与受控事务入库。"""
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import now_str
from app.models.device_binding import DeviceBinding
from app.models.package import Package
from app.models.product import Product
from app.services.catalog_service import to_number


PRODUCT_FIELDS = [
    "min_price",
    "max_price",
    "unit",
    "pieces_per_unit",
    "units_per_box",
    "box_price",
    "applicable_devices",
    "raw_price_desc",
    "remark",
]

PACKAGE_FIELDS = [
    "sku_ids",
    "quantities",
    "std_price",
    "discount_price",
    "discount_rate",
    "device_qty",
    "consumable_qty",
    "consumable_boxes",
    "fixed_bundle",
    "device_price",
    "note",
]


def _same(a, b) -> bool:
    if isinstance(a, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    return to_number(a) == to_number(b) if a is not None and b is not None else a == b


def _candidate_diff(field_names: list[str], existing, candidate: dict, existing_json=None) -> list[str]:
    diff = []
    for field in field_names:
        value = candidate.get(field)
        if field == "fixed_bundle" and value is not None:
            value = 1 if value is True or value == 1 else 0
        if value is None:
            continue
        if existing_json is not None and field in ("sku_ids", "quantities"):
            current = json.loads(existing_json[field] or "[]")
        else:
            current = getattr(existing, field, None)
        if not _same(current, value):
            diff.append(field)
    return diff


def apply_candidates(db: Session, candidates: dict, mode: str, allow_name_update: bool = False) -> dict:
    """dry-run 返回“将会”统计；apply 用单事务写入正式业务表。

    规模与并发：
    - 只按候选集涉及的 SKU / 套餐 ID 取数，不再把整表读进内存；
    - ``FOR UPDATE`` 锁定待改动的行，避免多进程/多 worker 下的读-改-写互相覆盖；
    - 同一进程内另有 ``agent_service`` 的活跃运行互斥，二者叠加覆盖跨进程场景。
    """
    candidate_products = list(candidates.get("products") or [])
    candidate_packages = list(candidates.get("packages") or [])
    candidate_bindings = list(candidates.get("bindings") or [])

    product_skus = [str(p.get("sku_id")) for p in candidate_products if p.get("sku_id")]
    package_ids = [str(p.get("package_id")) for p in candidate_packages if p.get("package_id")]
    binding_keys = {
        (str(b.get("device_sku_id")), str(b.get("consumable_sku_id")))
        for b in candidate_bindings
        if b.get("device_sku_id") and b.get("consumable_sku_id")
    }

    product_by_sku: dict[str, Product] = {}
    if product_skus:
        product_by_sku = {
            row.sku_id: row
            for row in db.scalars(
                select(Product).where(Product.sku_id.in_(product_skus)).with_for_update()
            ).all()
        }
    package_by_id: dict[str, Package] = {}
    if package_ids:
        package_by_id = {
            row.package_id: row
            for row in db.scalars(
                select(Package).where(Package.package_id.in_(package_ids)).with_for_update()
            ).all()
        }
    existing_bindings: set[tuple[str, str]] = set()
    if binding_keys:
        device_ids = {key[0] for key in binding_keys}
        existing_bindings = {
            (row.device_sku_id, row.consumable_sku_id)
            for row in db.execute(
                select(DeviceBinding.device_sku_id, DeviceBinding.consumable_sku_id).where(
                    DeviceBinding.device_sku_id.in_(device_ids)
                )
            ).all()
        }

    result = {
        "mode": mode,
        "products_added": 0,
        "products_updated": 0,
        "products_skipped": 0,
        "packages_added": 0,
        "packages_updated": 0,
        "packages_skipped": 0,
        "bindings_added": 0,
        "bindings_skipped": 0,
        "issues": list(candidates.get("issues", [])),
    }

    for product in candidate_products:
        existing = product_by_sku.get(product["sku_id"])
        if existing is None:
            result["products_added"] += 1
            if mode == "apply":
                db.add(
                    Product(
                        sku_id=product["sku_id"],
                        category=product["category"],
                        name=product["name"],
                        min_price=to_number(product.get("min_price")),
                        max_price=to_number(product.get("max_price")),
                        unit=product.get("unit"),
                        pieces_per_unit=product.get("pieces_per_unit"),
                        units_per_box=product.get("units_per_box"),
                        box_price=to_number(product.get("box_price")),
                        applicable_devices=product.get("applicable_devices"),
                        raw_price_desc=product.get("raw_price_desc"),
                        remark=product.get("remark"),
                        image=product.get("image"),
                    )
                )
            continue
        name_changed = False
        if existing.name != product["name"]:
            if not allow_name_update:
                result["products_skipped"] += 1
                result["issues"].append(
                    f"SKU {product['sku_id']} 现有名称与资料名称不同，为避免错误合并已跳过："
                    f"现有「{existing.name}」→ 资料「{product['name']}」"
                )
                continue
            name_changed = True
        diff = _candidate_diff(PRODUCT_FIELDS, existing, product)
        if not diff and not name_changed:
            result["products_skipped"] += 1
            continue
        result["products_updated"] += 1
        if mode != "apply":
            continue
        if name_changed:
            existing.name = product["name"]
        for field in diff:
            value = product.get(field)
            setattr(existing, field, value)
        existing.updated_at = now_str()

    for binding in candidate_bindings:
        key = (binding["device_sku_id"], binding["consumable_sku_id"])
        if key in existing_bindings:
            result["bindings_skipped"] += 1
            continue
        result["bindings_added"] += 1
        if mode == "apply":
            db.add(
                DeviceBinding(
                    device_sku_id=binding["device_sku_id"],
                    consumable_sku_id=binding["consumable_sku_id"],
                )
            )

    for package in candidate_packages:
        existing = package_by_id.get(package["package_id"])
        if existing is None:
            result["packages_added"] += 1
            if mode == "apply":
                db.add(
                    Package(
                        package_id=package["package_id"],
                        name=package["name"],
                        sku_ids=json.dumps(package["sku_ids"], ensure_ascii=False),
                        quantities=json.dumps(package["quantities"], ensure_ascii=False),
                        std_price=to_number(package.get("std_price")),
                        discount_price=to_number(package.get("discount_price")),
                        discount_rate=package.get("discount_rate"),
                        device_qty=package.get("device_qty"),
                        consumable_qty=package.get("consumable_qty"),
                        consumable_boxes=package.get("consumable_boxes"),
                        fixed_bundle=1 if package.get("fixed_bundle") else 0,
                        device_price=to_number(package.get("device_price")),
                        note=package.get("note"),
                    )
                )
            continue
        pkg_name_changed = False
        if existing.name != package["name"]:
            if not allow_name_update:
                result["packages_skipped"] += 1
                result["issues"].append(
                    f"套餐 {package['package_id']} 现有名称与资料名称不同，为避免错误合并已跳过"
                )
                continue
            pkg_name_changed = True
        diff = _candidate_diff(PACKAGE_FIELDS, existing, package)
        if not diff and not pkg_name_changed:
            result["packages_skipped"] += 1
            continue
        result["packages_updated"] += 1
        if mode != "apply":
            continue
        if pkg_name_changed:
            existing.name = package["name"]
        for field in diff:
            value = package.get(field)
            if field in ("sku_ids", "quantities"):
                setattr(existing, field, json.dumps(value, ensure_ascii=False))
            elif field == "fixed_bundle":
                existing.fixed_bundle = 1 if value else 0
            else:
                setattr(existing, field, value)
        existing.updated_at = now_str()

    if mode == "apply":
        try:
            db.commit()
        except IntegrityError as exc:
            # 并发写入撞唯一键：回滚并用明确错误暴露，避免留下半截数据
            db.rollback()
            raise RuntimeError(
                f"入库冲突：候选数据与并发写入重复（{type(exc.orig).__name__}），已整体回滚"
            ) from exc
    return result
