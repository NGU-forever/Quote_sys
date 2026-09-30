"""LLM 调用计量：每次模型调用的 token、耗时与成本明细（只新增表）。

不修改 import_runs 现有列，成本/耗时通过本表聚合得到，避免历史库需要迁移。
"""

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, now_str


class LlmCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    # 产生该次调用的图节点（profiler_node / extract_products_node / correction_node ...）
    node: Mapped[str] = mapped_column(String(48), nullable=False, default="")
    provider: Mapped[str] = mapped_column(String(24), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(96), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")

    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="")

    created_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str)
