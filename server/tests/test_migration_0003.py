"""Integration test for migration 0003.

Boots a fresh sqlite db, runs `alembic upgrade head` (so 0001 → 0002 → 0003
fire in order), and asserts:
 - is_deleted column exists on buckets
 - the four default rows have new uuid-hex ids and structured criteria
 - inbox_threads rows previously pointing at default-important now point at
   the new uuid for "Important"
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


REPO_ROOT = Path(__file__).resolve().parents[1]


def _alembic_cfg(db_url: str) -> Config:
    # Override DATABASE_URL in env so that migrations/env.py (which calls
    # get_settings()) picks up the temp sqlite file rather than the real
    # postgres URL or the conftest in-memory URL. Also bust the lru_cache
    # so the new env var is picked up on the next call.
    os.environ["DATABASE_URL"] = db_url
    from app.config import get_settings
    get_settings.cache_clear()
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    return cfg


@pytest.fixture
def migrated_db(tmp_path):
    db_path = tmp_path / "mig.db"
    db_url = f"sqlite+pysqlite:///{db_path}"
    cfg = _alembic_cfg(db_url)
    command.upgrade(cfg, "0002_inbox")

    eng = create_engine(db_url, future=True)
    with eng.begin() as conn:
        conn.execute(text(
            "INSERT INTO users (id, email, created_at) VALUES "
            "('u1', 'a@b.com', '2026-04-30T00:00:00+00:00')"
        ))
        conn.execute(text(
            "INSERT INTO inbox_threads (id, user_id, gmail_id, subject, bucket_id, recent_message_id) VALUES "
            "('t1', 'u1', 'gT1', 'hi', 'default-important', NULL)"
        ))

    command.upgrade(cfg, "0003_buckets_v2")
    yield eng
    eng.dispose()


def test_is_deleted_column_exists(migrated_db):
    with migrated_db.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(buckets)")).all()
    cols = {r[1] for r in rows}
    assert "is_deleted" in cols


def test_default_buckets_have_new_uuid_ids_and_structured_criteria(migrated_db):
    with migrated_db.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, name, criteria, is_deleted FROM buckets WHERE user_id IS NULL"
        )).all()
    assert len(rows) == 4
    names = {r[1] for r in rows}
    assert names == {"Important", "Can wait", "Auto-archive", "Newsletter"}
    assert all(not r[0].startswith("default-") for r in rows), rows
    for _id, name, crit, is_del in rows:
        assert "<positive>" in crit, f"{name} missing structured positives"
        assert "<nearmiss>" in crit, f"{name} missing structured near-misses"
        assert is_del == 0, f"{name} should not be soft-deleted"


def test_inbox_threads_bucket_id_was_repointed(migrated_db):
    with migrated_db.connect() as conn:
        bid = conn.execute(text(
            "SELECT bucket_id FROM inbox_threads WHERE id = 't1'"
        )).scalar_one()
        new_id = conn.execute(text(
            "SELECT id FROM buckets WHERE name='Important' AND user_id IS NULL"
        )).scalar_one()
    assert bid == new_id


def test_old_default_rows_are_gone(migrated_db):
    with migrated_db.connect() as conn:
        rows = conn.execute(text(
            "SELECT id FROM buckets WHERE id LIKE 'default-%'"
        )).all()
    assert rows == []
