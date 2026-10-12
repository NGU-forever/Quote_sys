"""设计器数据模型。

包含 5 张表：
1. ui_spec_drafts: 草稿（定稿前的尝试，可随时丢弃）
2. ui_specs: 正式定稿（冻结，同一时刻仅允许一个 active）
3. ui_signal_snapshots: 画像快照（复现与回归）
4. ui_style_presets: 风格包（内置与扩展 Token）
5. ui_spec_revisions: 定稿后的三类微调历史（可回退）
"""
from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, now_str


class UiSpecDraft(Base):
    __tablename__ = "ui_spec_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    signals_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview_preset: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_str)


class UiSpec(Base):
    __tablename__ = "ui_specs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    spec_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_level: Mapped[str] = mapped_column(String(16), nullable=False)  # database / assets / sample
    finalized_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finalized_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_str)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class UiSignalSnapshot(Base):
    __tablename__ = "ui_signal_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draft_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sales_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consumable_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    binding_density: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_str)


class UiStylePreset(Base):
    __tablename__ = "ui_style_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    preset_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    tokens_json: Mapped[str] = mapped_column(Text, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_str)


class UiSpecRevision(Base):
    __tablename__ = "ui_spec_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    spec_id: Mapped[int] = mapped_column(Integer, nullable=False)
    patch_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_str)
