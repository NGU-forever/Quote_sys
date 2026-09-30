"""数据生成 Agent 运行记录（只新增表，不改动现有业务表）。"""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, now_str


class ImportRun(Base):
    __tablename__ = "import_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)  # dry-run / apply
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="inventory")
    provider: Mapped[str] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    products_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    packages_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bindings_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    products_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    packages_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    packages_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    packages_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bindings_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bindings_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    candidates_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str)
    started_at: Mapped[str | None] = mapped_column(String, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String, nullable=True)
