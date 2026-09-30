"""有界工具调用循环（ReAct）：模型自主选工具 → 服务端执行 → Observation 回灌。

设计约束：
1. **步数硬上限**：最多 ``max_steps`` 次模型调用，超限即停，不会无限自转；
2. **工具错误不炸 run**：工具异常变成 ``ok=False`` 的 Observation 交回模型；
3. **终止工具显式化**：只有 terminal_tools 里的工具能结束循环并产出结构化结果；
4. **全程可审计**：每一步产出可落库的 trace（节点 / 工具 / 参数摘要 / 结果摘要）；
5. **可取消**：每步开始前检查 cancel_check。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from app.agent.graph.runtime import GraphRuntime


@dataclass
class ToolLoopOutcome:
    """工具循环结果。"""

    finished: bool = False
    terminal: dict | None = None
    steps: int = 0
    stopped_reason: str = "max_steps"  # submitted / no_tool_call / max_steps / skipped
    issues: list[str] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)


def _digest(value: Any, limit: int = 400) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(value)
    return text if len(text) <= limit else text[:limit] + "…"


def run_tool_loop(
    runtime: GraphRuntime,
    *,
    node: str,
    system_prompt: str,
    user_prompt: str,
    tool_schemas: list[dict],
    execute: Callable[[str, dict], dict],
    terminal_tools: Mapping[str, Callable[[dict], dict]],
    max_steps: int,
    max_observation_chars: int = 6000,
) -> ToolLoopOutcome:
    """执行有界工具循环。``execute`` 抛出的异常会被转成 Observation。"""
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    outcome = ToolLoopOutcome()
    if runtime.provider is None:
        outcome.stopped_reason = "skipped"
        return outcome

    for step in range(1, max(1, max_steps) + 1):
        runtime.ensure_active()
        response = runtime.chat(messages, tool_schemas, node=node)
        outcome.steps = step
        calls = list(getattr(response, "tool_calls", None) or [])
        summary = str(getattr(response, "summary", "") or "")
        outcome.trace.append(
            {"step": step, "role": "assistant", "tool": None, "summary": summary[:300]}
        )

        if not calls:
            outcome.stopped_reason = "no_tool_call"
            return outcome

        messages.append(
            {
                "role": "assistant",
                "content": summary,
                "tool_calls": [
                    {
                        "id": call.call_id or f"{node}-{step}-{index}",
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments or {}, ensure_ascii=False),
                        },
                    }
                    for index, call in enumerate(calls)
                ],
            }
        )

        for index, call in enumerate(calls):
            call_id = call.call_id or f"{node}-{step}-{index}"
            arguments = call.arguments if isinstance(call.arguments, dict) else {}

            if call.name in terminal_tools:
                try:
                    terminal = terminal_tools[call.name](arguments)
                except Exception as exc:  # 终止工具参数非法：回灌给模型重新提交
                    observation = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": _digest(observation, max_observation_chars),
                        }
                    )
                    outcome.trace.append(
                        {
                            "step": step,
                            "role": "tool",
                            "tool": call.name,
                            "summary": f"提交被拒绝：{exc}"[:300],
                        }
                    )
                    continue
                outcome.finished = True
                outcome.terminal = terminal
                outcome.stopped_reason = "submitted"
                outcome.trace.append(
                    {
                        "step": step,
                        "role": "tool",
                        "tool": call.name,
                        "summary": f"提交来源计划：{_digest(terminal, 200)}",
                    }
                )
                return outcome

            try:
                observation = execute(call.name, arguments)
            except Exception as exc:  # 工具级异常只作为 Observation，不中断 run
                observation = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            if not isinstance(observation, dict):
                observation = {"ok": True, "result": observation}

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": _digest(observation, max_observation_chars),
                }
            )
            outcome.trace.append(
                {
                    "step": step,
                    "role": "tool",
                    "tool": call.name,
                    "summary": f"{call.name}({_digest(arguments, 120)}) → "
                    f"{_digest(observation, 160)}"[:300],
                }
            )

    outcome.stopped_reason = "max_steps"
    outcome.issues.append(
        f"{node} 工具循环达到 max_steps={max_steps} 仍未提交结果，已按兜底策略继续"
    )
    return outcome
