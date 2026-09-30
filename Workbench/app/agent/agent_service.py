"""LangGraph 状态图运行状态机、后台执行与报告。"""
import json
import logging
import threading

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent import persistence, validation
from app.agent.graph.builder import build_import_graph
from app.agent.graph.config import get_checkpointer
from app.agent.graph.runtime import AgentCancelled, GraphRuntime
from app.agent.llm_client import OpenAICompatibleClient
from app.agent.metrics import record_llm_call, summarize_run_llm
from app.agent.mock_provider import MockProvider
from app.core.config import settings
from app.db.base import SessionLocal, now_str
from app.models.device_binding import DeviceBinding
from app.models.import_run import ImportRun
from app.models.import_run_event import ImportRunEvent
from app.models.package import Package
from app.models.product import Product
from app.services.agent_config_service import get_agent_ai

logger = logging.getLogger(__name__)


_lock = threading.Lock()
_active: set[int] = set()
_cancel_events: dict[int, threading.Event] = {}


class _RunNotFound(Exception):
    pass


def try_claim_run(run_id: int) -> bool:
    with _lock:
        if _active:
            return False
        _active.add(run_id)
        _cancel_events[run_id] = threading.Event()
        return True


def release_run(run_id: int) -> None:
    with _lock:
        _active.discard(run_id)
        _cancel_events.pop(run_id, None)


def has_active_run() -> bool:
    with _lock:
        return bool(_active)


def request_cancel(run_id: int) -> bool:
    with _lock:
        event = _cancel_events.get(run_id)
        if event is None:
            return False
        event.set()
        return True


def is_cancelled(run_id: int) -> bool:
    with _lock:
        event = _cancel_events.get(run_id)
        return bool(event and event.is_set())


def start_background(run_id: int, resume: bool = False) -> None:
    if not try_claim_run(run_id):
        raise RuntimeError("已有 Agent 任务正在运行")

    def runner():
        try:
            execute_run(run_id, resume=resume)
        finally:
            release_run(run_id)

    threading.Thread(target=runner, name=f"agent-run-{run_id}", daemon=True).start()


def _load_run(db: Session, run_id: int) -> ImportRun:
    run = db.get(ImportRun, run_id)
    if run is None:
        raise _RunNotFound(f"运行记录不存在：{run_id}")
    return run


def _append_event(db: Session, run_id: int, step: int, role: str, tool: str | None, summary: str) -> None:
    db.add(
        ImportRunEvent(
            run_id=run_id,
            step=step,
            role=role,
            tool=tool,
            summary=summary[:600],
        )
    )
    db.commit()


def _update_run(db: Session, run_id: int, **fields) -> None:
    run = _load_run(db, run_id)
    for key, value in fields.items():
        setattr(run, key, value)
    db.commit()


def _provider(ai_config: dict) -> tuple[object, str]:
    explicit = str(ai_config.get("provider") or "auto").strip().lower()
    if explicit == "mock":
        return MockProvider(), "mock"
    if explicit == "openai":
        return (
            OpenAICompatibleClient(
                base_url=ai_config.get("base_url") or settings.llm_base_url,
                api_key=ai_config.get("api_key") or settings.llm_api_key,
                model=ai_config.get("model") or settings.llm_model,
            ),
            "openai",
        )
    if ai_config.get("base_url") and ai_config.get("model"):
        # provider=auto 且配置了地址+模型 ⇒ 走真实（可能计费）接口，显式告警避免误用
        logger.warning(
            "Agent provider=auto 命中真实 LLM 接口：base_url=%s model=%s（将产生真实调用与费用）",
            ai_config.get("base_url"),
            ai_config.get("model"),
        )
        return OpenAICompatibleClient(
            base_url=ai_config["base_url"],
            api_key=ai_config["api_key"],
            model=ai_config["model"],
        ), "openai"
    return MockProvider(), "mock"


def _llm_observer(run_id: int):
    """把每次模型调用的 token/耗时落到 llm_calls；计量失败不影响主流程。"""

    def observe(payload: dict) -> None:
        try:
            with SessionLocal() as metrics_db:
                record_llm_call(
                    metrics_db,
                    run_id=run_id,
                    node=str(payload.get("node") or ""),
                    provider=str(payload.get("provider") or ""),
                    model=str(payload.get("model") or ""),
                    prompt_version=settings.agent_prompt_version,
                    usage=payload.get("usage"),
                    latency_ms=int(payload.get("latency_ms") or 0),
                )
        except Exception:  # pragma: no cover - 计量属于旁路
            logger.exception("LLM 计量写入失败（已忽略）")

    return observe


