"""Shared redis connection factories.

Two flavors:
 - get_redis(): synchronous client used by celery workers and request-path code
   that doesn't need to await.
 - get_async_redis(): asyncio client used by the SSE endpoint and the pub/sub
   dispatcher (which must coexist with FastAPI's event loop).

Both are lazy singletons keyed off REDIS_URL so tests can monkeypatch them
without touching the real network.
"""

from functools import lru_cache
import redis
import redis.asyncio as aredis
from app.config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


@lru_cache
def get_async_redis() -> aredis.Redis:
    return aredis.Redis.from_url(get_settings().redis_url, decode_responses=True)
