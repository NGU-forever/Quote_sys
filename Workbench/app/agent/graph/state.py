"""Shared state for the LangGraph Workbench data generation agent."""
import operator
from typing import Annotated, TypedDict


class AgentGraphState(TypedDict, total=False):
    """Serializable state passed between graph nodes."""

    run_id: int
    mode: str
    manifest: dict
    db_stats: dict
    sources_plan: dict
    products_extracted: list[dict]
    packages_extracted: list[dict]
    bindings_extracted: list[dict]
    issues: Annotated[list[str], operator.add]
    candidates: dict | None
    validation_errors: list[str]
    retry_count: int
    status: str
    apply_result: dict
    report: dict
    # 工具循环轨迹（用于落运行事件，让 ReAct 过程可审计）
    react_trace: Annotated[list[dict], operator.add]
