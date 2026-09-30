"""数据生成 Agent API（/api/agent，登录保护）。"""
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent import agent_service
from app.agent.readers.common import safe_file_path
from app.agent.readers.manifest import build_manifest
from app.core.config import settings
from app.core.deps import get_db, require_user
from app.models.import_run import ImportRun
from app.models.user import User
from app.services.agent_config_service import get_agent_ai, get_agent_ai_public, put_agent_ai

router = APIRouter(prefix="/agent")


class StartRunRequest(BaseModel):
    mode: str | None = Field(default=None, pattern="^(dry-run|apply)$")
    note: str | None = Field(default=None, max_length=200)


class ApplyRunPayload(BaseModel):
    candidates: dict | None = None


class AgentConfigUpdate(BaseModel):
    provider: str | None = Field(default=None, pattern="^(auto|openai|mock)$")
    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=200)
    api_key: str | None = Field(default=None, max_length=500)
    max_steps: int | None = Field(default=None, ge=1, le=100)
    default_mode: str | None = Field(default=None, pattern="^(dry-run|apply)$")


@router.get("/assets")
def list_assets(_: User = Depends(require_user)):
    return {"data": build_manifest()}


@router.get("/config")
def read_agent_config(db: Session = Depends(get_db), _: User = Depends(require_user)):
    return {"data": get_agent_ai_public(db)}


@router.put("/config")
def write_agent_config(
    payload: AgentConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_user),
):
    try:
        data = put_agent_ai(
            db,
            provider=payload.provider,
            base_url=payload.base_url,
            model=payload.model,
            api_key=payload.api_key,
            max_steps=payload.max_steps,
            default_mode=payload.default_mode,
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": data}


@router.get("/assets/status")
def assets_status(_: User = Depends(require_user)):
    manifest = build_manifest()
    return {
        "data": {
            "supported_count": manifest["supported_count"],
            "unsupported_count": manifest["unsupported_count"],
            "scanned_at": manifest["scanned_at"],
            "files": manifest["files"],
            "root_path": manifest.get("root_path"),
        }
    }


@router.post("/assets/upload")
async def upload_asset(
    file: UploadFile = File(...),
    _: User = Depends(require_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    ext = Path(file.filename).suffix.lower()
    if ext not in {".xlsx", ".docx", ".csv", ".md", ".txt"}:
        raise HTTPException(
            status_code=400,
            detail="仅支持上传 .xlsx / .docx / .csv / .md / .txt 格式的源资料文件",
        )
    clean_name = Path(file.filename).name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="非法文件名")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 50MB")

    target_dir = settings.assets_root
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / clean_name
    target_path.write_bytes(content)
    return {"data": build_manifest()}


@router.delete("/assets/{filename:path}")
def delete_asset(
    filename: str,
    _: User = Depends(require_user),
):
    try:
        path = safe_file_path(filename)
        path.unlink(missing_ok=False)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": build_manifest()}


@router.get("/runs")
def list_runs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_user),
):
    runs = db.scalars(
        select(ImportRun).order_by(ImportRun.id.desc()).limit(limit)
    ).all()
    return {"data": [agent_service.run_to_dict(db, r) for r in runs]}


@router.post("/runs", status_code=201)
def start_run(
    payload: StartRunRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    if agent_service.has_active_run():
        raise HTTPException(status_code=409, detail="已有 Agent 任务正在运行，请稍候")
    body = payload or StartRunRequest()
    mode = body.mode or get_agent_ai(db)["default_mode"]
    if mode not in {"dry-run", "apply"}:
        raise HTTPException(status_code=400, detail="mode 只允许 dry-run / apply")
    run = ImportRun(
        mode=mode,
        status="pending",
        stage="inventory",
        note=body.note,
        created_by_user_id=user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        agent_service.start_background(run.id)
    except RuntimeError as exc:
        pending = db.get(ImportRun, run.id)
        if pending is not None:
            db.delete(pending)
            db.commit()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"data": agent_service.run_to_dict(db, run)}


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db), _: User = Depends(require_user)):
    run = db.get(ImportRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return {"data": agent_service.run_to_dict(db, run)}


@router.post("/runs/{run_id}/resume")
def resume_run(run_id: int, db: Session = Depends(get_db), _: User = Depends(require_user)):
    """从检查点续跑中断的运行（进程重启/异常中断后不必从头再来）。"""
    run = db.get(ImportRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    if run.status == "running":
        raise HTTPException(status_code=409, detail="该任务仍在运行中")
    if agent_service.has_active_run():
        raise HTTPException(status_code=409, detail="已有 Agent 任务正在运行，请稍候")
    try:
        agent_service.start_background(run_id, resume=True)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.refresh(run)
    return {"data": agent_service.run_to_dict(db, run)}


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: int, db: Session = Depends(get_db), _: User = Depends(require_user)):
    run = db.get(ImportRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    if run.status not in {"pending", "running"}:
        raise HTTPException(status_code=409, detail="当前任务已结束，不能取消")
    if agent_service.request_cancel(run_id):
        return {"data": {"ok": True, "status": "cancelling"}}
    # 线程尚未登记（极短窗口）：直接把状态置为 cancelled，避免界面一直轮询
    if run.status == "pending":
        run.status = "cancelled"
        run.stage = "cancelled"
        db.commit()
        return {"data": {"ok": True, "status": "cancelled"}}
    raise HTTPException(status_code=409, detail="任务已进入收尾阶段，无法取消")


@router.post("/runs/{run_id}/retry", status_code=201)
def retry_run(
    run_id: int,
    payload: StartRunRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    original = db.get(ImportRun, run_id)
    if original is None:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    if agent_service.has_active_run():
        raise HTTPException(status_code=409, detail="已有 Agent 任务正在运行，请稍候")
    body = payload or StartRunRequest()
    mode = body.mode or original.mode or get_agent_ai(db)["default_mode"]
    run = ImportRun(
        mode=mode,
        status="pending",
        stage="inventory",
        note=body.note or f"重试 #{original.id}：{original.note or ''}".strip() or None,
        created_by_user_id=user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        agent_service.start_background(run.id)
    except RuntimeError as exc:
        pending = db.get(ImportRun, run.id)
        if pending is not None:
            db.delete(pending)
            db.commit()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"data": agent_service.run_to_dict(db, run)}


@router.post("/runs/{run_id}/apply")
def apply_run(
    run_id: int,
    payload: ApplyRunPayload | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_user),
):
    run = db.get(ImportRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    if agent_service.has_active_run():
        raise HTTPException(status_code=409, detail="已有 Agent 任务正在运行，请稍候")
    candidates_override = payload.candidates if payload else None
    try:
        return {"data": agent_service.apply_saved_run(db, run_id, candidates_override=candidates_override)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"入库失败：{exc}") from exc

