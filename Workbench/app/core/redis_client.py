"""Redis 客户端管理器与连接池（支持优雅降级）。

当 Redis 未启动或不可用时，记录 warning 日志并优雅降级为 None，
保证核心报价与离线 SQLite 业务不被阻塞。
"""
from __future__ import annotations

import logging
from typing import Optional

try:
    from redis import asyncio as aioredis
    from redis.asyncio import Redis as AsyncRedis
except ImportError:
    aioredis = None
    AsyncRedis = None  # type: ignore

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_redis_pool: Optional[AsyncRedis] = None


async def get_redis() -> Optional[AsyncRedis]:
    """获取异步 Redis 连接客户端。若连接失败或 Redis 未安装，则优雅降级返回 None。"""
    global _redis_pool
    if aioredis is None:
        logger.warning("Redis package not installed, running without cache")
        return None

    if _redis_pool is None:
        settings = get_settings()
        try:
            client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await client.ping()
            _redis_pool = client
        except Exception as e:
            logger.warning("Redis unavailable, running without cache: %s", e)
            _redis_pool = None
            return None
    return _redis_pool


async def close_redis() -> None:
    """关闭 Redis 连接池。"""
    global _redis_pool
    if _redis_pool is not None:
        try:
            await _redis_pool.aclose()
        except Exception as e:
            logger.debug("Error closing Redis pool: %s", e)
        finally:
            _redis_pool = None
