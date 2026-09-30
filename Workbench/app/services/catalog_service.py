"""兼容层业务逻辑（接口契约对齐旧工作台后端，前端无需改动即可切换）。

包含：
- 设备-耗材绑定读取（bound_consumable_skus / bound_device_skus）
- product / package 的序列化（map_product / map_package）
- 落地页目录构建（build_catalog）
- 套餐报价字段推导与绑定校验（derive_package_quote_fields / validate_package_bindings）
- 下一个 sku / package id 生成

行为与旧工作台后端保持一致，保证旧前端无需改动即可切换。
"""
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.redis_client import get_redis
from app.models.device_binding import DeviceBinding
from app.models.package import Package
from app.models.product import Product

logger = logging.getLogger(__name__)



def to_number(value):
    """与 Node 端 toNumber 对齐：空值→None，整数值返回 int，其余返回 float。"""
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n != n:  # NaN
        return None
    return int(n) if n.is_integer() else n


# ---------- 设备-耗材绑定 ----------

def bound_consumable_skus(db: Session, device_sku_id: str) -> list[str]:
    """某设备已绑定的耗材 sku 列表（按 sku 升序）。"""
    return list(
        db.scalars(
            select(DeviceBinding.consumable_sku_id)
            .where(DeviceBinding.device_sku_id == device_sku_id)
            .order_by(DeviceBinding.consumable_sku_id.asc())
        ).all()
    )


def bound_device_skus(db: Session, consumable_sku_id: str) -> list[str]:
    """某耗材已绑定的设备 sku 列表（按 sku 升序）。"""
    return list(
        db.scalars(
            select(DeviceBinding.device_sku_id)
            .where(DeviceBinding.consumable_sku_id == consumable_sku_id)
            .order_by(DeviceBinding.device_sku_id.asc())
        ).all()
    )


# ---------- 序列化 ----------

def map_product(db: Session, product: Product) -> dict:
    """序列化产品，附带设备-耗材绑定（双向）。"""
    is_device = product.category in ("device", "hardware")
    return {
        "id": product.id,
        "sku_id": product.sku_id,
        "category": product.category,
        "name": product.name,
        "min_price": to_number(product.min_price),
        "max_price": to_number(product.max_price),
        "unit": product.unit,
        "pieces_per_unit": to_number(product.pieces_per_unit),
        "units_per_box": to_number(product.units_per_box),
        "box_price": to_number(product.box_price),
        "applicable_devices": product.applicable_devices,
        "raw_price_desc": product.raw_price_desc,
        "remark": product.remark,
        "image": product.image or "",
        "created_at": product.created_at,
        "updated_at": product.updated_at,
        "bound_consumables": bound_consumable_skus(db, product.sku_id) if is_device else [],
        "bound_devices": bound_device_skus(db, product.sku_id) if not is_device else [],
        "spec": product.spec,
        "is_active": product.is_active,
    }


def map_package(pkg: Package) -> dict:
    """序列化套餐：解析 JSON 字段，并对齐 sku_ids 与 quantities 长度。"""
    sku_ids = json.loads(pkg.sku_ids or "[]")
    quantities = json.loads(pkg.quantities or "[]")
    aligned = [quantities[i] if i < len(quantities) else None for i in range(len(sku_ids))]
    return {
        "id": pkg.id,
        "package_id": pkg.package_id,
        "name": pkg.name,
        "sku_ids": sku_ids,
        "quantities": aligned,
        "std_price": to_number(pkg.std_price),
        "discount_price": to_number(pkg.discount_price),
        "discount_rate": pkg.discount_rate,
        "device_qty": to_number(pkg.device_qty),
        "consumable_qty": to_number(pkg.consumable_qty),
        "consumable_boxes": to_number(pkg.consumable_boxes),
        "fixed_bundle": bool(pkg.fixed_bundle),
        "device_price": to_number(pkg.device_price),
        "note": pkg.note,
        "created_at": pkg.created_at,
        "updated_at": pkg.updated_at,
    }


# ---------- id 生成 ----------

