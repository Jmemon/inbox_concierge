from collections.abc import Iterator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.config import get_settings


def _normalize(url: str) -> str:
    # Railway provides postgresql://; SQLAlchemy 2.x prefers an explicit driver.
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


_settings = get_settings()
engine = create_engine(_normalize(_settings.database_url), pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
