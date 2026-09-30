"""Agent 计量：LLM 调用成本折算与运行级汇总。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.llm_call import LlmCall


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """按配置的百万 token 单价折算成本；未配置单价时返回 0。"""
    return round(
        (max(0, prompt_tokens) / 1_000_000) * settings.llm_input_price_per_1m
        + (max(0, completion_tokens) / 1_000_000) * settings.llm_output_price_per_1m,
        6,
    )


def record_llm_call(
    db: Session,
    *,
    run_id: int,
    node: str,
    provider: str,
    model: str,
    prompt_version: str,
    usage: dict | None,
    latency_ms: int,
) -> None:
    """写入一次 LLM 调用明细。用量缺失（离线 Mock / 网关不返回 usage）按 0 计。"""
    usage = usage or {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
    db.add(
        LlmCall(
            run_id=run_id,
            node=node,
            provider=provider,
            model=model or "",
            prompt_version=prompt_version,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=max(0, int(latency_ms)),
            cost=estimate_cost(prompt_tokens, completion_tokens),
            currency=settings.llm_price_currency if (prompt_tokens or completion_tokens) else "",
        )
    )
    db.commit()


def summarize_run_llm(db: Session, run_id: int) -> dict:
    """聚合某次运行的 LLM 用量：总 token / 总耗时 / 总成本 + 分节点明细。"""
    rows = db.execute(
        select(
            LlmCall.node,
            func.count(LlmCall.id),
            func.coalesce(func.sum(LlmCall.prompt_tokens), 0),
            func.coalesce(func.sum(LlmCall.completion_tokens), 0),
            func.coalesce(func.sum(LlmCall.total_tokens), 0),
            func.coalesce(func.sum(LlmCall.latency_ms), 0),
            func.coalesce(func.sum(LlmCall.cost), 0.0),
        )
        .where(LlmCall.run_id == run_id)
        .group_by(LlmCall.node)
    ).all()

    per_node = [
        {
            "node": node,
            "calls": int(calls),
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "total_tokens": int(total_tokens),
            "latency_ms": int(latency_ms),
            "cost": round(float(cost), 6),
        }
        for node, calls, prompt_tokens, completion_tokens, total_tokens, latency_ms, cost in rows
    ]
    per_node.sort(key=lambda item: item["node"])
    return {
        "calls": sum(item["calls"] for item in per_node),
        "prompt_tokens": sum(item["prompt_tokens"] for item in per_node),
        "completion_tokens": sum(item["completion_tokens"] for item in per_node),
        "total_tokens": sum(item["total_tokens"] for item in per_node),
        "latency_ms": sum(item["latency_ms"] for item in per_node),
        "cost": round(sum(item["cost"] for item in per_node), 6),
        "currency": settings.llm_price_currency,
        "per_node": per_node,
    }