def next_sku_id(db: Session, category: str) -> str:
    """按类别生成下一个 sku_id（P/C + 三位序号）。"""
    prefix = "P" if category in ("device", "hardware") else "C"
    last = db.scalars(
        select(Product.sku_id)
        .where(Product.category == category, Product.sku_id.like(f"{prefix}%"))
        .order_by(Product.sku_id.desc())
        .limit(1)
    ).first()
    max_n = 0
    if last:
        digits = last[len(prefix):]
        if digits.isdigit():
            max_n = int(digits)
    return f"{prefix}{max_n + 1:03d}"


def next_package_id(db: Session) -> str:
    """生成下一个套餐 id（PKG + 三位序号）。"""
    last = db.scalars(
        select(Package.package_id)
        .where(Package.package_id.like("PKG%"))
        .order_by(Package.package_id.desc())
        .limit(1)
    ).first()
    max_n = 0
    if last:
        digits = last[3:]
        if digits.isdigit():
            max_n = int(digits)
    return f"PKG{max_n + 1:03d}"


# ---------- 套餐报价字段推导与绑定校验 ----------

def derive_package_quote_fields(
    db: Session,
    sku_ids: list[str],
    quantities: list,
    fixed_bundle: bool = False,
) -> tuple:
    """根据 SKU 明细推导套餐报价字段。

    固定整购套餐（fixed_bundle）按“每套包含全部 SKU”统计总数；
    未勾选的赠机/推广套餐把耗材行视为“任选其一的适用耗材”，
    因此按首个耗材行计算单套耗材数量与箱数，避免把多款可选耗材重复相加。
    """
    device_qty = None
    consumable_qty = None
    consumable_boxes = None
    total_boxes = 0
    has_boxes = False
    for i, sku in enumerate(sku_ids):
        product = db.scalar(select(Product).where(Product.sku_id == sku))
        qty = int(quantities[i]) if i < len(quantities) and quantities[i] is not None else 0
        if product is None:
            continue
        if product.category in ("device", "hardware"):
            if fixed_bundle:
                device_qty = (device_qty or 0) + (qty or 1)
            elif device_qty is None:
                device_qty = qty or 1
        else:
            upb = to_number(product.units_per_box)
            if fixed_bundle:
                consumable_qty = (consumable_qty or 0) + qty
                if upb and upb > 0:
                    has_boxes = True
                    total_boxes += qty / upb
            elif consumable_qty is None:
                consumable_qty = qty
                if upb and upb > 0:
                    has_boxes = True
                    total_boxes += qty / upb
    if has_boxes:
        consumable_boxes = round(total_boxes)
    return device_qty, consumable_qty, consumable_boxes


def validate_package_bindings(db: Session, sku_ids: list[str]) -> str | None:
    """设备-耗材绑定校验。返回错误文案（不通过）或 None（通过）。"""
    device_skus: list[str] = []
    consumable_skus: list[str] = []
    for sku in sku_ids:
        product = db.scalar(select(Product).where(Product.sku_id == sku))
        if product is None:
            continue
        if product.category == "device":
            device_skus.append(sku)
        else:
            consumable_skus.append(sku)

    if not device_skus or not consumable_skus:
        return None

    # 存在未绑定耗材的设备 → 自由搭配，允许
    if any(not bound_consumable_skus(db, sku) for sku in device_skus):
        return None

    allowed: set[str] = set()
    for sku in device_skus:
        allowed.update(bound_consumable_skus(db, sku))

    offending = [sku for sku in consumable_skus if sku not in allowed]
    if not offending:
        return None

    def describe(sku: str) -> str:
        p = db.scalar(select(Product).where(Product.sku_id == sku))
        return f"{sku} {p.name if p else ''}".strip()

    return (
        f"套餐内设备已绑定耗材，以下耗材不可搭配：{'、'.join(describe(s) for s in offending)}；"
        f"可搭配：{'、'.join(describe(s) for s in sorted(allowed))}。"
        "如需自由搭配，请先在「设备管理」中解除对应设备的耗材绑定。"
    )


