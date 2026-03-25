import json
import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings

# ── connection pool (shared across requests) ──────────────────────────────────
_pool: Redis | None = None


def get_redis() -> Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _pool


# ── transcription progress helpers ───────────────────────────────────────────
# Key pattern: transcribe:progress:{task_id}
# TTL: 1 hour (task result is no longer needed after that)

_PROGRESS_TTL = 3600
_KEY_PREFIX = "transcribe:progress:"


async def set_progress(
    task_id: str,
    current: int,
    total: int,
    message: str,
    status: str = "running",   # running | done | error
) -> None:
    r = get_redis()
    payload = json.dumps({
        "current": current,
        "total": total,
        "message": message,
        "status": status,
    })
    await r.set(f"{_KEY_PREFIX}{task_id}", payload, ex=_PROGRESS_TTL)


async def get_progress(task_id: str) -> dict | None:
    r = get_redis()
    raw = await r.get(f"{_KEY_PREFIX}{task_id}")
    if raw is None:
        return None
    return json.loads(raw)


async def delete_progress(task_id: str) -> None:
    r = get_redis()
    await r.delete(f"{_KEY_PREFIX}{task_id}")