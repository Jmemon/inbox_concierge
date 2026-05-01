"""Per-user sync lock backed by Redis SET NX EX.

Without this lock, two celery tasks can race on the same user — typically the
SSE-on-connect kickoff and a beat-driven poll_new_messages firing seconds
later before the first task has set gmail_last_history_id. Both take the
full_sync path, both try to insert the same (user_id, gmail_id) row, the
second hits the unique constraint, the entire transaction rolls back, and
the user is left with a half-synced or empty inbox.

The lock holds for the duration of one sync. The ttl is a safety net for
worker crashes — after ttl seconds it auto-releases so a dead worker doesn't
strand a user.

Holders MUST release in a try/finally. Acquire returns False when another
worker holds the lock; the caller should log + return rather than retry.
"""

from app.realtime import redis_client


_KEY_PREFIX = "sync_lock"
_DEFAULT_TTL_SECONDS = 600  # 10 minutes — comfortably longer than full_sync's worst case


def _key(user_id: str) -> str:
    return f"{_KEY_PREFIX}:{user_id}"


def acquire(user_id: str, *, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> bool:
    """Returns True iff this caller now holds the lock."""
    return bool(
        redis_client.get_redis().set(_key(user_id), "1", nx=True, ex=ttl_seconds)
    )


def release(user_id: str) -> None:
    redis_client.get_redis().delete(_key(user_id))