def effective_package_price(pkg: Package) -> float | int | None:
    """Quote 实际结算价：折扣价优先，其次标准价 × 折扣率，最后标准价。"""
    std_price = to_number(pkg.std_price)
    discount_price = to_number(pkg.discount_price)
    if discount_price is not None:
        return discount_price
    if std_price is not None:
        rate_text = str(pkg.discount_rate or "").strip().replace("%", "")
        if rate_text:
            try:
                rate = float(rate_text)
            except ValueError:
                rate = 0.0
            if 0 < rate < 1:
                return to_number(std_price * rate)
    return std_price


def normalize_package_body(db: Session, body: dict) -> dict:
    """规范化套餐请求体：解析 sku/数量、推导报价字段、规范化 null 值。"""
    raw_skus = body.get("sku_ids")
    sku_ids = [str(s).strip() for s in raw_skus] if isinstance(raw_skus, list) else []
    sku_ids = [s for s in sku_ids if s]

    raw_qty = body.get("quantities")
    quantities = [to_number(n) for n in raw_qty] if isinstance(raw_qty, list) else []

    fixed_bundle = 1 if body.get("fixed_bundle") else 0
    dq, cq, cb = derive_package_quote_fields(db, sku_ids, quantities, bool(fixed_bundle))

    def field(key):
        return to_number(body.get(key))

    return {
        "name": str(body.get("name") or "").strip(),
        "sku_ids": sku_ids,
        "quantities": quantities,
        "std_price": field("std_price"),
        "discount_price": field("discount_price"),
        "discount_rate": str(body.get("discount_rate") or "").strip() or None,
        "device_qty": field("device_qty") if field("device_qty") is not None else dq,
        "consumable_qty": field("consumable_qty") if field("consumable_qty") is not None else cq,
        "consumable_boxes": field("consumable_boxes") if field("consumable_boxes") is not None else cb,
        "fixed_bundle": fixed_bundle,
        "device_price": field("device_price"),
        "note": str(body.get("note") or "").strip() or None,
    }


# ---------- 落地页目录 ----------

