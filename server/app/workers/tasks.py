"""Celery task definitions.

Each task opens its own SQLAlchemy session (workers run outside the FastAPI
request lifecycle, so they can't lean on Depends(get_db)).

`SessionLocal` is referenced as a module-level attribute so tests can monkey-
patch it onto an in-memory engine.

poll_new_messages owns the history.list call so it can:
 - return silently when there are no new records (don't publish on noise),
 - fall back to full_sync when gmail 404s (cursor expired past the ~30 day
   retention window), and
 - hand the records through to partial_sync_inbox to avoid a redundant fetch.
"""

import json
import logging
from app.db.session import SessionLocal as _AppSessionLocal
from app.db.models import User
from app.services import active_users, sync_lock
from app.services import redis_client as _redis_client
from app.services.gmail import get_gmail_client
from app.workers import gmail_sync
from app.workers.celery_app import celery_app


SessionLocal = _AppSessionLocal
log = logging.getLogger(__name__)


def _publish_thread_ids(user_id: str, thread_ids: list[str]) -> None:
    if not thread_ids:
        return
    channel = f"user:{user_id}"
    log.info("_publish_thread_ids: channel=%s count=%d", channel, len(thread_ids))
    payload = json.dumps({"thread_ids": thread_ids})
    _redis_client.get_redis().publish(channel, payload)


@celery_app.task(name="app.workers.tasks.enqueue_polls")
def enqueue_polls() -> None:
    """Beat fan-out: purge expired entries, then enqueue one poll per active user."""
    active_users.purge_expired()
    active = list(active_users.list_active())
    log.info("enqueue_polls: found %d active users: %s", len(active), active)
    for uid in active:
        # Random 0-10s spread happens at apply_async time. Use a fixed countdown of
        # 0 here for determinism in tests; production beat schedule could randomize.
        poll_new_messages.apply_async(args=[uid], countdown=0)


@celery_app.task(name="app.workers.tasks.poll_new_messages")
def poll_new_messages(user_id: str) -> None:
    """Sync new messages for one user and publish updated thread ids.

    Flow:
     1. No history cursor yet → full_sync_inbox (bootstrap).
     2. Cursor present → call history.list:
        - 404 → HistoryGoneError → full_sync_inbox (recovery).
        - empty records → return silently.
        - records → partial_sync_inbox(history_records, new_history_id).
     3. Publish touched thread ids on user:{user_id}.

    Holds a per-user redis lock for the duration so a concurrent
    full_sync_inbox_task or another beat-driven poll can't race on the
    (user_id, gmail_id) unique constraint and leave the inbox half-synced.
    """
    log.info("poll_new_messages: start user=%s", user_id)
    if not sync_lock.acquire(user_id):
        log.info("poll_new_messages: user=%s already syncing, skipping", user_id)
        return
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user is None:
            log.warning("poll_new_messages: user %s not found", user_id)
            return

        if not user.gmail_last_history_id:
            log.info("poll_new_messages: user=%s has no history cursor → full sync", user_id)
            ids = gmail_sync.full_sync_inbox(db, user=user)
            log.info("poll_new_messages: user=%s full sync complete, publishing %d ids", user_id, len(ids))
            _publish_thread_ids(user_id, ids)
            return

        gmail = get_gmail_client(db, user)
        try:
            history_records, new_history_id = gmail_sync.fetch_history_records(
                gmail, start_history_id=user.gmail_last_history_id,
            )
        except gmail_sync.HistoryGoneError:
            log.info("poll_new_messages: history 404 for %s; falling back to full sync", user_id)
            ids = gmail_sync.full_sync_inbox(db, user=user)
            log.info("poll_new_messages: user=%s recovery full sync complete, publishing %d ids", user_id, len(ids))
            _publish_thread_ids(user_id, ids)
            return

        if not history_records:
            log.info("poll_new_messages: user=%s history returned 0 records → no publish", user_id)
            return  # silent: no new changes

        log.info("poll_new_messages: user=%s got %d history records → partial sync", user_id, len(history_records))
        ids = gmail_sync.partial_sync_inbox(
            db, user=user,
            history_records=history_records,
            new_history_id=new_history_id,
        )
        log.info("poll_new_messages: user=%s partial sync complete, publishing %d ids", user_id, len(ids))
        _publish_thread_ids(user_id, ids)
    finally:
        db.close()
        sync_lock.release(user_id)


@celery_app.task(name="app.workers.tasks.full_sync_inbox")
def full_sync_inbox_task(user_id: str) -> None:
    """Explicit full-sync entry point. Used by the SSE-on-connect kickoff and
    by POST /api/inbox/refresh when the user has no history cursor.

    Holds the same per-user lock poll_new_messages uses, so the SSE kickoff
    and a concurrent beat-driven poll can't both try to fan out 200 inserts
    against the unique constraint at the same time.
    """
    log.info("full_sync_inbox_task: start user=%s", user_id)
    if not sync_lock.acquire(user_id):
        log.info("full_sync_inbox_task: user=%s already syncing, skipping", user_id)
        return
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user is None:
            log.warning("full_sync_inbox_task: user %s not found", user_id)
            return
        ids = gmail_sync.full_sync_inbox(db, user=user)
        log.info("full_sync_inbox_task: user=%s complete, publishing %d ids", user_id, len(ids))
        _publish_thread_ids(user_id, ids)
    finally:
        db.close()
        sync_lock.release(user_id)
