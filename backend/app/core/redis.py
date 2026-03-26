"""
Redis helpers.

Two clients:
  - Sync  (redis.Redis)       → used by Celery tasks (sync context)
  - Async (redis.asyncio)     → used by FastAPI SSE endpoint

Progress key pattern : transcribe:progress:{task_id}
TTL                  : 1 hour
"""

import json
import redis
import redis.asyncio as aioredis

from app.core.config import settings

_PROGRESS_TTL = 3600
_KEY_PREFIX = "transcribe:progress:"

# ── sync client (Celery) ──────────────────────────────────────────────────────
_sync_client: redis.Redis | None = None


def get_sync_redis() -> redis.Redis:
    global _sync_client
    if _sync_client is None:
        _sync_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _sync_client


def set_progress_sync(
    task_id: str,
    current: int,
    total: int,
    message: str,
    status: str = "running",
) -> None:
    r = get_sync_redis()
    payload = json.dumps({
        "current": current,
        "total": total,
        "message": message,
        "status": status,
    })
    r.set(f"{_KEY_PREFIX}{task_id}", payload, ex=_PROGRESS_TTL)


# ── async client (FastAPI) ────────────────────────────────────────────────────
_async_client: aioredis.Redis | None = None


def get_async_redis() -> aioredis.Redis:
    global _async_client
    if _async_client is None:
        _async_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _async_client


async def get_progress(task_id: str) -> dict | None:
    r = get_async_redis()
    raw = await r.get(f"{_KEY_PREFIX}{task_id}")
    if raw is None:
        return None
    return json.loads(raw)