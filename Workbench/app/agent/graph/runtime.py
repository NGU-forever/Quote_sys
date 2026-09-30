"""Runtime dependencies and cancellation helpers shared by graph nodes."""
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx


class AgentCancelled(RuntimeError):
    """Raised when a running graph is cancelled by the user."""


@dataclass
class GraphRuntime:
    provider: Any
    provider_name: str
    db: Any
    cancel_check: Callable[[], bool]
    # 工具循环的模型调用上限（对应界面上的 max_steps）
    max_steps: int = 20
    # 是否启用工具循环（离线 Mock 走确定性规则，真实模型下开启）
    enable_tool_loop: bool = False
    # LLM 计量回调：每次模型调用后回调一次，由 agent_service 落 llm_calls 表
    llm_observer: Callable[[dict], None] | None = None
    llm_calls: int = field(default=0, init=False)

    def ensure_active(self) -> None:
        if self.cancel_check():
            raise AgentCancelled("任务已取消")

    def chat(self, messages: list[dict], tool_schemas: list[dict], node: str = ""):
        """Call the provider with bounded retries for transient transport errors.

        每次成功调用都会回调 ``llm_observer``（token / 耗时 / 模型 / 节点）。
        """
        last_error: Exception | None = None
        for attempt in range(1, 4):
            self.ensure_active()
            try:
                started = time.perf_counter()
                response = self.provider.chat(messages, tool_schemas)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
            except AgentCancelled:
                raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500:
                    raise RuntimeError(
                        f"LLM 调用失败（HTTP {exc.response.status_code}）："
                        f"{exc.response.text[:200]}"
                    ) from exc
                last_error = exc
            except httpx.TransportError as exc:
                last_error = exc
            except Exception as exc:
                raise RuntimeError(f"LLM 调用失败：{exc}") from exc
            else:
                self.llm_calls += 1
                self._observe(node, response, elapsed_ms)
                return response
            if attempt < 3:
                time.sleep(2 * attempt)
        raise RuntimeError(f"LLM 调用失败：{last_error}") from last_error

    def _observe(self, node: str, response: Any, elapsed_ms: int) -> None:
        if self.llm_observer is None:
            return
        latency = int(getattr(response, "latency_ms", 0) or elapsed_ms)
        self.llm_observer(
            {
                "node": node,
                "provider": self.provider_name,
                "model": str(getattr(response, "model", "") or ""),
                "usage": getattr(response, "usage", None),
                "latency_ms": latency,
            }
        )
