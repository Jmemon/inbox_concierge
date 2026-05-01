"""Inbox read/write helpers shared by api endpoints and celery workers.

All functions take a SQLAlchemy Session that the caller owns; this module
never commits. The caller (api request handler or worker task) controls the
transaction boundary so a sync job can write threads + messages + history-id
update atomically.
"""

import uuid
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from app.db.models import InboxMessage, InboxThread, User


def upsert_thread(
    db: Session,
    *,
    user_id: str,
    gmail_thread_id: str,
    subject: str | None,
    bucket_id: str | None,
) -> InboxThread:
    """Upsert one thread row by (user_id, gmail_thread_id).

    Concurrent inserts of the same (user_id, gmail_thread_id) will raise
    sqlalchemy.exc.IntegrityError on the second write — the unique constraint
    catches the SELECT-then-INSERT race. Worker tasks (workers/tasks.py) handle
    that by letting Celery retry the entire task; this module never catches.
    """
    stmt = select(InboxThread).where(
        InboxThread.user_id == user_id,
        InboxThread.gmail_id == gmail_thread_id,
    )
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        row = InboxThread(
            id=uuid.uuid4().hex,
            user_id=user_id,
            gmail_id=gmail_thread_id,
            subject=subject,
            bucket_id=bucket_id,
            recent_message_id=None,
        )
        db.add(row)
        db.flush()
    else:
        row.subject = subject if subject is not None else row.subject
        if bucket_id is not None:
            row.bucket_id = bucket_id
    return row


def upsert_message(
    db: Session,
    *,
    user_id: str,
    gmail_thread_id: str,
    gmail_message_id: str,
    gmail_internal_date: int,
    gmail_history_id: str,
    to_addr: str | None,
    from_addr: str | None,
    body_preview: str | None,
) -> InboxMessage:
    # Thread must already exist (caller is expected to upsert_thread first).
    thread = db.execute(
        select(InboxThread).where(
            InboxThread.user_id == user_id, InboxThread.gmail_id == gmail_thread_id
        )
    ).scalar_one()

    existing = db.execute(
        select(InboxMessage).where(
            InboxMessage.user_id == user_id,
            InboxMessage.gmail_id == gmail_message_id,
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = InboxMessage(
            id=uuid.uuid4().hex,
            thread_id=thread.id,
            user_id=user_id,
            gmail_id=gmail_message_id,
            gmail_thread_id=gmail_thread_id,
            gmail_internal_date=gmail_internal_date,
            gmail_history_id=gmail_history_id,
            to_addr=to_addr,
            from_addr=from_addr,
            body_preview=body_preview,
        )
        db.add(existing)
        db.flush()
    else:
        existing.gmail_internal_date = gmail_internal_date
        existing.gmail_history_id = gmail_history_id
        existing.to_addr = to_addr
        existing.from_addr = from_addr
        existing.body_preview = body_preview

    # Use a single indexed lookup instead of loading all thread messages.
    # inbox_messages.gmail_internal_date is indexed, so ORDER BY + LIMIT 1 is O(log N).
    most_recent_id = db.execute(
        select(InboxMessage.id)
        .where(InboxMessage.thread_id == thread.id)
        .order_by(InboxMessage.gmail_internal_date.desc())
        .limit(1)
    ).scalar_one_or_none()
    if most_recent_id is not None:
        thread.recent_message_id = most_recent_id

    return existing


def list_threads(
    db: Session, *, user_id: str, limit: int, offset: int
) -> list[InboxThread]:
    """Return threads for the user, most-recently-active first.

    Sort key is the gmail_internal_date of each thread's recent message. Threads
    with no messages yet (shouldn't happen post-sync, but defensively) sort to
    the bottom.
    """
    stmt = (
        select(InboxThread, InboxMessage.gmail_internal_date)
        .outerjoin(InboxMessage, InboxMessage.id == InboxThread.recent_message_id)
        .where(InboxThread.user_id == user_id)
        .order_by(InboxMessage.gmail_internal_date.desc().nulls_last())
        .limit(limit)
        .offset(offset)
    )
    return [row[0] for row in db.execute(stmt).all()]


def get_thread(db: Session, *, user_id: str, thread_id: str) -> InboxThread | None:
    return db.execute(
        select(InboxThread).where(
            InboxThread.id == thread_id, InboxThread.user_id == user_id
        )
    ).scalar_one_or_none()


def get_threads_batch(
    db: Session, *, user_id: str, thread_ids: list[str]
) -> list[InboxThread]:
    """Returns the InboxThread rows for the given ids, scoped to user_id.

    Threads not owned by user_id (or non-existent) are silently omitted; result
    order is NOT guaranteed to match thread_ids — caller sorts client-side using
    the id layer that already encodes the desired order.
    """
    if not thread_ids:
        return []
    stmt = select(InboxThread).where(
        InboxThread.user_id == user_id,
        InboxThread.id.in_(thread_ids),
    )
    return list(db.execute(stmt).scalars().all())


def get_message(db: Session, *, user_id: str, message_id: str) -> InboxMessage | None:
    """Fetch one message scoped to a user. Returns None if no such message
    exists OR if the message belongs to a different user — callers are NOT
    told which case occurred (no enumeration via 404 vs 403 split)."""
    return db.execute(
        select(InboxMessage).where(
            InboxMessage.id == message_id,
            InboxMessage.user_id == user_id,
        )
    ).scalar_one_or_none()


def update_user_history_id(db: Session, *, user_id: str, history_id: str) -> None:
    user = db.get(User, user_id)
    if user is not None:
        user.gmail_last_history_id = history_id


def clear_user_inbox(db: Session, *, user_id: str) -> None:
    """Wipe all inbox_threads + inbox_messages for one user.

    Used by full_sync_inbox to skip reconciliation: after a long offline gap
    or a 404 on history.list, just delete and repopulate from scratch.
    Order matters — messages have a FK to threads.
    """
    db.execute(delete(InboxMessage).where(InboxMessage.user_id == user_id))
    db.execute(delete(InboxThread).where(InboxThread.user_id == user_id))
