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

import asyncio
import json
import logging
from sqlalchemy import select
from app.config import get_settings
from app.db.session import SessionLocal as _AppSessionLocal
from app.db.models import User, InboxThread, InboxMessage
from app.realtime import active_users, sync_lock
from app.realtime import redis_client as _redis_client
from app.gmail.client import get_gmail_client
from app.gmail.parser import assemble_thread, thread_to_string
from app.inbox import preview_cache
from app.llm import client as llm_client
from app.llm.prompts import score_thread
from app.workers import gmail_sync
from app.workers.celery_app import celery_app


SessionLocal = _AppSessionLocal
log = logging.getLogger(__name__)

# --- draft preview constants ---
# Maximum number of inbox threads to consider when scoring candidates.
CANDIDATE_LIMIT = 100
# If the candidate pool is below this, extend history inline before scoring.
EXTEND_THRESHOLD = 100
# How many scored results to surface in each category.
TOP_POSITIVES = 3
TOP_NEAR_MISSES = 3
# Score thresholds that define positive vs. near-miss.
POSITIVE_THRESHOLD = 7
NEAR_MISS_LOW = 4
NEAR_MISS_HIGH = 6


def _publish(user_id: str, event: str, payload: dict) -> None:
    """Typed publish — finalised in Task 15. All publishers go through here.

    Logs the redis subscriber count returned by `publish` so operations can
    diagnose delivery failures: subscribers=0 means no SSE-side dispatcher
    was listening on this user's channel at publish time (e.g. due to
    subscribe/unsubscribe churn during SSE flapping). The published frame
    is silently dropped by redis when nobody is subscribed.
    """
    body = json.dumps({"event": event, **payload})
    n = _redis_client.get_redis().publish(f"user:{user_id}", body)
    log.info("publish: user=%s event=%s subscribers=%d bytes=%d",
             user_id, event, n, len(body))


def _publish_thread_ids(user_id: str, thread_ids: list[str]) -> None:
    if not thread_ids:
        return
    log.info("_publish_thread_ids: user=%s count=%d", user_id, len(thread_ids))
    _publish(user_id, "threads_updated", {"thread_ids": thread_ids})


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


@celery_app.task(name="app.workers.tasks.draft_preview_bucket")
def draft_preview_bucket(user_id: str, draft_id: str, name: str, description: str,
                         exclude_thread_ids: list[str] | None = None) -> None:
    """Score inbox threads against a prospective bucket and publish a preview.

    Reads up to CANDIDATE_LIMIT inbox threads, inline-extends history if the
    pool is too small, refetches full bodies from Gmail, scores each thread
    0-10 via the LLM in parallel, then publishes a bucket_draft_preview event
    containing top-3 positives (>=7) and top-3 near-misses (4-6).
    """
    log.info("draft_preview_bucket: user=%s draft=%s", user_id, draft_id)
    exclude = set(exclude_thread_ids or [])
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user is None:
            return

        candidates = _read_candidates(db, user_id=user_id, exclude=exclude, limit=CANDIDATE_LIMIT)
        if len(candidates) < EXTEND_THRESHOLD:
            log.info("draft_preview: pool=%d < %d, extending inline", len(candidates), EXTEND_THRESHOLD)
            _extend_inline(db, user=user)
            candidates = _read_candidates(db, user_id=user_id, exclude=exclude, limit=CANDIDATE_LIMIT)

        gmail = get_gmail_client(db, user)
        scored = _score_all(gmail, candidates=candidates, name=name, description=description)

        positives = sorted([s for s in scored if s["score"] >= POSITIVE_THRESHOLD],
                           key=lambda s: -s["score"])[:TOP_POSITIVES]
        near = sorted([s for s in scored if NEAR_MISS_LOW <= s["score"] <= NEAR_MISS_HIGH],
                      key=lambda s: -s["score"])[:TOP_NEAR_MISSES]

        # Cache before publish: a polling client that arrives between the two
        # operations sees the ready result rather than stale "pending". The
        # cache is the source of truth; the SSE push is a perf optimization.
        preview_cache.store_result(draft_id, user_id=user_id,
                                   positives=positives, near_misses=near)

        _publish(user_id, "bucket_draft_preview", {
            "draft_id": draft_id, "positives": positives, "near_misses": near,
        })
    finally:
        db.close()


