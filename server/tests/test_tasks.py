import os
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "1")

import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import fakeredis
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, User
from app.workers import tasks, gmail_sync


@pytest.fixture
def fake_redis(monkeypatch):
    r = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr("app.services.redis_client.get_redis", lambda: r)
    return r


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path}/test.db", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal


def _seed_user(session_factory, *, history_id="100"):
    db = session_factory()
    db.add(User(
        id="u1", email="x@y.com",
        created_at=datetime.now(timezone.utc),
        gmail_last_history_id=history_id,
    ))
    db.commit()
    db.close()


def _drained_pubsub(fake_redis, channel: str):
    ps = fake_redis.pubsub()
    ps.subscribe(channel)
    ps.get_message(timeout=0.1)  # drain the subscribe-confirmation
    return ps


def test_poll_new_messages_publishes_when_history_returns_records(
    fake_redis, session_factory, monkeypatch,
):
    """Happy path: history.list returns records → partial_sync called with them
    → ids published. history.list MUST be called by the task itself, not by
    partial_sync_inbox."""
    monkeypatch.setattr("app.workers.tasks.SessionLocal", session_factory)
    _seed_user(session_factory)
    ps = _drained_pubsub(fake_redis, "user:u1")

    fake_records = [{"id": "200", "messagesAdded": [{"message": {"id": "gM1", "threadId": "gT1"}}]}]

    gmail = MagicMock()
    with patch("app.workers.tasks.get_gmail_client", return_value=gmail), \
         patch("app.workers.tasks.gmail_sync.fetch_history_records",
               return_value=(fake_records, "200")) as mock_fetch, \
         patch("app.workers.tasks.gmail_sync.partial_sync_inbox",
               return_value=["gT1"]) as mock_partial:
        tasks.poll_new_messages.apply(args=["u1"])

    mock_fetch.assert_called_once()
    # The records fetched at task level must be passed through, not re-fetched.
    _, kwargs = mock_partial.call_args
    assert kwargs["history_records"] == fake_records
    assert kwargs["new_history_id"] == "200"

    msg = ps.get_message(timeout=1.0)
    assert msg and msg["type"] == "message"
    assert json.loads(msg["data"])["thread_ids"] == ["gT1"]


def test_poll_new_messages_silent_when_history_returns_no_records(
    fake_redis, session_factory, monkeypatch,
):
    """No new history records → no publish, no partial_sync call."""
    monkeypatch.setattr("app.workers.tasks.SessionLocal", session_factory)
    _seed_user(session_factory)
    ps = _drained_pubsub(fake_redis, "user:u1")

    gmail = MagicMock()
    with patch("app.workers.tasks.get_gmail_client", return_value=gmail), \
         patch("app.workers.tasks.gmail_sync.fetch_history_records",
               return_value=([], "100")), \
         patch("app.workers.tasks.gmail_sync.partial_sync_inbox") as mock_partial:
        tasks.poll_new_messages.apply(args=["u1"])

    mock_partial.assert_not_called()
    assert ps.get_message(timeout=0.2) is None  # nothing published


def test_poll_new_messages_falls_back_to_full_sync_on_404(
    fake_redis, session_factory, monkeypatch,
):
    """When history.list raises HistoryGoneError (gmail 404), the task must
    invoke full_sync_inbox and publish the resulting ids."""
    monkeypatch.setattr("app.workers.tasks.SessionLocal", session_factory)
    _seed_user(session_factory)
    ps = _drained_pubsub(fake_redis, "user:u1")

    gmail = MagicMock()
    with patch("app.workers.tasks.get_gmail_client", return_value=gmail), \
         patch("app.workers.tasks.gmail_sync.fetch_history_records",
               side_effect=gmail_sync.HistoryGoneError()), \
         patch("app.workers.tasks.gmail_sync.full_sync_inbox",
               return_value=["gT_new"]) as mock_full, \
         patch("app.workers.tasks.gmail_sync.partial_sync_inbox") as mock_partial:
        tasks.poll_new_messages.apply(args=["u1"])

    mock_full.assert_called_once()
    mock_partial.assert_not_called()

    msg = ps.get_message(timeout=1.0)
    assert msg and json.loads(msg["data"])["thread_ids"] == ["gT_new"]


def test_poll_new_messages_does_full_sync_when_user_has_no_history_id(
    fake_redis, session_factory, monkeypatch,
):
    """First-time poll (no cursor): skip history.list entirely, go full_sync."""
    monkeypatch.setattr("app.workers.tasks.SessionLocal", session_factory)
    _seed_user(session_factory, history_id=None)
    ps = _drained_pubsub(fake_redis, "user:u1")

    with patch("app.workers.tasks.gmail_sync.fetch_history_records") as mock_fetch, \
         patch("app.workers.tasks.gmail_sync.full_sync_inbox",
               return_value=["gT_a"]) as mock_full:
        tasks.poll_new_messages.apply(args=["u1"])

    mock_fetch.assert_not_called()
    mock_full.assert_called_once()
    msg = ps.get_message(timeout=1.0)
    assert msg and json.loads(msg["data"])["thread_ids"] == ["gT_a"]


def test_enqueue_polls_purges_and_fans_out(fake_redis, monkeypatch):
    fake_redis.zadd("active_users", {"u1": 99999999999, "u2": 99999999999})
    enqueued: list[str] = []
    monkeypatch.setattr("app.workers.tasks.poll_new_messages.apply_async",
                        lambda args, countdown=0: enqueued.append(args[0]))

    tasks.enqueue_polls.apply()

    assert sorted(enqueued) == ["u1", "u2"]
