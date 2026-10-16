"""资料 → 业务画像（M4）。

画像来源三级（与第 0 屏预览数据源同构）：
1. 现有库统计（signals）——永远可用；
2. assets 目录里的资料片段——文本类文件取前若干字符；
3. 可选的模型判断——把 1+2 交给 LLM 做行业/口径判断，失败或未配置时**完全走规则**。

规则优先是硬要求：不配 API Key 也必须能出完整画像（设计文档 §2 D3）。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agent.readers.common import safe_file_path
from app.agent.readers.manifest import build_manifest
from app.designer.llm import enrich_spec_with_llm
from app.designer.signals import compute_signals
from app.designer.terminology import detect_price_term, detect_promo_tone

TEXT_EXCERPT_CHARS = 600
MAX_ASSETS = 8


def collect_assets_digest() -> list[dict]:
    """assets 清单 + 文本类资料片段；读取失败静默跳过，不影响出图。"""
    try:
        manifest = build_manifest()
    except Exception:
        return []

    entries: list[dict] = []
    for item in manifest.get("files", []):
        if not item.get("supported"):
            continue
        entry: dict[str, Any] = {"path": item.get("path"), "type": item.get("type")}
        if item.get("type") == "text":
            try:
                entry["excerpt"] = safe_file_path(item["path"]).read_text(
                    encoding="utf-8-sig", errors="replace"
                )[:TEXT_EXCERPT_CHARS]
            except Exception:
                pass
        entries.append(entry)
        if len(entries) >= MAX_ASSETS:
            break
    return entries


def build_digest(db: Session) -> dict:
    """汇总画像输入：库内统计 + 资料片段 + 术语线索。"""
    signals = compute_signals(db)
    assets = collect_assets_digest()
    texts = [item.get("excerpt") or "" for item in assets]
    texts.extend([item.get("path") or "" for item in assets])
    price_term, price_counts = detect_price_term(texts)
    promo = detect_promo_tone(texts)
    return {
        "signals": signals,
        "assets": assets,
        "terminology_hints": {
            "price_term": price_term,
            "price_term_counts": price_counts,
            "promo_tone": promo,
        },
        "price_term": price_term,
        "promo": promo,
    }


def rule_based_profile(digest: dict) -> dict:
    """纯规则画像：任何环境都能算出结果。"""
    signals = digest.get("signals") or {}
    total = int(signals.get("product_count") or 0)
    consumable_ratio = float(signals.get("consumable_ratio") or 0.0)

    if total == 0:
        sell_mode = "device_with_consumable"
    elif consumable_ratio >= 0.9:
        sell_mode = "consumable_only"
    elif consumable_ratio <= 0.1:
        sell_mode = "device_only"
    else:
        sell_mode = "device_with_consumable"

    pricing_mode = "negotiable" if signals.get("has_negotiable") else "floor_price"
    scene = "on_site"
    if int(signals.get("quote_count") or 0) > 200 and int(signals.get("sales_count") or 0) > 1:
        scene = "office"

    roles = ["admin"]
    if int(signals.get("sales_count") or 0) > 1 or total > 0:
        roles.append("sales")

    return {
        "industry": "medical",
        "sell_mode": sell_mode,
        "scene": scene,
        "pricing_mode": pricing_mode,
        "roles": roles,
        "output_targets": ["print_a4"],
        "category_name": "主要设备与配件",
    }


def resolve_profile(
    db: Session,
    provider: Any = None,
    digest: dict | None = None,
) -> tuple[dict, list[str], dict]:
    """返回 (profile, issues, digest)。

    provider 为 None（未配置模型 / 离线 / 测试环境）时直接返回规则画像。
    """
    digest = digest or build_digest(db)
    base = rule_based_profile(digest)
    if provider is None:
        return base, [], digest

    # 复用带三道门与有界自愈的增强管线，只取其中的 profile 部分
    seed_spec = {
        "spec_version": 1,
        "profile": base,
        "style": {"preset_id": "medical-clean", "density": "comfortable"},
        "modules": ["quote_editor"],
        "screens": [],
        "entities": {},
    }
    enriched, issues, _attempts = enrich_spec_with_llm(seed_spec, digest, provider)
    profile = enriched.get("profile") or base
    for key, value in base.items():
        profile.setdefault(key, value)
    return profile, issues, digest
