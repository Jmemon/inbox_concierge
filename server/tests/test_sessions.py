from datetime import datetime, timezone
import uuid
import pytest
from app.db.models import User
from app.services import sessions as svc


@pytest.fixture
def user(db):
    u = User(id=uuid.uuid4().hex, email="alice@example.com", name="Alice", created_at=datetime.now(timezone.utc))
    db.add(u)
    db.commit()
    return u


def test_create_session_then_lookup_returns_it(db, user):
    sid = svc.create_session(db, user_id=user.id, ttl_seconds=3600)
    assert isinstance(sid, str) and len(sid) >= 32
    s = svc.lookup_active_session(db, session_id=sid)
    assert s is not None and s.user_id == user.id


def test_lookup_returns_none_for_revoked(db, user):
    sid = svc.create_session(db, user_id=user.id, ttl_seconds=3600)
    svc.revoke_session(db, session_id=sid)
    assert svc.lookup_active_session(db, session_id=sid) is None


def test_lookup_returns_none_for_expired(db, user):
    sid = svc.create_session(db, user_id=user.id, ttl_seconds=-1)  # already expired
    assert svc.lookup_active_session(db, session_id=sid) is None
