import os
# Set test env BEFORE app modules load settings.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
# A real Fernet key (urlsafe base64-encoded 32 bytes). Constant for tests.
os.environ.setdefault("ENCRYPTION_KEY", "zmWNn3kP4nQwiX7rT2dSvR1mY8oC0bF6jH9aLuV3eUk=")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://testserver/auth/callback")
os.environ.setdefault("ENV", "development")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    s = TestSession()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()
