#!/usr/bin/env python3
"""黄金屏像素比对：visual/baseline（基准） vs visual/current（本次渲染）。

用法：
    python3 tests/visual/compare.py
    VISUAL_THRESHOLD=0.002 python3 tests/visual/compare.py   # 收紧到 0.2% 像素

判定：尺寸不同 → 直接失败；否则统计"非零差异像素占比"，超过阈值即失败，
并把差异图写到 visual/current/diff/ 便于定位。

依赖 Pillow（DSH 捆绑 Python 自带；也可用 pip install pillow）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageChops
except ImportError:  # pragma: no cover
    print("[visual] 需要 Pillow：pip install pillow（或使用捆绑 Python 运行）", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "visual" / "baseline"
CURRENT = ROOT / "visual" / "current"
DIFF_DIR = CURRENT / "diff"
THRESHOLD = float(os.environ.get("VISUAL_THRESHOLD", "0.0005"))  # 默认 0.05% 像素差异


def diff_ratio(baseline: Image.Image, current: Image.Image) -> tuple[float, Image.Image]:
    delta = ImageChops.difference(baseline.convert("RGB"), current.convert("RGB"))
    bbox = delta.getbbox()
    histogram = delta.convert("L").histogram()
    changed = sum(histogram[8:])  # 忽略 0-7 的抗锯齿噪声
    total = baseline.width * baseline.height
    return changed / total if total else 0.0, delta


def main() -> int:
    if not BASELINE.exists():
        print(f"[visual] 缺少基准目录：{BASELINE}\n请先运行：node tests/visual/capture.mjs --update")
        return 1
    if not CURRENT.exists():
        print(f"[visual] 缺少本次渲染目录：{CURRENT}\n请先运行 capture.mjs")
        return 1

    baselines = sorted(p for p in BASELINE.glob("*.png"))
    if not baselines:
        print(f"[visual] 基准目录为空：{BASELINE}")
        return 1

    failures: list[str] = []
    unchanged = 0
    for base_path in baselines:
        current_path = CURRENT / base_path.name
        if not current_path.exists():
            failures.append(f"{base_path.name}: 本次未渲染该组合")
            continue

        baseline = Image.open(base_path)
        current = Image.open(current_path)
        if baseline.size != current.size:
            failures.append(
                f"{base_path.name}: 尺寸变化 {baseline.size} → {current.size}"
            )
            continue

        ratio, delta = diff_ratio(baseline, current)
        if ratio > THRESHOLD:
            DIFF_DIR.mkdir(parents=True, exist_ok=True)
            delta.save(DIFF_DIR / base_path.name)
            failures.append(
                f"{base_path.name}: 差异 {ratio:.3%} > 阈值 {THRESHOLD:.3%}（差异图见 visual/current/diff/）"
            )
        else:
            unchanged += 1

    total = len(baselines)
    print(f"\n[visual] 黄金屏比对：{unchanged}/{total} 张通过（阈值 {THRESHOLD:.3%} 像素差异）")
    if failures:
        print("[visual] 未通过：")
        for item in failures:
            print(f"  ✗ {item}")
        print("\n若差异是有意为之（改了渲染器或 token），请运行：node tests/visual/capture.mjs --update")
        return 1

    print("[visual] 全部通过 ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
