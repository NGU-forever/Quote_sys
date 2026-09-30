"""Agent 评测入口：在 golden case 上跑完整状态图并输出指标。

用法（先启动 PostgreSQL，评测使用独立库，不会碰开发库）::

    cd Workbench
    # 1) 流水线一致性（离线 scripted，CI 可用，不需要模型）
    .venv/bin/python -m eval.run_eval --provider scripted --enforce

    # 2) 真实模型抽取质量（需要 .env 配置 LLM_BASE_URL/LLM_MODEL，会产生真实费用）
    .venv/bin/python -m eval.run_eval --provider live --out eval/report-live.json

指标口径：
- products/packages/bindings：按业务主键的微平均 P/R/F1；
- hallucination_rate：模型/流水线凭空造出的商品占比（FP / (TP+FP)）；
- product_field_accuracy：主键匹配上的实体之间字段级一致率；
- pass_rate：case 级全对率（含期望失败路径与 issue 关键词覆盖）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

_WORKBENCH_DIR = Path(__file__).resolve().parent.parent
if str(_WORKBENCH_DIR) not in sys.path:
    sys.path.insert(0, str(_WORKBENCH_DIR))

# 评测库：显式用独立库，避免误连开发库
if os.environ.get("EVAL_DATABASE_URL") and not os.environ.get("TEST_DATABASE_URL"):
    os.environ["TEST_DATABASE_URL"] = os.environ["EVAL_DATABASE_URL"]

from tests import db_support  # noqa: E402  # 必须在任何 app.* 之前导入

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.agent.graph.builder import build_import_graph  # noqa: E402
from app.agent.graph.runtime import GraphRuntime  # noqa: E402
from app.agent.llm_client import LLMResponse, OpenAICompatibleClient, ToolCall  # noqa: E402
from app.agent.metrics import estimate_cost  # noqa: E402
from app.agent.readers.manifest import build_manifest  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.models.device_binding import DeviceBinding  # noqa: E402
from app.models.package import Package  # noqa: E402
from app.models.product import Product  # noqa: E402
from eval import scoring  # noqa: E402
from eval.golden_cases import CASES, GoldenCase  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402


class ScriptedProvider:
    """离线评测用：把 case 里预置的候选当作模型输出（衡量流水线而非模型）。"""

    def __init__(self, case: GoldenCase):
        self.case = case
        self.corrections = 0

    def chat(self, messages, tool_schemas):
        name = str((tool_schemas[0].get("function") or {}).get("name") or "")
        if name == "extract_products":
            return LLMResponse(
                tool_calls=[ToolCall(name, {"products": self.case.raw.get("products", []), "issues": []}, call_id=name)],
                summary="scripted products",
                model="scripted",
            )
        if name == "extract_packages":
            return LLMResponse(
                tool_calls=[ToolCall(name, {"packages": self.case.raw.get("packages", []), "issues": []}, call_id=name)],
                summary="scripted packages",
                model="scripted",
            )
        if name == "extract_bindings":
            return LLMResponse(
                tool_calls=[ToolCall(name, {"bindings": self.case.raw.get("bindings", []), "issues": []}, call_id=name)],
                summary="scripted bindings",
                model="scripted",
            )
        if name == "correct_candidates":
            self.corrections += 1
            payload = self.case.corrected if self.case.corrected is not None else self.case.raw
            body = {
                "products": payload.get("products", []),
                "packages": payload.get("packages", []),
                "bindings": payload.get("bindings", []),
                "issues": payload.get("issues", []),
            }
            return LLMResponse(tool_calls=[ToolCall(name, body, call_id=name)], summary="scripted correction")
        return LLMResponse(summary="scripted noop")


class UsageRecorder:
    """收集 LLM 计量（评测里不落库，直接聚合）。"""

    def __init__(self):
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.latency_ms = 0
        self.cost = 0.0

    def __call__(self, payload: dict) -> None:
        self.calls += 1
        usage = payload.get("usage") or {}
        self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        self.completion_tokens += int(usage.get("completion_tokens") or 0)
        self.total_tokens += int(usage.get("total_tokens") or 0)
        self.latency_ms += int(payload.get("latency_ms") or 0)
        self.cost += estimate_cost(
            int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
        )

    def as_dict(self) -> dict:
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "cost": round(self.cost, 6),
        }


def _initial_state(mode: str = "apply") -> dict:
    return {
        "run_id": 0,
        "mode": mode,
        "manifest": {},
        "db_stats": {},
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


def _db_snapshot(session) -> tuple[list[dict], list[dict], list[tuple[str, str]]]:
    products = [
        {
            "sku_id": row.sku_id,
            "category": row.category,
            "name": row.name,
            "min_price": row.min_price,
            "max_price": row.max_price,
            "unit": row.unit,
        }
        for row in session.scalars(select(Product).order_by(Product.sku_id)).all()
    ]
    packages = [
        {
            "package_id": row.package_id,
            "name": row.name,
            "sku_ids": json.loads(row.sku_ids or "[]"),
            "quantities": json.loads(row.quantities or "[]"),
            "std_price": row.std_price,
        }
        for row in session.scalars(select(Package).order_by(Package.package_id)).all()
    ]
    bindings = [
        (row.device_sku_id, row.consumable_sku_id)
        for row in session.scalars(
            select(DeviceBinding).order_by(DeviceBinding.device_sku_id, DeviceBinding.consumable_sku_id)
        ).all()
    ]
    return products, packages, bindings


def run_case(case: GoldenCase, provider_kind: str, max_steps: int, mode: str = "apply") -> dict:
    engine = db_support.create_test_engine()
    db_support.reset_schema(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    recorder = UsageRecorder()
    provider = (
        ScriptedProvider(case)
        if provider_kind == "scripted"
        else OpenAICompatibleClient(
            base_url=settings.llm_base_url, api_key=settings.llm_api_key, model=settings.llm_model
        )
    )
    started = time.perf_counter()
    status = "succeeded"
    error: str | None = None
    issues: list[str] = []
    session = Session()
    tmp_root = tempfile.mkdtemp(prefix=f"eval-{case.key}-")
    try:
        root = Path(tmp_root)
        case.assets(root)
        with patch.object(settings, "assets_dir", str(root)):
            build_manifest(root)  # 预热：读取器异常应在此处就暴露
            runtime = GraphRuntime(
                provider=provider,
                provider_name=provider_kind,
                db=session,
                cancel_check=lambda: False,
                max_steps=max_steps,
                enable_tool_loop=provider_kind == "live",
                llm_observer=recorder,
            )
            graph = build_import_graph(runtime, InMemorySaver())
            try:
                final = graph.invoke(
                    _initial_state(mode), config={"configurable": {"thread_id": f"eval-{case.key}"}}
                )
                status = str((final or {}).get("status") or "succeeded")
                issues = list((final or {}).get("issues") or [])
                if status == "failed":
                    error = "；".join((final or {}).get("validation_errors") or []) or "agent failed"
            except Exception as exc:  # 图执行异常按失败计
                session.rollback()
                status = "failed"
                error = f"{type(exc).__name__}: {exc}"
        products, packages, bindings = _db_snapshot(session)
    finally:
        session.close()
        engine.dispose()

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    corrections = provider.corrections if isinstance(provider, ScriptedProvider) else 0
    score = scoring.score_case(
        case,
        status=status,
        products=products,
        packages=packages,
        bindings=bindings,
        issues=issues,
        error=error,
        llm=recorder.as_dict(),
        corrections=corrections,
    )
    score["elapsed_ms"] = elapsed_ms
    return score


def _print_case(score: dict) -> None:
    flag = "PASS" if score["passed"] else "FAIL"
    print(
        f"[{flag}] {score['key']:<34} status={score['status']:<9} "
        f"products F1={score['products']['f1']:.2f} "
        f"packages F1={score['packages']['f1']:.2f} "
        f"bindings F1={score['bindings']['f1']:.2f} "
        f"field={score['product_fields']['accuracy']:.2f} "
        f"heal={score['corrections']} {score['elapsed_ms']}ms"
    )
    if not score["passed"]:
        if not score["status_ok"]:
            print(f"       └ 状态期望 {score['expected_status']}，实际 {score['status']}：{score['error']}")
        if score["missing_issue_keywords"]:
            print(f"       └ 缺少 issue 关键词：{score['missing_issue_keywords']}")
        for name in ("products", "packages", "bindings"):
            bucket = score[name]
            if bucket["fp"] or bucket["fn"]:
                print(f"       └ {name} fp={bucket['fp']} fn={bucket['fn']}")
        for mismatch in score["product_fields"]["mismatches"][:3]:
            print(f"       └ 字段错配 {mismatch}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QuoteSys Agent 评测")
    parser.add_argument("--provider", choices=("scripted", "live"), default="scripted")
    parser.add_argument("--cases", default="", help="只跑指定 case（逗号分隔）")
    parser.add_argument("--max-steps", type=int, default=settings.llm_max_steps)
    parser.add_argument("--mode", choices=("dry-run", "apply"), default="apply")
    parser.add_argument("--out", default="", help="指标 JSON 输出路径")
    parser.add_argument("--enforce", action="store_true", help="低于阈值时以非零退出码结束")
    parser.add_argument("--min-pass-rate", type=float, default=1.0)
    parser.add_argument("--min-product-f1", type=float, default=1.0)
    args = parser.parse_args(argv)

    selected = [case for case in CASES if not args.cases or case.key in set(args.cases.split(","))]
    if not selected:
        print("没有匹配的 case", file=sys.stderr)
        return 2

    db_support.ensure_test_database()
    print(f"评测库：{db_support.test_database_url()}")
    print(f"provider={args.provider} cases={len(selected)} mode={args.mode} max_steps={args.max_steps}\n")

    scores = []
    for case in selected:
        score = run_case(case, args.provider, args.max_steps, args.mode)
        scores.append(score)
        _print_case(score)

    summary = scoring.aggregate(scores)
    print("\n================ 汇总 ================")
    for name in ("products", "packages", "bindings"):
        bucket = summary["micro"][name]
        print(
            f"{name:<10} P={bucket['precision']:.3f} R={bucket['recall']:.3f} F1={bucket['f1']:.3f} "
            f"(tp={bucket['tp']} fp={bucket['fp']} fn={bucket['fn']})"
        )
    print(f"商品字段级准确率     : {summary['product_field_accuracy']:.3f}")
    print(f"套餐字段级准确率     : {summary['package_field_accuracy']:.3f}")
    print(f"幻觉率(商品 FP 占比) : {summary['hallucination_rate']:.3f}")
    print(f"case 通过率          : {summary['pass_rate']:.3f} ({summary['passed']}/{summary['cases']})")
    print(f"触发自愈的 case      : {summary['self_heal_runs']}")
    if args.provider == "live":
        print(
            f"LLM 调用 {summary['llm_calls']} 次 / {summary['llm_total_tokens']} tokens / "
            f"{summary['llm_latency_ms']}ms / 成本 {summary['llm_cost']} {settings.llm_price_currency}"
        )
    if summary["failed_cases"]:
        print(f"未通过 case：{', '.join(summary['failed_cases'])}")

    report = {
        "provider": args.provider,
        "mode": args.mode,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "prompt_version": settings.agent_prompt_version,
        "summary": summary,
        "cases": scores,
    }
    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = _WORKBENCH_DIR / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"指标已写入：{out_path}")

    if args.enforce:
        if summary["pass_rate"] < args.min_pass_rate:
            print(f"未达阈值：pass_rate {summary['pass_rate']} < {args.min_pass_rate}", file=sys.stderr)
            return 1
        if summary["micro"]["products"]["f1"] < args.min_product_f1:
            print(
                f"未达阈值：products F1 {summary['micro']['products']['f1']} < {args.min_product_f1}",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
