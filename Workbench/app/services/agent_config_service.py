"""Agent 的 AI 接口配置：页面保存到 app_settings，运行时优先于 .env。"""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.app_setting import AppSetting

AGENT_AI_KEY = "agent_ai"


def get_agent_ai(db: Session) -> dict:
    """返回 Agent 当前生效配置（含 api_key，只允许服务端读取）。"""
    row = db.scalar(select(AppSetting).where(AppSetting.key == AGENT_AI_KEY))
    raw: dict = {}
    if row is not None:
        try:
            value = json.loads(row.value)
            if isinstance(value, dict):
                raw = value
        except (TypeError, ValueError):
            raw = {}

    # 无页面配置时使用 .env / 环境变量；有页面配置后以页面保存值为准。
    if not raw:
        return {
            "provider": settings.llm_provider,
            "base_url": settings.llm_base_url,
            "api_key": settings.llm_api_key,
            "model": settings.llm_model,
            "max_steps": settings.llm_max_steps,
            "default_mode": settings.agent_default_mode,
        }

    def pick(name: str, env_value, fallback=""):
        value = raw.get(name)
        return value if value is not None else (env_value if env_value else fallback)

    provider = raw.get("provider") or settings.llm_provider or "auto"
    base_url = pick("base_url", settings.llm_base_url)
    api_key = pick("api_key", settings.llm_api_key)
    model = pick("model", settings.llm_model)
    try:
        max_steps = int(raw.get("max_steps") or settings.llm_max_steps or 20)
    except (TypeError, ValueError):
        max_steps = settings.llm_max_steps
    default_mode = raw.get("default_mode") or settings.agent_default_mode or "apply"
    return {
        "provider": provider,
        "base_url": base_url or "",
        "api_key": api_key or "",
        "model": model or "",
        "max_steps": max(1, max_steps),
        "default_mode": default_mode if default_mode in {"dry-run", "apply"} else "apply",
    }


def get_agent_ai_public(db: Session) -> dict:
    """前端可读配置：不返回 api_key 原文。"""
    config = get_agent_ai(db)
    key = config.get("api_key") or ""
    masked = None
    if key:
        masked = f"{key[:3]}...{key[-3:]}" if len(key) > 8 else "••••••"
    return {
        "provider": config["provider"],
        "base_url": config["base_url"],
        "model": config["model"],
        "max_steps": config["max_steps"],
        "default_mode": config["default_mode"],
        "has_api_key": bool(key),
        "api_key_masked": masked,
    }


def put_agent_ai(
    db: Session,
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_steps: int | None = None,
    default_mode: str | None = None,
) -> dict:
    """更新页面保存的 AI 配置；api_key=None 表示保留原值，'' 表示清空。"""
    current = get_agent_ai(db)
    next_config = dict(current)
    if provider is not None:
        next_config["provider"] = provider
    if base_url is not None:
        next_config["base_url"] = (base_url or "").strip()
    if model is not None:
        next_config["model"] = (model or "").strip()
    if api_key is not None:
        next_config["api_key"] = (api_key or "").strip()
    if max_steps is not None:
        next_config["max_steps"] = max(1, min(100, int(max_steps)))
    if default_mode is not None:
        next_config["default_mode"] = default_mode

    provider = next_config["provider"]
    if provider not in {"auto", "openai", "mock"}:
        raise ValueError("provider 只允许 auto / openai / mock")
    if default_mode is not None and next_config["default_mode"] not in {"dry-run", "apply"}:
        raise ValueError("default_mode 只允许 dry-run / apply")
    if provider == "openai" and (not next_config["base_url"] or not next_config["model"]):
        raise ValueError("使用 openai 时需要填写接口地址与模型（本地模型可不填 API Key）")

    db.merge(
        AppSetting(
            key=AGENT_AI_KEY,
            value=json.dumps(next_config, ensure_ascii=False),
        )
    )
    db.commit()
    return get_agent_ai_public(db)
