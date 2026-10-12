"""设计器后端 API 路由。

实现端点：
- POST  /api/designer/signals       计算画像指标、来源级别与排序结果
- POST  /api/designer/preview       生成指定预设包的预览 Spec
- POST  /api/designer/compile       汇总向导答案生成正式 Spec 与校验报告
- POST  /api/designer/finalize      定稿写入 ui_specs 冻结
- GET   /api/designer/spec          读取当前生效 Spec
- PATCH /api/designer/spec          三类微调（modules / columns / preset_id）
- POST  /api/designer/spec/rollback 回退上一版本微调
- POST  /api/designer/reset         逃生舱：重置 Spec
"""
import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_user
from app.designer.compiler import compile_wizard_to_spec
from app.designer.presets import build_preview_spec_draft
from app.designer.ranking import determine_source_level, rank_preview_presets
from app.designer.sampler import sample_preview_data
from app.designer.signals import compute_signals
from app.designer.validator import validate_and_repair_spec
from app.models.ui_designer import UiSpec, UiSpecRevision
from app.models.user import User

router = APIRouter(prefix="/api/designer", tags=["designer"])


def _require_admin(user: User = Depends(require_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


class PreviewRequest(BaseModel):
    preset_id: str = "order-entry"


class CompileRequest(BaseModel):
    answers: Dict[str, Any]


class FinalizeRequest(BaseModel):
    spec: Dict[str, Any]


class PatchSpecRequest(BaseModel):
    preset_id: Optional[str] = None
    modules: Optional[list] = None
    columns: Optional[Dict[str, list]] = None


@router.post("/signals")
def get_signals_and_ranking(
    db: Session = Depends(get_db),
    user: User = Depends(_require_admin),
):
    signals = compute_signals(db)
    source_level = determine_source_level(signals)
    ranking = rank_preview_presets(signals)
    sample_data = sample_preview_data(db, source_level=source_level)

    return {
        "signals": signals,
        "ranking": ranking,
        "source_level": source_level,
        "sample_data": sample_data,
    }


@router.post("/preview")
def get_preset_preview_spec(
    req: PreviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(_require_admin),
):
    signals = compute_signals(db)
    source_level = determine_source_level(signals)
    spec_draft = build_preview_spec_draft(req.preset_id, source_level=source_level)
    return {"spec": spec_draft}


@router.post("/compile")
def compile_spec(
    req: CompileRequest,
    db: Session = Depends(get_db),
    user: User = Depends(_require_admin),
):
    signals = compute_signals(db)
    source_level = determine_source_level(signals)
    spec, issues = compile_wizard_to_spec(req.answers, signals, source_level=source_level)
    return {"spec": spec, "issues": issues}


@router.post("/finalize")
def finalize_spec(
    req: FinalizeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(_require_admin),
):
    validated_spec, issues = validate_and_repair_spec(req.spec)
    source_level = validated_spec.get("meta", {}).get("source_level", "database")

    # 冻结并置为激活，同时间仅允许一条 active
    db.execute(update(UiSpec).values(is_active=False))

    new_spec = UiSpec(
        spec_version=validated_spec.get("spec_version", 1),
        payload_json=json.dumps(validated_spec, ensure_ascii=False),
        source_level=source_level,
        finalized_by=user.id,
        is_active=True,
    )
    db.add(new_spec)
    db.commit()
    db.refresh(new_spec)

    return {
        "success": True,
        "spec_id": new_spec.id,
        "issues": issues,
    }


@router.get("/spec")
def get_active_spec(
    db: Session = Depends(get_db),
):
    active_spec = db.scalar(select(UiSpec).where(UiSpec.is_active == True).limit(1))  # noqa: E712
    if not active_spec:
        raise HTTPException(status_code=404, detail="尚未定稿任何生效 Spec")

    return {
        "id": active_spec.id,
        "spec_version": active_spec.spec_version,
        "source_level": active_spec.source_level,
        "payload": json.loads(active_spec.payload_json),
        "finalized_at": active_spec.finalized_at,
    }


@router.patch("/spec")
def patch_spec(
    patch: PatchSpecRequest,
    db: Session = Depends(get_db),
    user: User = Depends(_require_admin),
):
    active_spec = db.scalar(select(UiSpec).where(UiSpec.is_active == True).limit(1))  # noqa: E712
    if not active_spec:
        raise HTTPException(status_code=404, detail="尚未定稿任何生效 Spec")

    payload = json.loads(active_spec.payload_json)

    # 记录版本变更快照
    revision = UiSpecRevision(
        spec_id=active_spec.id,
        patch_json=json.dumps(payload, ensure_ascii=False),
    )
    db.add(revision)

    # 三类安全微调
    if patch.preset_id:
        payload["style"]["preset_id"] = patch.preset_id
    if patch.modules is not None:
        payload["modules"] = patch.modules
    if patch.columns is not None and "entities" in payload:
        for ent, cols in patch.columns.items():
            if ent in payload["entities"]:
                payload["entities"][ent]["list_columns"] = cols

    # 重新校验
    repaired, _ = validate_and_repair_spec(payload)
    active_spec.payload_json = json.dumps(repaired, ensure_ascii=False)
    db.commit()

    return {"success": True}


@router.post("/spec/rollback")
def rollback_spec(
    db: Session = Depends(get_db),
    user: User = Depends(_require_admin),
):
    active_spec = db.scalar(select(UiSpec).where(UiSpec.is_active == True).limit(1))  # noqa: E712
    if not active_spec:
        raise HTTPException(status_code=404, detail="尚未定稿任何生效 Spec")

    latest_rev = db.scalar(
        select(UiSpecRevision)
        .where(UiSpecRevision.spec_id == active_spec.id)
        .order_by(UiSpecRevision.id.desc())
        .limit(1)
    )
    if not latest_rev:
        raise HTTPException(status_code=400, detail="无历史版本可供回退")

    active_spec.payload_json = latest_rev.patch_json
    db.delete(latest_rev)
    db.commit()

    return {"success": True}


@router.post("/reset")
def reset_designer(
    db: Session = Depends(get_db),
    user: User = Depends(_require_admin),
):
    # 逃生舱：重置 Spec，不动任何业务数据
    db.execute(update(UiSpec).values(is_active=False))
    db.commit()
    return {"success": True, "message": "已成功重置设计器"}