def _db_stats(db: Session) -> dict:
    """库内规模统计：用 COUNT 聚合，避免把整表读进内存。"""
    total = db.scalar(select(func.count()).select_from(Product)) or 0
    devices = (
        db.scalar(
            select(func.count()).select_from(Product).where(Product.category == "device")
        )
        or 0
    )
    return {
        "products": int(total),
        "devices": int(devices),
        "consumables": int(total) - int(devices),
        "packages": int(db.scalar(select(func.count()).select_from(Package)) or 0),
        "bindings": int(db.scalar(select(func.count()).select_from(DeviceBinding)) or 0),
    }


def _result_summary(result: dict) -> str:
    return (
        f"新增商品 {result['products_added']}、更新 {result['products_updated']}、"
        f"跳过 {result['products_skipped']}；新增套餐 {result['packages_added']}、"
        f"更新 {result['packages_updated']}、跳过 {result['packages_skipped']}；"
        f"新增绑定 {result['bindings_added']}、跳过 {result['bindings_skipped']}"
    )


_NODE_ORDER = [
    "inventory_node",
    "profiler_node",
    "extract_products_node",
    "extract_packages_node",
    "extract_bindings_node",
    "reconcile_node",
    "validate_node",
    "correction_node",
    "fail_node",
    "apply_node",
    "report_node",
]

_NODE_STAGES = {
    "inventory_node": "inventory",
    "profiler_node": "profiler",
    "extract_products_node": "extract-products",
    "extract_packages_node": "extract-packages",
    "extract_bindings_node": "extract-bindings",
    "reconcile_node": "reconcile",
    "validate_node": "validate",
    "correction_node": "correction",
    "fail_node": "failed",
    "apply_node": "apply",
    "report_node": "report",
}


def _node_summary(node_name: str, state: dict) -> str:
    plan = state.get("sources_plan") or {}
    candidates = state.get("candidates") or {}
    if node_name == "inventory_node":
        manifest = state.get("manifest") or {}
        return (
            f"扫描完成：支持 {manifest.get('supported_count', 0)} 个文件，"
            f"不支持 {manifest.get('unsupported_count', 0)} 个文件"
        )
    if node_name == "profiler_node":
        return (
            "内容嗅探完成："
            f"商品来源 {len(plan.get('products') or [])}、"
            f"套餐来源 {len(plan.get('packages') or [])}、"
            f"绑定来源 {len(plan.get('bindings') or [])}"
        )
    if node_name == "extract_products_node":
        return f"商品提取完成：{len(state.get('products_extracted') or [])} 条"
    if node_name == "extract_packages_node":
        return f"套餐提取完成：{len(state.get('packages_extracted') or [])} 条"
    if node_name == "extract_bindings_node":
        return f"绑定提取完成：{len(state.get('bindings_extracted') or [])} 条"
    if node_name == "reconcile_node":
        return (
            "跨源仲裁完成："
            f"商品 {len(candidates.get('products') or [])}、"
            f"套餐 {len(candidates.get('packages') or [])}、"
            f"绑定 {len(candidates.get('bindings') or [])}"
        )
    if node_name == "validate_node":
        errors = state.get("validation_errors") or []
        return (
            "硬质检通过，进入受控入库"
            if not errors
            else f"硬质检发现 {len(errors)} 项错误：{errors[0]}"
        )
    if node_name == "correction_node":
        return f"定向自愈第 {state.get('retry_count', 0)} 轮完成"
    if node_name == "fail_node":
        return "硬质检自愈达到上限，任务失败并回滚"
    if node_name == "apply_node":
        result = state.get("apply_result") or {}
        return _result_summary(result) + (
            "（dry-run：未写正式表）"
            if state.get("mode") == "dry-run"
            else ""
        )
    if node_name == "report_node":
        return "执行报告已生成"
    return node_name


