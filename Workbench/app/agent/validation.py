"""候选数据服务端硬校验：模型输出必须通过白名单结构 + 引用完整性检查。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.schemas import CandidateSet
from app.models.device_binding import DeviceBinding
from app.models.product import Product
from pydantic import ValidationError


def _error_path(err) -> str:
    loc = ".".join(str(x) for x in err.get("loc", []))
    return f"{loc}: {err.get('msg', '')}" if loc else str(err.get("msg", ""))


def validate_candidates(payload: dict, db: Session) -> tuple[dict, list[str], list[str]]:
    """返回 (normalized, issues, errors)；errors 非空时不允许 apply。"""
    try:
        parsed = CandidateSet.model_validate(payload or {})
    except ValidationError as exc:
        errors = [_error_path(err) for err in exc.errors()]
        return {"products": [], "packages": [], "bindings": [], "issues": []}, [], errors

    issues = list(parsed.issues)
    errors: list[str] = []
    normalized = {
        "products": [p.model_dump(mode="json") for p in parsed.products],
        "packages": [p.model_dump(mode="json") for p in parsed.packages],
        "bindings": [b.model_dump(mode="json") for b in parsed.bindings],
        "issues": issues,
    }
    if not parsed.products and not parsed.packages and not parsed.bindings:
        errors.append("未收到任何可导入的候选记录")

    # 产品：SKU 不能重复；不能把已有商品改成另一类别
    seen_skus: dict[str, str] = {}
    existing = {
        row.sku_id: {"category": row.category, "name": row.name}
        for row in db.scalars(select(Product)).all()
    }
    existing_bindings = {
        (b.device_sku_id, b.consumable_sku_id)
        for b in db.scalars(select(DeviceBinding)).all()
    }
    for p in parsed.products:
        if p.sku_id in seen_skus:
            errors.append(f"候选 SKU {p.sku_id} 重复出现")
        else:
            seen_skus[p.sku_id] = p.category
        if p.sku_id in existing and existing[p.sku_id]["category"] != p.category:
            errors.append(
                f"SKU {p.sku_id} 已存在且类别为 {existing[p.sku_id]['category']}，不能改为 {p.category}"
            )

    known = {sku: category for sku, category in seen_skus.items()}
    known.update({sku: row["category"] for sku, row in existing.items()})

    # 套餐：id 唯一、SKU 必须已存在或在本批产品中、数量长度一致（schema 已保证）
    seen_packages: set[str] = set()
    for pkg in parsed.packages:
        if pkg.package_id in seen_packages:
            errors.append(f"候选套餐 {pkg.package_id} 重复出现")
        else:
            seen_packages.add(pkg.package_id)
        unknown = [sku for sku in pkg.sku_ids if sku not in known]
        if unknown:
            errors.append(
                f"套餐 {pkg.package_id} 引用了不存在的 SKU：{'、'.join(unknown)}"
            )

    # 绑定：引用必须存在且类别符合设备/耗材
    seen_bindings: set[tuple[str, str]] = set()
    for b in parsed.bindings:
        key = (b.device_sku_id, b.consumable_sku_id)
        if key in seen_bindings:
            errors.append(f"绑定 {b.device_sku_id}-{b.consumable_sku_id} 重复出现")
        else:
            seen_bindings.add(key)
        device_category = known.get(b.device_sku_id)
        consumable_category = known.get(b.consumable_sku_id)
        if device_category is None:
            errors.append(f"绑定引用了不存在的设备 SKU：{b.device_sku_id}")
        elif device_category != "device":
            errors.append(f"绑定左侧 {b.device_sku_id} 不是设备（category={device_category}）")
        if consumable_category is None:
            errors.append(f"绑定引用了不存在的耗材 SKU：{b.consumable_sku_id}")
        elif consumable_category != "consumable":
            errors.append(
                f"绑定右侧 {b.consumable_sku_id} 不是耗材（category={consumable_category}）"
            )

    # 套餐不得与最终设备-耗材绑定冲突（与既有套餐管理接口口径一致）
    final_bindings = existing_bindings | seen_bindings
    bound_by_device: dict[str, set[str]] = {}
    for device_sku, consumable_sku in final_bindings:
        bound_by_device.setdefault(device_sku, set()).add(consumable_sku)
    for pkg in parsed.packages:
        device_skus = [sku for sku in pkg.sku_ids if known.get(sku) == "device"]
        consumable_skus = [sku for sku in pkg.sku_ids if known.get(sku) == "consumable"]
        if not device_skus or not consumable_skus:
            continue
        restricted = [sku for sku in device_skus if bound_by_device.get(sku)]
        if not restricted:
            continue
        allowed: set[str] = set()
        for sku in restricted:
            allowed.update(bound_by_device.get(sku, set()))
        offending = [sku for sku in consumable_skus if sku not in allowed]
        if offending:
            errors.append(
                f"套餐 {pkg.package_id} 中设备已绑定耗材，以下耗材不可搭配："
                f"{'、'.join(offending)}（可搭配：{'、'.join(sorted(allowed)) or '无'}）"
            )

    return normalized, issues, errors
