"""Active-user registry backed by a redis sorted set.

Members are user ids. The score is the expiry timestamp (unix seconds).
Beat's fan-out task purges expired entries before each tick, so api crashes
don't strand users in the registry forever.
"""

import time
from app.realtime import redis_client


KEY = "active_users"


def add(user_id: str, *, ttl_seconds: int) -> None:
    # Access get_redis through the module so monkeypatching redis_client.get_redis
    # in tests correctly intercepts the call (direct import would capture the old ref).
    r = redis_client.get_redis()
    r.zadd(KEY, {user_id: time.time() + ttl_seconds})


def refresh(user_id: str, *, ttl_seconds: int) -> None:
    """Extend a user's TTL. Called by the api heartbeat every 20s while the SSE
    connection is open."""
    add(user_id, ttl_seconds=ttl_seconds)  # ZADD overwrites the score


def remove(user_id: str) -> None:
    redis_client.get_redis().zrem(KEY, user_id)


def list_active() -> list[str]:
    return redis_client.get_redis().zrange(KEY, 0, -1)


def purge_expired() -> int:
    """Drop entries whose score is in the past. Returns count removed."""
    return redis_client.get_redis().zremrangebyscore(KEY, "-inf", time.time())
