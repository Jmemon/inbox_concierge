"""Tests for the /api/sse endpoint.

Design note on TestClient + SSE: Starlette's synchronous TestClient blocks in
portal.call() until the full ASGI response completes. An infinite SSE generator
never completes, so we patch fastapi.responses.StreamingResponse in the sse
module to use a finite async generator instead — this lets the TestClient
complete and allows us to check status, headers, and side-effects normally.
"""
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock
import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient
from fastapi.responses import StreamingResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.models import Base, User
from app.db.session import get_db
from app.services import sessions, sse_connections


@pytest.fixture
def authed_client(tmp_path, monkeypatch):
    sse_connections.reset()
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.services.redis_client.get_async_redis", lambda: fake)
    import fakeredis as fakeredis_sync
    monkeypatch.setattr("app.services.redis_client.get_redis",
                        lambda: fakeredis_sync.FakeStrictRedis(decode_responses=True))

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path}/test.db", future=True)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _get_db():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()
    app.dependency_overrides[get_db] = _get_db

    db = TestSession()
    db.add(User(id="u1", email="a@b.com", created_at=datetime.now(timezone.utc), gmail_last_history_id="100"))
    db.commit()
    sid = sessions.create_session(db, user_id="u1", ttl_seconds=600)
    db.close()

    c = TestClient(app)
    c.cookies.set("session", sid)
    yield c
    app.dependency_overrides.clear()


def test_sse_unauthorized_without_session():
    c = TestClient(app)
    r = c.get("/api/sse", headers={"accept": "text/event-stream"})
    assert r.status_code == 401


def test_sse_returns_stream_and_kickoff_enqueued(authed_client):
    """SSE connection returns correct headers and enqueues a kickoff task.

    Starlette's TestClient blocks until the ASGI response completes, so we
    patch StreamingResponse in the sse module to replace the infinite generator
    with a single-frame finite one. This lets the TestClient complete while
    still exercising the full endpoint handler path (auth, kickoff task, headers).
    """

    async def _finite_generator():
        """Yields one SSE comment and stops — makes the TestClient unblock."""
        yield ": connected\n\n"

    # We intercept StreamingResponse construction inside app.api.sse so the
    # infinite event_stream() is replaced with our finite generator.
    _original_StreamingResponse = StreamingResponse

    def _patched_StreamingResponse(content, **kwargs):
        # Replace whatever async generator was passed with our finite one,
        # preserving all other kwargs (media_type, headers).
        return _original_StreamingResponse(_finite_generator(), **kwargs)

    with patch("app.api.sse.tasks.poll_new_messages.apply_async") as mock_apply, \
         patch("app.api.sse.pubsub.subscribe", new_callable=AsyncMock), \
         patch("app.api.sse.active_users.add"), \
         patch("app.api.sse.StreamingResponse", side_effect=_patched_StreamingResponse):

        with authed_client.stream("GET", "/api/sse") as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            assert r.headers.get("x-accel-buffering") == "no"
            # close immediately; we just want to verify headers + kickoff

        mock_apply.assert_called_once()