def execute_run(run_id: int, resume: bool = False) -> None:
    db = SessionLocal()
    try:
        run = _load_run(db, run_id)
        run.status = "running"
        run.stage = "inventory"
        if not resume or not run.started_at:
            run.started_at = now_str()
        run.error = None
        ai_config = get_agent_ai(db)
        provider_client, provider_name = _provider(ai_config)
        run.provider = provider_name
        run.prompt_version = settings.agent_prompt_version
        db.commit()
        _append_event(
            db,
            run_id,
            0,
            "system",
            None,
            "任务续跑：从检查点恢复" if resume else "任务启动，开始扫描 assets 目录",
        )

        runtime = GraphRuntime(
            provider=provider_client,
            provider_name=provider_name,
            db=db,
            cancel_check=lambda: is_cancelled(run_id),
            max_steps=int(ai_config.get("max_steps") or settings.llm_max_steps),
            # 离线 Mock 走确定性规则定位；真实模型才启用工具循环
            enable_tool_loop=provider_name != "mock",
            llm_observer=_llm_observer(run_id),
        )
        initial_state = {
            "run_id": run_id,
            "mode": run.mode,
            "manifest": {},
            "db_stats": _db_stats(db),
            "sources_plan": {},
            "products_extracted": [],
            "packages_extracted": [],
            "bindings_extracted": [],
            "issues": [],
            "candidates": None,
            "validation_errors": [],
            "retry_count": 0,
            "status": "running",
            "apply_result": {},
            "report": {},
        }
        step = 0
        final_state = initial_state
        config = {"configurable": {"thread_id": str(run_id)}}
        with get_checkpointer() as checkpointer:
            graph = build_import_graph(runtime, checkpointer)
            if resume:
                snapshot = graph.get_state(config)
                if not snapshot.values:
                    raise RuntimeError("该运行没有可续跑的检查点")
                if not snapshot.next:
                    raise RuntimeError("该运行的图已执行结束，没有待续跑节点")
                final_state = dict(snapshot.values)
                _append_event(
                    db,
                    run_id,
                    step,
                    "system",
                    None,
                    f"从检查点续跑，待执行节点：{'、'.join(snapshot.next)}",
                )
            for chunk in graph.stream(
                None if resume else initial_state,
                config=config,
                stream_mode="updates",
            ):
                runtime.ensure_active()
                snapshot = dict(graph.get_state(config).values or {})
                final_state = dict(snapshot)
                for node_name in _NODE_ORDER:
                    if node_name not in chunk:
                        continue
                    update = chunk[node_name]
                    update = update if isinstance(update, dict) else {}
                    event_state = {**snapshot, **update}
                    final_state.update(update)
                    if update.get("issues"):
                        final_state["issues"] = list(
                            dict.fromkeys(
                                [
                                    *(final_state.get("issues") or []),
                                    *update["issues"],
                                ]
                            )
                        )
                    step += 1
                    _update_run(
                        db,
                        run_id,
                        stage=_NODE_STAGES.get(node_name, node_name),
                    )
                    if node_name == "inventory_node":
                        run.file_count = int(
                            (event_state.get("manifest") or {}).get(
                                "supported_count",
                                0,
                            )
                        )
                        db.commit()
                    for trace_item in update.get("react_trace") or []:
                        if not isinstance(trace_item, dict):
                            continue
                        _append_event(
                            db,
                            run_id,
                            step,
                            str(trace_item.get("role") or "system"),
                            trace_item.get("tool"),
                            str(trace_item.get("summary") or ""),
                        )
                    _append_event(
                        db,
                        run_id,
                        step,
                        "report" if node_name in {"apply_node", "report_node"} else "system",
                        node_name,
                        _node_summary(node_name, event_state),
                    )

        if is_cancelled(run_id):
            raise AgentCancelled("任务已取消")
        if final_state.get("status") == "failed":
            errors = final_state.get("validation_errors") or []
            _load_run(db, run_id)
            run.status = "failed"
            run.stage = "failed"
            run.error = (
                f"候选质检在 3 次自愈后仍未通过：{'；'.join(errors[:5])}"
                if errors
                else "Agent 任务失败"
            )[:2000]
            run.report_json = json.dumps(
                {
                    **(final_state.get("report") or {}),
                    "llm": summarize_run_llm(db, run_id),
                },
                ensure_ascii=False,
                default=str,
            )
            run.finished_at = now_str()
            db.commit()
            return

        latest_candidates = final_state.get("candidates") or {
            "products": [],
            "packages": [],
            "bindings": [],
            "issues": [],
        }
        result = final_state.get("apply_result") or {}
        report = final_state.get("report") or {
            "mode": run.mode,
            "provider": provider_name,
            "summary": result,
            "issues": latest_candidates.get("issues", []),
        }
        report["prompt_version"] = settings.agent_prompt_version
        report["llm"] = summarize_run_llm(db, run_id)
        candidates_json = json.dumps(
            {
                "products": latest_candidates["products"],
                "packages": latest_candidates["packages"],
                "bindings": latest_candidates["bindings"],
            },
            ensure_ascii=False,
            default=str,
        )
        run = _load_run(db, run_id)
        run.products_candidates = len(latest_candidates["products"])
        run.packages_candidates = len(latest_candidates["packages"])
        run.bindings_candidates = len(latest_candidates["bindings"])
        run.products_added = result["products_added"]
        run.products_updated = result["products_updated"]
        run.products_skipped = result["products_skipped"]
        run.packages_added = result["packages_added"]
        run.packages_updated = result["packages_updated"]
        run.packages_skipped = result["packages_skipped"]
        run.bindings_added = result["bindings_added"]
        run.bindings_skipped = result["bindings_skipped"]
        run.candidates_json = candidates_json
        run.report_json = json.dumps(report, ensure_ascii=False, default=str)
        run.status = "succeeded"
        run.stage = "report"
        run.error = None
        run.finished_at = now_str()
        db.commit()
    except _RunNotFound:
        # run 被删除等极端情况：不写状态
        db.rollback()
    except AgentCancelled:
        try:
            db.rollback()
            _update_run(
                db,
                run_id,
                status="cancelled",
                stage="cancelled",
                finished_at=now_str(),
            )
            _append_event(db, run_id, 0, "report", None, "任务已取消")
        except Exception:
            db.rollback()
    except Exception as exc:
        try:
            db.rollback()
            _update_run(db, run_id, status="failed", stage="failed", error=str(exc)[:2000], finished_at=now_str())
            _append_event(db, run_id, 0, "report", None, f"运行失败：{str(exc)[:300]}")
        except Exception:
            db.rollback()
    finally:
        db.close()


