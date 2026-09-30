"""LLM 适配：OpenAI 兼容 Chat Completions tools/tool_calls。"""
import json
from dataclasses import dataclass, field

import httpx

from app.core.config import settings


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


class OpenAICompatibleClient:
    """通过 httpx 调用企业网关/OpenAI 兼容 /chat/completions。"""

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None):
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model
        if not self.base_url or not self.model:
            raise RuntimeError("LLM_PROVIDER=openai 时需配置 LLM_BASE_URL 与 LLM_MODEL")

    def chat(self, messages: list[dict], tool_schemas: list[dict]) -> LLMResponse:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
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
        )
