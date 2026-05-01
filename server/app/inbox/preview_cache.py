"""Per-draft-id cache for bucket draft preview results.

Backs the polling fallback in the new-bucket flow: the worker writes the
scored result here keyed on draft_id, and the client polls
GET /api/buckets/draft/preview/{draft_id} to retrieve it if the SSE push
was lost (connection blip during the ~40s scoring window, redis pubsub
fire-and-forget delivery to a transiently-empty subscriber set, etc).

Stored shape:
  pending: {"status": "pending", "user_id": "<uid>"}
  ready:   {"status": "ready",   "user_id": "<uid>",
            "positives": [...], "near_misses": [...]}

user_id is stored so the GET endpoint can verify ownership — draft_id is
a uuid hex generated server-side but we don't want to assume it's a secret.

TTL is 600s — comfortably longer than worst-case scoring (~60s) plus a
buffer for the user to review the result. Mirrors sync_lock's TTL.
"""

import json
from app.realtime import redis_client


_KEY_PREFIX = "preview"
_DEFAULT_TTL_SECONDS = 600


def _key(draft_id: str) -> str:
    return f"{_KEY_PREFIX}:{draft_id}"


def mark_pending(draft_id: str, *, user_id: str,
                 ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
    """Write a pending placeholder. Called from the POST endpoint right after
    enqueuing the celery task so a polling client immediately sees
    status=pending instead of racing the worker startup and seeing 404."""
    body = json.dumps({"status": "pending", "user_id": user_id})
    redis_client.get_redis().set(_key(draft_id), body, ex=ttl_seconds)


def store_result(draft_id: str, *, user_id: str,
                 positives: list[dict], near_misses: list[dict],
                 ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
    """Overwrite the pending placeholder with the worker's scored result.
    Called BEFORE _publish so a poll that lands between the cache write and
    the SSE dispatch sees the ready payload instead of stale pending."""
    body = json.dumps({
        "status": "ready", "user_id": user_id,
        "positives": positives, "near_misses": near_misses,
    })
    redis_client.get_redis().set(_key(draft_id), body, ex=ttl_seconds)


def load(draft_id: str) -> dict | None:
    """Read the cached entry. Returns the parsed dict or None for missing
    or expired keys (TTL elapsed). 404 on the wire."""
    raw = redis_client.get_redis().get(_key(draft_id))
    if raw is None:
        return None
    return json.loads(raw)