def run_to_dict(db: Session, run: ImportRun) -> dict:
    events = db.scalars(
        select(ImportRunEvent)
        .where(ImportRunEvent.run_id == run.id)
        .order_by(ImportRunEvent.step.asc(), ImportRunEvent.id.asc())
    ).all()
    return {
        "id": run.id,
        "mode": run.mode,
        "status": run.status,
        "stage": run.stage,
        "provider": run.provider,
        "prompt_version": run.prompt_version,
        "note": run.note,
        "file_count": run.file_count,
        "products_candidates": run.products_candidates,
        "packages_candidates": run.packages_candidates,
        "bindings_candidates": run.bindings_candidates,
        "products_added": run.products_added,
        "products_updated": run.products_updated,
        "products_skipped": run.products_skipped,
        "packages_added": run.packages_added,
        "packages_updated": run.packages_updated,
        "packages_skipped": run.packages_skipped,
        "bindings_added": run.bindings_added,
        "bindings_skipped": run.bindings_skipped,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "error": run.error,
        "llm": summarize_run_llm(db, run.id),
        "report": json.loads(run.report_json) if run.report_json else None,
        "candidates": json.loads(run.candidates_json) if run.candidates_json else None,
        "events": [
            {
                "id": e.id,
                "step": e.step,
                "role": e.role,
                "tool": e.tool,
                "summary": e.summary,
                "created_at": e.created_at,
            }
            for e in events
        ],
    }


def apply_saved_run(db: Session, run_id: int, candidates_override: dict | None = None) -> dict:
    """把此前成功预演（dry-run）生成的候选数据集正式写入数据库。支持传入经人工审阅/编辑的候选集。"""
    run = _load_run(db, run_id)
    if run.status != "succeeded":
        raise ValueError(f"只有成功完成的任务才能入库（当前状态：{run.status}）")

    if candidates_override is not None:
        normalized, _, errors = validation.validate_candidates(candidates_override, db)
        if errors:
            raise ValueError(f"候选数据未通过硬校验：{'；'.join(errors[:3])}")
        candidates = normalized
        run.candidates_json = json.dumps(candidates, ensure_ascii=False, default=str)
        run.products_candidates = len(candidates.get("products", []))
        run.packages_candidates = len(candidates.get("packages", []))
        run.bindings_candidates = len(candidates.get("bindings", []))
    else:
        if not run.candidates_json:
            raise ValueError("该任务未包含候选数据，无法入库")
        candidates = json.loads(run.candidates_json)

    result = persistence.apply_candidates(
        db,
        candidates,
        mode="apply",
        allow_name_update=(candidates_override is not None),
    )

    max_step = db.scalar(
        select(ImportRunEvent.step)
        .where(ImportRunEvent.run_id == run.id)
        .order_by(ImportRunEvent.step.desc())
        .limit(1)
    ) or 0

    run.mode = "apply"
    run.stage = "applied"
    run.products_added = result["products_added"]
    run.products_updated = result["products_updated"]
    run.products_skipped = result["products_skipped"]
    run.packages_added = result["packages_added"]
    run.packages_updated = result["packages_updated"]
    run.packages_skipped = result["packages_skipped"]
    run.bindings_added = result["bindings_added"]
    run.bindings_skipped = result["bindings_skipped"]

    if run.report_json:
        report = json.loads(run.report_json)
        report["mode"] = "apply"
        report["summary"] = result
        run.report_json = json.dumps(report, ensure_ascii=False, default=str)

    _append_event(
        db,
        run.id,
        max_step + 1,
        "human",
        "apply_approval",
        f"人工审核通过，候选数据已正式写入数据库：{_result_summary(result)}",
    )
    db.commit()
    return run_to_dict(db, run)

