"""bucket_repo policy tests. SQLAlchemy passthroughs (insert returns row,
mutation persists, etc) aren't tested — only the rules the api layer relies
on: per-user scoping, soft-delete filtering, and the criteria builder."""

from datetime import datetime, timezone
import pytest
from app.db.models import Bucket, User
from app.inbox import bucket_repo


@pytest.fixture
def db_with_defaults(db):
    db.add(User(id="u1", email="a@b.com", created_at=datetime.now(timezone.utc)))
    db.add(User(id="u2", email="c@d.com", created_at=datetime.now(timezone.utc)))
    db.add(Bucket(id="def-important", user_id=None, name="Important",
                  criteria="x", is_deleted=False))
    db.commit()
    return db


def test_list_active_includes_user_customs_and_excludes_soft_deleted(db_with_defaults):
    bucket_repo.create_custom(db_with_defaults, user_id="u1", name="Kept", criteria="x")
    deleted = bucket_repo.create_custom(db_with_defaults, user_id="u1",
                                         name="Deleted", criteria="x")
    db_with_defaults.commit()
    bucket_repo.soft_delete(db_with_defaults, deleted)
    db_with_defaults.commit()

    names = {b.name for b in bucket_repo.list_active(db_with_defaults, user_id="u1")}
    assert names == {"Important", "Kept"}


def test_list_active_excludes_other_users_buckets(db_with_defaults):
    bucket_repo.create_custom(db_with_defaults, user_id="u2",
                              name="Theirs", criteria="x")
    db_with_defaults.commit()
    names = {b.name for b in bucket_repo.list_active(db_with_defaults, user_id="u1")}
    assert "Theirs" not in names


def test_formulate_criteria_produces_tagged_blocks_in_default_format():
    text = bucket_repo.formulate_criteria(
        description="Book club emails.",
        confirmed_positives=[{"sender": "club@b.com", "subject": "march pick",
                              "snippet": "Beloved", "rationale": "club"}],
        confirmed_negatives=[{"sender": "marketing@v.com", "subject": "sale",
                              "snippet": "20% off", "rationale": "marketing"}],
    )
    assert "Book club emails." in text
    assert "Example cases:" in text
    assert "<positive>" in text and "Beloved" in text
    assert "<nearmiss>" in text and "20% off" in text
