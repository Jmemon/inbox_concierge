import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import UserSession


def create_session(db: Session, *, user_id: str, ttl_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    sid = secrets.token_urlsafe(32)
    row = UserSession(
        id=sid,
        user_id=user_id,
        created_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
        last_seen_at=now,
        revoked_at=None,
    )
    db.add(row)
    db.commit()
    return sid


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def lookup_active_session(db: Session, *, session_id: str) -> UserSession | None:
    if not session_id:
        return None
    now = datetime.now(timezone.utc)
    stmt = select(UserSession).where(UserSession.id == session_id)
    row = db.execute(stmt).scalar_one_or_none()
    if row is None or row.revoked_at is not None or _aware(row.expires_at) <= now:
        return None
    row.last_seen_at = now
    db.commit()
    return row


def revoke_session(db: Session, *, session_id: str) -> None:
    row = db.get(UserSession, session_id)
    if row is None:
        return
    row.revoked_at = datetime.now(timezone.utc)
    db.commit()
