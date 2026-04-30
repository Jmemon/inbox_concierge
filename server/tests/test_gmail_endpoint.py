from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.models import Base
from app.db.session import get_db
from app.services import google_oauth


@pytest.fixture
def client_with_session(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path}/test.db", future=True)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _get_db_override():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db_override
    c = TestClient(app)

    # Authenticate via the callback path with a mocked exchange
    login = c.get("/auth/login", follow_redirects=False)
    from urllib.parse import urlparse, parse_qs
    state_in_url = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    fake = google_oauth.ExchangedTokens(
        access_token="ya29.fake",
        refresh_token="1//fake-refresh",
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),  # far-future, no refresh needed
        email="alice@example.com",
        name="Alice",
    )
    with patch("app.api.auth.google_oauth.exchange_code", return_value=fake):
        c.get(f"/auth/callback?code=x&state={state_in_url}", follow_redirects=False)

    yield c
    app.dependency_overrides.clear()
    engine.dispose()


def test_gmail_profile_requires_auth():
    c = TestClient(app)
    r = c.get("/api/gmail/profile")
    assert r.status_code == 401


def test_gmail_profile_returns_summary_when_authed(client_with_session):
    fake_summary = {
        "email": "alice@example.com",
        "messages_total": 10,
        "threads_total": 5,
        "recent_subjects": ["hi", "hello", "hola"],
    }
    with patch("app.api.gmail.gmail_service.fetch_profile_summary", return_value=fake_summary):
        r = client_with_session.get("/api/gmail/profile")
    assert r.status_code == 200
    assert r.json() == fake_summary
