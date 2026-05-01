"""Gmail sync logic, called by celery tasks.

Three entry points:
 - fetch_history_records: thin wrapper around users.history.list. Translates a
   404 (cursor older than gmail's ~30-day window) into HistoryGoneError so the
   caller can fall back to a full sync.
 - partial_sync_inbox: incremental writer. Optionally takes pre-fetched
   history_records so poll_new_messages can call history.list once and pass
   the result through (per spec: "called by poll_new_messages. also reusable
   for full sync. if history_records is null, fetch via users.history.list").
 - full_sync_inbox: bootstrap / 404-recovery. Clears existing inbox rows for
   the user and repopulates from the latest 200 threads.

All three commit internally and return the list of gmail_thread_ids that were
touched. Returning ids only (not full thread payloads) keeps callers — the SSE
publish path in tasks.py — small: the data is in postgres for the api to read.
"""

import logging

from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.models import Bucket, User
from app.services import inbox_repo
from app.services.classification import classify
from app.services.gmail import get_gmail_client
from app.services.message_parser import assemble_thread, ParsedThread


log = logging.getLogger(__name__)


class HistoryGoneError(Exception):
    """users.history.list returned 404. The startHistoryId is older than the
    ~30-day window Gmail keeps. Caller should fall back to a full sync."""


def _available_bucket_ids(db: Session, user_id: str) -> list[str]:
    """Default buckets (user_id IS NULL) plus any custom buckets owned by user."""
    rows = db.execute(
        select(Bucket).where((Bucket.user_id == None) | (Bucket.user_id == user_id))  # noqa: E711
    ).scalars().all()
    return [b.id for b in rows]


def _upsert_thread_with_messages(
    db: Session, *, user_id: str, parsed: ParsedThread, bucket_ids: list[str]
) -> str:
    """Classify the thread, then write it and all its messages to postgres.

    Caller is responsible for the surrounding transaction (db.commit happens
    in partial_sync_inbox / full_sync_inbox).

    Returns the internal InboxThread.id (UUID hex). This is the id the api +
    client use everywhere to identify a thread; the worker returns it so the
    SSE publish path can carry the same identifier — sending gmail_thread_id
    instead would make /api/threads/batch (which filters by InboxThread.id)
    return zero rows.
    """
    # Skip classification when no buckets exist yet (e.g. fresh test DB or
    # first-time user before default buckets are seeded). bucket_id is nullable.
    bucket_id = classify(parsed, bucket_ids) if bucket_ids else None
    thread = inbox_repo.upsert_thread(
        db,
        user_id=user_id,
        gmail_thread_id=parsed.gmail_thread_id,
        subject=parsed.subject,
        bucket_id=bucket_id,
    )
    for m in parsed.messages:
        inbox_repo.upsert_message(
            db,
            user_id=user_id,
            gmail_thread_id=parsed.gmail_thread_id,
            gmail_message_id=m.gmail_message_id,
            gmail_internal_date=m.gmail_internal_date,
            gmail_history_id=m.gmail_history_id,
            to_addr=m.to_addr,
            from_addr=m.from_addr,
            body_preview=m.body_preview,
        )
    return thread.id


def fetch_history_records(
    gmail_client, *, start_history_id: str
) -> tuple[list[dict], str | None]:
    """Call users.history.list and return (records, latest_history_id).

    Raises HistoryGoneError when gmail returns 404 (the cursor is past the
    retention window). All other HttpErrors propagate.
    """
    log.info("fetch_history_records: start_history_id=%s", start_history_id)
    try:
        resp = gmail_client.users().history().list(
            userId="me",
            startHistoryId=start_history_id,
            historyTypes=["messageAdded"],
        ).execute()
    except HttpError as e:
        if getattr(e.resp, "status", None) == 404:
            raise HistoryGoneError() from e
        raise
    history = resp.get("history", []) or []
    new_history_id = resp.get("historyId")
    log.info("fetch_history_records: got %d records, new historyId=%s", len(history), new_history_id)
    return history, new_history_id