def _read_candidates(db, *, user_id: str, exclude: set[str], limit: int) -> list[dict]:
    """Query the DB for inbox threads to score, newest-first.

    Returns a list of dicts with keys: thread_id, gmail_thread_id, subject,
    sender, body_preview. Overfetches to account for excluded threads so the
    final pool is as close to `limit` as possible.
    """
    stmt = (
        select(InboxThread.id, InboxThread.gmail_id, InboxThread.subject,
               InboxMessage.from_addr, InboxMessage.body_preview, InboxMessage.gmail_internal_date)
        .outerjoin(InboxMessage, InboxMessage.id == InboxThread.recent_message_id)
        .where(InboxThread.user_id == user_id)
        .order_by(InboxMessage.gmail_internal_date.desc().nulls_last())
        .limit(limit + len(exclude))  # fetch extra so excludes don't shrink the pool
    )
    out = []
    for row in db.execute(stmt).all():
        tid, gid, subject, sender, preview, _date = row
        if tid in exclude:
            continue
        out.append({"thread_id": tid, "gmail_thread_id": gid, "subject": subject,
                    "sender": sender, "body_preview": preview})
        if len(out) >= limit:
            break
    return out


def _extend_inline(db, *, user) -> None:
    """Acquire the per-user sync lock, run extend_inbox_history, then release.

    Errors here are non-fatal — the preview will just score what's already
    stored. Skips silently if another sync already holds the lock.
    Note: extend_inbox_history is implemented in Task 13.
    """
    if not sync_lock.acquire(user.id):
        log.info("draft_preview: extend skipped, another sync holds the lock")
        return
    try:
        # Use the oldest gmail_internal_date in the inbox as the "before"
        # cursor so extend_inbox_history fetches messages older than those stored.
        oldest = db.execute(
            select(InboxMessage.gmail_internal_date)
            .where(InboxMessage.user_id == user.id)
            .order_by(InboxMessage.gmail_internal_date.asc()).limit(1)
        ).scalar_one_or_none()
        if oldest is None:
            return
        gmail_sync.extend_inbox_history(db, user=user, before_internal_date_ms=oldest)
    finally:
        sync_lock.release(user.id)


@celery_app.task(name="app.workers.tasks.extend_inbox_history")
def extend_inbox_history_task(user_id: str, before_internal_date_ms: int) -> None:
    """Pull older threads on demand for a user.

    Acquires the per-user sync_lock so it cannot race with a concurrent full
    or partial sync. Calls extend_inbox_history which issues gmail.threads.list
    with q=before:<unix-secs>, classifies+upserts each stub, and leaves
    gmail_last_history_id untouched (the cursor must stay anchored at the most-
    recent message so future partial syncs keep working). Publishes an
    extend_complete event with the list of internal thread ids and a 'more' flag
    that is True when Gmail returned the full page of 200 stubs (meaning there
    are likely even older threads available).
    """
    if not sync_lock.acquire(user_id):
        log.info("extend_task: user=%s syncing already, skip", user_id)
        return
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user is None:
            return
        log.info("extend_task: user=%s starting before_ms=%d", user_id, before_internal_date_ms)
        ids, more = gmail_sync.extend_inbox_history(
            db, user=user, before_internal_date_ms=before_internal_date_ms,
        )
        log.info("extend_task: user=%s upserted %d ids, more=%s; publishing", user_id, len(ids), more)
        _publish(user_id, "extend_complete", {"thread_ids": ids, "more": more})
    finally:
        db.close()
        sync_lock.release(user_id)


def _score_all(gmail, *, candidates: list[dict], name: str, description: str) -> list[dict]:
    """Refetch full thread bodies from Gmail sequentially, then score in parallel.

    Sequential Gmail fetches (~200ms each) are unavoidable because the DB only
    stores a 150-char body_preview; we need the full body for accurate scoring.
    LLM scoring runs concurrently under the shared AsyncAnthropic semaphore.
    """
    parsed_threads = []
    for c in candidates:
        try:
            resp = gmail.users().threads().get(
                userId="me", id=c["gmail_thread_id"], format="full"
            ).execute()
            parsed = assemble_thread(
                thread_id=c["gmail_thread_id"],
                raw_messages=resp.get("messages", []) or [],
            )
            parsed_threads.append((c, parsed))
        except Exception:
            log.exception("draft_preview: gmail.threads.get failed for %s", c["gmail_thread_id"])

    s = get_settings()

    async def _score_one(parsed):
        text = await llm_client.call_messages(
            model=s.anthropic_classify_model,
            system=score_thread.SYSTEM_PROMPT,
            user=score_thread.build_user_message(
                thread_str=thread_to_string(parsed), name=name, description=description),
        )
        return score_thread.parse_response(text)

    async def _all():
        return await asyncio.gather(*[_score_one(p) for _, p in parsed_threads])

    parsed_results = llm_client.run_in_loop(_all())

    out = []
    for (c, parsed), result in zip(parsed_threads, parsed_results):
        if not result:
            continue
        out.append({
            "thread_id": c["thread_id"], "subject": c["subject"], "sender": c["sender"],
            "score": result["score"], "rationale": result["rationale"],
            "snippet": result["snippet"],
        })
    return out
