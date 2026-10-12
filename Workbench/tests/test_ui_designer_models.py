"""测试设计器新增的 5 张 ORM 数据模型。

包含：
- UiSpecDraft (草稿)
- UiSpec (正式冻结 Spec)
- UiSignalSnapshot (画像快照)
- UiStylePreset (风格包)
- UiSpecRevision (微调历史)
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base


@pytest.fixture
def db_session():
    """提供独立的 SQLite 内存测试会话，自包含且无需外部数据库。"""
    engine = create_engine("sqlite:///:memory:", future=True)
    # 动态导入确保 Base.metadata 收集到全部模型
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_ui_designer_models_exist():
    from app.models.ui_designer import (
        UiSpecDraft,
        UiSpec,
        UiSignalSnapshot,
        UiStylePreset,
        UiSpecRevision,
    )

    assert UiSpecDraft.__tablename__ == "ui_spec_drafts"
    assert UiSpec.__tablename__ == "ui_specs"
    assert UiSignalSnapshot.__tablename__ == "ui_signal_snapshots"
    assert UiStylePreset.__tablename__ == "ui_style_presets"
    assert UiSpecRevision.__tablename__ == "ui_spec_revisions"


def test_ui_spec_draft_crud(db_session):
    from app.models.ui_designer import UiSpecDraft

    draft = UiSpecDraft(
        created_by=1,
        payload_json='{"spec_version": 1}',
        signals_json='{"product_count": 10}',
        preview_preset="medical-clean",
    )
    db_session.add(draft)
    db_session.commit()

    saved = db_session.get(UiSpecDraft, draft.id)
    assert saved is not None
    assert saved.created_by == 1
    assert saved.preview_preset == "medical-clean"
    assert "spec_version" in saved.payload_json


def test_ui_spec_crud(db_session):
    from app.models.ui_designer import UiSpec

    spec = UiSpec(
        spec_version=1,
        payload_json='{"spec_version": 1, "screens": []}',
        source_level="database",
        finalized_by=1,
        finalized_at="2026-10-12 20:00:00",
        is_active=True,
    )
    db_session.add(spec)
    db_session.commit()

    saved = db_session.get(UiSpec, spec.id)
    assert saved is not None
    assert saved.spec_version == 1
    assert saved.source_level == "database"
    assert saved.is_active is True


def test_ui_style_preset_crud(db_session):
    from app.models.ui_designer import UiStylePreset

    preset = UiStylePreset(
        preset_id="medical-clean",
        name="医疗洁净",
        tokens_json='{"color.primary": "#0B5FA5"}',
        is_builtin=True,
    )
    db_session.add(preset)
    db_session.commit()

    saved = db_session.query(UiStylePreset).filter_by(preset_id="medical-clean").first()
    assert saved is not None
    assert saved.name == "医疗洁净"
    assert saved.is_builtin is True


def test_ui_signal_snapshot_crud(db_session):
    from app.models.ui_designer import UiSignalSnapshot

    snapshot = UiSignalSnapshot(
        draft_id=1,
        product_count=30,
        quote_count=15,
        sales_count=2,
        consumable_ratio=0.67,
        binding_density=1.2,
        payload_json='{"sample": true}',
    )
    db_session.add(snapshot)
    db_session.commit()

    saved = db_session.get(UiSignalSnapshot, snapshot.id)
    assert saved is not None
    assert saved.product_count == 30
    assert saved.consumable_ratio == pytest.approx(0.67, 0.01)


def test_ui_spec_revision_crud(db_session):
    from app.models.ui_designer import UiSpecRevision

    rev = UiSpecRevision(
        spec_id=1,
        patch_json='{"modules": ["catalog", "quotes"]}',
    )
    db_session.add(rev)
    db_session.commit()

    saved = db_session.get(UiSpecRevision, rev.id)
    assert saved is not None
    assert saved.spec_id == 1
    assert "catalog" in saved.patch_json