def partial_sync_inbox(
    db: Session, *,
    user: User,
    history_records: list[dict] | None = None,
    new_history_id: str | None = None,
) -> list[str]:
    """Incremental sync.

    If history_records is None, fetches them via fetch_history_records (which
    may raise HistoryGoneError; caller decides what to do with that). When the
    caller already has the records — e.g. poll_new_messages just called
    history.list to decide whether to publish — they pass them through to
    avoid a redundant API call.

    Writes touched threads + their messages to postgres in one transaction.
    Returns the list of internal InboxThread.id values (UUID hex) that were
    upserted — NOT gmail_thread_ids. The SSE publish path forwards these to
    /api/threads/batch, which filters by InboxThread.id.
    """
    records_provided = history_records is not None
    log.info(
        "partial_sync_inbox: user=%s records_provided=%s",
        user.id, records_provided,
    )
    gmail = get_gmail_client(db, user)
    bucket_ids = _available_bucket_ids(db, user.id)

    if history_records is None:
        history_records, new_history_id = fetch_history_records(
            gmail, start_history_id=user.gmail_last_history_id or "0",
        )

    if not history_records:
        log.info("partial_sync_inbox: user=%s no history records → returning empty", user.id)
        return []

    touched_gmail_ids: set[str] = set()
    for record in history_records:
        # v1 only handles messagesAdded; messagesDeleted is out of scope (users can't delete).
        for added in record.get("messagesAdded", []) or []:
            tid = (added.get("message") or {}).get("threadId")
            if tid:
                touched_gmail_ids.add(tid)

    log.info(
        "partial_sync_inbox: user=%s touched %d thread ids, fetching each",
        user.id, len(touched_gmail_ids),
    )
    internal_ids: list[str] = []
    for tid in touched_gmail_ids:
        log.info("partial_sync_inbox: fetching thread %s for user=%s", tid, user.id)
        thread_resp = gmail.users().threads().get(userId="me", id=tid, format="full").execute()
        parsed = assemble_thread(thread_id=tid, raw_messages=thread_resp.get("messages", []) or [])
        internal_id = _upsert_thread_with_messages(
            db, user_id=user.id, parsed=parsed, bucket_ids=bucket_ids,
        )
        internal_ids.append(internal_id)

    if new_history_id:
        inbox_repo.update_user_history_id(db, user_id=user.id, history_id=str(new_history_id))
    db.commit()
    log.info(
        "partial_sync_inbox: user=%s done, %d threads upserted",
        user.id, len(internal_ids),
    )
    return internal_ids


def full_sync_inbox(db: Session, *, user: User) -> list[str]:
    """Bootstrap / 404-recovery sync.

    Per the workers spec ("easy option: throw out what was in there"), this
    deletes the user's existing inbox_threads + inbox_messages and repopulates
    from the 200 most-recently-active gmail threads. Avoids reconciliation
    complexity for long offline gaps or expired history cursors.

    Returns the list of internal InboxThread.id values (UUID hex) that were
    upserted — NOT gmail_thread_ids. The SSE publish path forwards these to
    /api/threads/batch, which filters by InboxThread.id. Commits internally.
    """
    log.info("full_sync_inbox: start user=%s", user.id)
    gmail = get_gmail_client(db, user)
    bucket_ids = _available_bucket_ids(db, user.id)

    # Nuke first. Order: messages → threads (FK constraint).
    inbox_repo.clear_user_inbox(db, user_id=user.id)
    db.flush()

    listing = gmail.users().threads().list(userId="me", maxResults=200).execute()
    thread_stubs = listing.get("threads", []) or []
    log.info("full_sync_inbox: user=%s listing returned %d thread stubs", user.id, len(thread_stubs))

    internal_ids: list[str] = []
    max_history_id: int = 0
    for stub in thread_stubs:
        tid = stub["id"]
        log.info("full_sync_inbox: fetching thread %s for user=%s", tid, user.id)
        thread_resp = gmail.users().threads().get(userId="me", id=tid, format="full").execute()
        parsed = assemble_thread(thread_id=tid, raw_messages=thread_resp.get("messages", []) or [])
        internal_id = _upsert_thread_with_messages(
            db, user_id=user.id, parsed=parsed, bucket_ids=bucket_ids,
        )
        internal_ids.append(internal_id)
        for m in parsed.messages:
            try:
                hid = int(m.gmail_history_id)
            except (TypeError, ValueError):
                continue
            if hid > max_history_id:
                max_history_id = hid

    if max_history_id:
        inbox_repo.update_user_history_id(db, user_id=user.id, history_id=str(max_history_id))
    db.commit()
    log.info(
        "full_sync_inbox: user=%s done, %d threads touched, max_history_id=%d",
        user.id, len(internal_ids), max_history_id,
    )
    return internal_ids
