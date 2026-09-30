"""LLM 适配：OpenAI 兼容 Chat Completions tools/tool_calls。

同时负责：
1. 解析 usage → token 计量（供成本统计）；
2. 记录调用耗时；
3. 测试环境下硬拦截真实付费接口（避免误烧额度）。
"""
import json
import os
import time
from dataclasses import dataclass, field

import httpx

from app.core.config import settings


def remote_calls_blocked() -> bool:
    """测试环境默认禁止真实远端调用，需 QUOTESYS_ALLOW_REMOTE_LLM=1 显式放行。

    历史事故：测试期望走离线 Mock，但因 .env 中 LLM_PROVIDER=auto，真实请求
    打到了付费网关。这里做一道硬拦截，避免再次发生。
    """
    if os.environ.get("QUOTESYS_ALLOW_REMOTE_LLM") == "1":
        return False
    return bool(os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("QUOTESYS_TESTING"))


@dataclass
class ToolCall:
    name: str
    arguments: dict
    call_id: str | None = None


@dataclass
class LLMResponse:
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_requested: bool = False
    summary: str = ""
    raw: dict | None = None
    model: str = ""
    usage: dict | None = None
    latency_ms: int = 0


def normalize_usage(raw: object) -> dict | None:
    """把各家网关的 usage 归一成 prompt/completion/total_tokens。"""
    if not isinstance(raw, dict):
        return None
    prompt = int(raw.get("prompt_tokens") or raw.get("input_tokens") or 0)
    completion = int(raw.get("completion_tokens") or raw.get("output_tokens") or 0)
    total = int(raw.get("total_tokens") or (prompt + completion))
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


class OpenAICompatibleClient:
    """通过 httpx 调用企业网关/OpenAI 兼容 /chat/completions。"""

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None):
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model
        if not self.base_url or not self.model:
            raise RuntimeError("LLM_PROVIDER=openai 时需配置 LLM_BASE_URL 与 LLM_MODEL")

    def chat(self, messages: list[dict], tool_schemas: list[dict]) -> LLMResponse:
        if remote_calls_blocked():
            raise RuntimeError(
                "测试环境禁止调用真实 LLM 接口（避免误用付费额度）。"
                "确实需要请设置 QUOTESYS_ALLOW_REMOTE_LLM=1。"
            )
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        started = time.perf_counter()
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json={
                "model": self.model,
                "messages": messages,
                "tools": tool_schemas,
                "tool_choice": "auto",
            },
            timeout=180.0,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        response.raise_for_status()
        payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("LLM 返回空 choices")
        message = choices[0].get("message", {})
        content = str(message.get("content") or "").strip()
        tool_calls: list[ToolCall] = []
        finish = False
        for raw_call in message.get("tool_calls") or []:
            function = raw_call.get("function") or {}
            name = str(function.get("name") or "")
            try:
                arguments = json.loads(function.get("arguments") or "{}")
                if not isinstance(arguments, dict):
                    arguments = {}
            except (TypeError, ValueError):
                arguments = {}
            call = ToolCall(name=name, arguments=arguments, call_id=raw_call.get("id"))
            if name == "finish":
                finish = True
            tool_calls.append(call)
        summary = content[:300] or "、".join(call.name for call in tool_calls) or "模型未返回内容"
        return LLMResponse(
            tool_calls=tool_calls,
            finish_requested=finish,
            summary=summary,
            raw=payload,
            model=str(payload.get("model") or self.model),
            usage=normalize_usage(payload.get("usage")),
            latency_ms=latency_ms,
        )
