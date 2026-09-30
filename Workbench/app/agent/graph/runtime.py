"""Runtime dependencies and cancellation helpers shared by graph nodes."""
import time
from dataclasses import dataclass
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

    def ensure_active(self) -> None:
        if self.cancel_check():
            raise AgentCancelled("任务已取消")

    def chat(self, messages: list[dict], tool_schemas: list[dict]):
        """Call the provider with bounded retries for transient transport errors."""
        last_error: Exception | None = None
        for attempt in range(1, 4):
            self.ensure_active()
            try:
                return self.provider.chat(messages, tool_schemas)
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
            if attempt < 3:
                time.sleep(2 * attempt)
        raise RuntimeError(f"LLM 调用失败：{last_error}") from last_error
