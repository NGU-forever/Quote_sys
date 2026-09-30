"""app_settings 读取/写入 + 同步负载构建。"""
import hashlib
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.services.catalog_service import build_catalog

DEFAULT_COMPANY = {
    "name": "超声医疗报价平台",
    "phone": "400-800-1026",
    "email": "quote@ultrasound-med.cn",
    "address": "上海市徐汇区医疗科技园",
}

DEFAULT_PRICING = {
    "devicePrice": 3200,
    "bagsPerBox": 600,
    "giftRatio": 2,
    "plan2UnitPrice": 5.5,
    "plan2MinBoxes": 2,
    "quoteValidityDays": 30,
    "quotePrefix": "Q",
    "plan1Tiers": [
        {"minBoxes": 1, "price": 3.5, "label": "1箱起订"},
        {"minBoxes": 5, "price": 3.0, "label": "5箱起订"},
        {"minBoxes": 10, "price": 2.5, "label": "10箱起订"},
    ],
}


def _read_map(db: Session) -> dict[str, str]:
    return {s.key: s.value for s in db.scalars(select(AppSetting)).all()}


def get_settings_dict(db: Session) -> dict:
    """读取 company + pricing；缺失时回退内置默认值（不强制写入库）。"""
    rows = _read_map(db)
    company = json.loads(rows["company"]) if "company" in rows else DEFAULT_COMPANY
    pricing = json.loads(rows["pricing"]) if "pricing" in rows else DEFAULT_PRICING
    return {"company": company, "pricing": pricing}


def put_settings(db: Session, company: dict | None, pricing: dict | None) -> dict:
    """整体替换 company / pricing（传入 None 表示该项不更新）。"""
    if company is not None:
        db.merge(AppSetting(key="company", value=json.dumps(company, ensure_ascii=False)))
    if pricing is not None:
        db.merge(AppSetting(key="pricing", value=json.dumps(pricing, ensure_ascii=False)))
    db.commit()
    return get_settings_dict(db)


def build_sync_payload(db: Session) -> dict:
    """客户机同步负载：catalog + settings + 内容哈希 rev + updated_at。"""
    payload = {"catalog": build_catalog(db), "settings": get_settings_dict(db)}
    rev = hashlib.sha1(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {**payload, "rev": rev, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
