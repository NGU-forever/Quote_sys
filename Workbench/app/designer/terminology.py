"""行业术语本地化：同一字段在不同行业叫法不同。

设计文档 §9.1 D 组：资料里出现"底价 / 供货价 / 同行价 / 批发价"时，
min_price 的界面标签应随行业口径变化，而不是永远叫"最低底价"。

规则优先（离线可用），LLM 只是可选增强（见 llm.py）。
"""
from __future__ import annotations

from typing import Iterable

# 口径关键词 → min_price 的界面标签
PRICE_TERM_LABELS = {
    "底价": "最低底价",
    "供货价": "供货价",
    "同行价": "同行价",
    "批发价": "批发价",
    "出厂价": "出厂价",
    "经销价": "经销价",
}

DEFAULT_PRICE_LABEL = "最低底价"

# 促销语气关键词（影响套餐区块文案与"省 ¥X"展示）
PROMO_TERMS = ("赠机", "买赠", "满赠", "整购", "买x赠y", "特价", "促销")


def detect_price_term(texts: Iterable[str]) -> tuple[str, dict]:
    """从资料文本里按词频挑选价格口径词。

    返回 (命中词, 全部词频)；无命中时返回 ("", {})。
    """
    counts: dict[str, int] = {}
    for text in texts:
        if not text:
            continue
        content = str(text)
        for term in PRICE_TERM_LABELS:
            hits = content.count(term)
            if hits:
                counts[term] = counts.get(term, 0) + hits
    if not counts:
        return "", {}
    term = max(counts.items(), key=lambda item: item[1])[0]
    return term, counts


def detect_promo_tone(texts: Iterable[str]) -> bool:
    """资料里是否出现明显促销语气。"""
    blob = " ".join(str(t) for t in texts if t)
    return any(term in blob for term in PROMO_TERMS)


def localize_field_labels(price_term: str = "", promo: bool = False) -> dict:
    """按价格口径返回字段标签表（供 spec.entities.*.labels 使用）。"""
    price_label = PRICE_TERM_LABELS.get(price_term, DEFAULT_PRICE_LABEL)
    labels = {
        "product": {
            "min_price": price_label,
            "max_price": "最高价",
            "box_price": "整箱价",
        },
        "quote": {
            "quote_no": "单号",
            "sales_name": "业务员",
        },
    }
    if promo:
        labels["product"]["raw_price_desc"] = "促销口径"
    return labels


def merge_labels(base: dict, override: dict) -> dict:
    """把 LLM 给出的标签覆盖到规则标签上（按实体合并）。"""
    merged = {entity: dict(fields) for entity, fields in (base or {}).items()}
    for entity, fields in (override or {}).items():
        if not isinstance(fields, dict):
            continue
        merged.setdefault(entity, {})
        for key, value in fields.items():
            if value:
                merged[entity][str(key)] = str(value)
    return merged
