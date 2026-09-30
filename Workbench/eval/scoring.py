"""评测打分：集合级 P/R/F1、字段级准确率与汇总（纯函数，可单测）。"""
from __future__ import annotations

from typing import Callable, Iterable, Sequence

PRODUCT_FIELDS = ("category", "name", "min_price", "max_price", "unit")
PACKAGE_FIELDS = ("name", "sku_ids", "quantities", "std_price")


def _round(value: float) -> float:
    return round(value, 4)


def prf(expected: set, actual: set) -> dict:
    """由两个集合算出 TP/FP/FN 与 precision/recall/F1。"""
    tp = len(expected & actual)
    fp = len(actual - expected)
    fn = len(expected - actual)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": _round(precision),
        "recall": _round(recall),
        "f1": _round(f1),
    }


def score_entities(expected: Sequence[dict], actual: Sequence[dict], key: Callable[[dict], object]) -> dict:
    """按业务主键比对两组实体。"""
    return prf({key(item) for item in expected}, {key(item) for item in actual})


def _value_equal(left, right) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(left) == float(right)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_value_equal(a, b) for a, b in zip(left, right))
    return left == right


def field_accuracy(
    expected: Sequence[dict],
    actual: Sequence[dict],
    key: Callable[[dict], object],
    fields: Iterable[str],
) -> dict:
    """只在「主键匹配上」的实体之间比较字段，返回字段级准确率与错配明细。"""
    fields = tuple(fields)
    actual_by_key = {key(item): item for item in actual}
    total = 0
    correct = 0
    mismatches: list[str] = []
    for item in expected:
        item_key = key(item)
        counterpart = actual_by_key.get(item_key)
        if counterpart is None:
            continue
        for field in fields:
            total += 1
            if _value_equal(item.get(field), counterpart.get(field)):
                correct += 1
            else:
                mismatches.append(
                    f"{item_key}.{field}: 期望 {item.get(field)!r} 实际 {counterpart.get(field)!r}"
                )
    return {
        "total": total,
        "correct": correct,
        "accuracy": _round(correct / total) if total else 1.0,
        "mismatches": mismatches,
    }


def score_case(
    case,
    *,
    status: str,
    products: list[dict],
    packages: list[dict],
    bindings: list[tuple[str, str]],
    issues: Sequence[str],
    error: str | None,
    llm: dict | None = None,
    corrections: int = 0,
) -> dict:
    """对单个 case 打分（含期望失败路径与 issue 关键词覆盖）。"""
    product_score = score_entities(case.expected_products, products, lambda item: item["sku_id"])
    package_score = score_entities(case.expected_packages, packages, lambda item: item["package_id"])
    binding_score = score_entities(
        [{"key": pair} for pair in case.expected_bindings],
        [{"key": pair} for pair in bindings],
        lambda item: item["key"],
    )
    issue_text = " ".join([*issues, error or ""])
    missing_keywords = [word for word in case.expect_issue_keywords if word not in issue_text]
    status_ok = status == case.expect_status
    passed = (
        status_ok
        and not missing_keywords
        and product_score["fp"] == 0
        and product_score["fn"] == 0
        and package_score["fp"] == 0
        and package_score["fn"] == 0
        and binding_score["fp"] == 0
        and binding_score["fn"] == 0
    )
    return {
        "key": case.key,
        "title": case.title,
        "tags": list(case.tags),
        "passed": passed,
        "status": status,
        "expected_status": case.expect_status,
        "status_ok": status_ok,
        "missing_issue_keywords": missing_keywords,
        "products": product_score,
        "packages": package_score,
        "bindings": binding_score,
        "product_fields": field_accuracy(
            case.expected_products, products, lambda item: item["sku_id"], PRODUCT_FIELDS
        ),
        "package_fields": field_accuracy(
            case.expected_packages, packages, lambda item: item["package_id"], PACKAGE_FIELDS
        ),
        "corrections": corrections,
        "llm": llm or {},
        "error": error,
    }


def aggregate(case_scores: Sequence[dict]) -> dict:
    """汇总：微平均 P/R/F1、字段准确率、通过率、自愈与成本合计。"""
    totals = {name: {"tp": 0, "fp": 0, "fn": 0} for name in ("products", "packages", "bindings")}
    for score in case_scores:
        for name, bucket in totals.items():
            for metric in ("tp", "fp", "fn"):
                bucket[metric] += score[name][metric]

    micro = {}
    for name, bucket in totals.items():
        micro[name] = prf_from_counts(bucket["tp"], bucket["fp"], bucket["fn"])

    field_total = sum(score["product_fields"]["total"] for score in case_scores)
    field_correct = sum(score["product_fields"]["correct"] for score in case_scores)
    package_field_total = sum(score["package_fields"]["total"] for score in case_scores)
    package_field_correct = sum(score["package_fields"]["correct"] for score in case_scores)

    llm_calls = sum(int((score.get("llm") or {}).get("calls") or 0) for score in case_scores)
    llm_tokens = sum(int((score.get("llm") or {}).get("total_tokens") or 0) for score in case_scores)
    llm_cost = sum(float((score.get("llm") or {}).get("cost") or 0.0) for score in case_scores)
    llm_latency = sum(int((score.get("llm") or {}).get("latency_ms") or 0) for score in case_scores)

    passed = sum(1 for score in case_scores if score["passed"])
    return {
        "cases": len(case_scores),
        "passed": passed,
        "pass_rate": _round(passed / len(case_scores)) if case_scores else 0.0,
        "micro": micro,
        "product_field_accuracy": _round(field_correct / field_total) if field_total else 1.0,
        "package_field_accuracy": _round(package_field_correct / package_field_total)
        if package_field_total
        else 1.0,
        "hallucination_rate": _round(
            micro["products"]["fp"] / (micro["products"]["tp"] + micro["products"]["fp"])
        )
        if (micro["products"]["tp"] + micro["products"]["fp"])
        else 0.0,
        "self_heal_runs": sum(1 for score in case_scores if score["corrections"] > 0),
        "llm_calls": llm_calls,
        "llm_total_tokens": llm_tokens,
        "llm_latency_ms": llm_latency,
        "llm_cost": round(llm_cost, 6),
        "failed_cases": [score["key"] for score in case_scores if not score["passed"]],
    }


def prf_from_counts(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": _round(precision),
        "recall": _round(recall),
        "f1": _round(f1),
    }