def build_catalog(db: Session) -> dict:
    """构建落地页报价计算器所需的目录形状（产品 + 套餐）。

    产品 id 按「设备在前、耗材在后、其余通用商品紧随其后，各按 sku_id 升序」稳定生成，
    套餐中的 sku 引用转换为该 id，保证与前端引用自洽。
    """
    products = db.scalars(select(Product).order_by(Product.sku_id.asc())).all()
    devices = [p for p in products if p.category in ("device", "hardware")]
    consumables = [p for p in products if p.category in ("consumable", "consumables")]
    others = [p for p in products if p.category not in ("device", "hardware", "consumable", "consumables")]
    product_by_sku = {p.sku_id: p for p in products}

    id_of: dict[str, int] = {}
    next_id = 1
    for p in devices:
        id_of[p.sku_id] = next_id
        next_id += 1
    for p in consumables:
        id_of[p.sku_id] = next_id
        next_id += 1
    for p in others:
        id_of[p.sku_id] = next_id
        next_id += 1

    catalog_products = []
    for r in devices + consumables + others:
        is_device = r.category in ("device", "hardware")
        is_consumable = r.category in ("consumable", "consumables")
        min_price = to_number(r.min_price)
        catalog_products.append(
            {
                "id": id_of[r.sku_id],
                "name": r.name,
                "category": r.category,
                "sku": r.sku_id,
                "price": min_price if min_price is not None else 0,
                "minPrice": min_price,
                "maxPrice": to_number(r.max_price),
                "unit": r.unit,
                "bagsPerBox": to_number(r.units_per_box) if to_number(r.units_per_box) is not None else 1,
                "piecesPerBag": to_number(r.pieces_per_unit) if to_number(r.pieces_per_unit) is not None else 1,
                "image": r.image or "",
                "boundConsumables": (
                    [id_of[s] for s in bound_consumable_skus(db, r.sku_id) if s in id_of]
                    if is_device
                    else []
                ),
                "spec": r.spec or ("医用级治疗设备" if is_device else ("医用级耗材" if is_consumable else "标准规格")),
                "power": r.spec or ("临床治疗" if is_device else ("医用级耗材" if is_consumable else "通用产品")),
                "desc": (
                    r.remark
                    or (
                        "适用于各级医疗机构的康复理疗、疼痛管理与临床治疗场景。"
                        if is_device
                        else (
                            "适配相应治疗设备的一次性医用耗材，采用医用级材质。"
                            if is_consumable
                            else (r.name or "")
                        )
                    )
                ),
                "tags": (
                    ["治疗设备", "价格表"]
                    if is_device
                    else (["医用耗材", "价格表"] if is_consumable else [r.category, "价格表"])
                ),
                "plan2Price": None,
                "tiers": [],
            }
        )

    device_sku_set = {d.sku_id for d in devices}
    packages = []
    for p in db.scalars(select(Package).order_by(Package.package_id.asc())).all():
        sku_ids = json.loads(p.sku_ids or "[]")
        raw_quantities = json.loads(p.quantities or "[]")
        device_ids: list[int] = []
        consumable_ids: list[int] = []
        items: list[dict] = []
        for i, sku in enumerate(sku_ids):
            pid = id_of.get(sku)
            product = product_by_sku.get(sku)
            if pid is None or product is None:
                continue
            qty = to_number(raw_quantities[i]) if i < len(raw_quantities) else None
            item = {
                "productId": pid,
                "id": pid,
                "sku": product.sku_id,
                "category": product.category,
                "name": product.name,
                "quantity": qty,
                "unit": product.unit,
                "bagsPerBox": to_number(product.units_per_box),
            }
            items.append(item)
            if sku in device_sku_set:
                device_ids.append(pid)
            else:
                consumable_ids.append(pid)
        price = effective_package_price(p)
        packages.append(
            {
                "id": p.package_id,
                "packageId": p.package_id,
                "name": p.name,
                "deviceId": device_ids[0] if device_ids else None,
                "consumableIds": consumable_ids,
                "deviceIds": device_ids,
                "deviceQty": to_number(p.device_qty),
                "consumableQty": to_number(p.consumable_qty),
                "consumableBoxes": to_number(p.consumable_boxes),
                "price": price,
                "stdPrice": to_number(p.std_price),
                "discountPrice": to_number(p.discount_price),
                "discountRate": p.discount_rate,
                "devicePrice": to_number(p.device_price),
                "fixedBundle": bool(p.fixed_bundle),
                "note": p.note,
                "items": items,
            }
        )

    return {"products": catalog_products, "packages": packages}


# ---------- Redis 缓存管理 ----------

CATALOG_CACHE_KEY = "quote:catalog:data"
CATALOG_CACHE_TTL = 3600


async def get_cached_catalog(db: Session) -> dict:
    """获取产品与套餐目录。

    优先从 Redis 键 quote:catalog:data 读取（TTL 3600 秒）；
    若未命中或 Redis 服务不可用，则安全降级走数据库构建并异步回写缓存。
    """
    redis = None
    try:
        redis = await get_redis()
        if redis is not None:
            cached = await redis.get(CATALOG_CACHE_KEY)
            if cached:
                return json.loads(cached)
    except Exception as e:
        logger.warning("Error reading catalog cache from Redis: %s", e)

    data = build_catalog(db)

    try:
        if redis is not None:
            await redis.set(CATALOG_CACHE_KEY, json.dumps(data, ensure_ascii=False), ex=CATALOG_CACHE_TTL)
    except Exception as e:
        logger.warning("Error writing catalog cache to Redis: %s", e)

    return data


async def invalidate_catalog_cache() -> None:
    """主动使目录缓存失效（在商品、套餐或绑定增删改后调用）。"""
    try:
        redis = await get_redis()
        if redis is not None:
            await redis.delete(CATALOG_CACHE_KEY)
    except Exception as e:
        logger.warning("Error invalidating catalog cache in Redis: %s", e)

