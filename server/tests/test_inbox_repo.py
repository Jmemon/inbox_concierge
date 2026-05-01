from datetime import datetime, timezone
from app.db.models import Base, User
from app.services import inbox_repo


def _seed_user(db, uid="u1"):
    Base.metadata.create_all(db.get_bind())
    db.add(User(id=uid, email=f"{uid}@x.com", created_at=datetime.now(timezone.utc)))
    db.commit()


def test_upsert_thread_and_message_creates_rows(db):
    _seed_user(db)
    inbox_repo.upsert_thread(db, user_id="u1", gmail_thread_id="gT", subject="hi", bucket_id="default-important")
    inbox_repo.upsert_message(
        db, user_id="u1", gmail_thread_id="gT",
        gmail_message_id="gM", gmail_internal_date=2_000_000,
        gmail_history_id="42",
        to_addr="me@x.com", from_addr="alice@x.com", body_preview="hello",
    )
    db.commit()
    threads = inbox_repo.list_threads(db, user_id="u1", limit=10, offset=0)
    assert len(threads) == 1
    assert threads[0].subject == "hi"
    assert threads[0].recent_message_id is not None


def test_upsert_message_updates_recent_message_pointer(db):
    _seed_user(db)
    inbox_repo.upsert_thread(db, user_id="u1", gmail_thread_id="gT", subject="hi", bucket_id=None)
    inbox_repo.upsert_message(
        db, user_id="u1", gmail_thread_id="gT", gmail_message_id="gM1",
        gmail_internal_date=1_000_000, gmail_history_id="10",
        to_addr=None, from_addr=None, body_preview="first",
    )
    inbox_repo.upsert_message(
        db, user_id="u1", gmail_thread_id="gT", gmail_message_id="gM2",
        gmail_internal_date=2_000_000, gmail_history_id="11",
        to_addr=None, from_addr=None, body_preview="second",
    )
    db.commit()
    [t] = inbox_repo.list_threads(db, user_id="u1", limit=10, offset=0)
    recent = inbox_repo.get_message(db, message_id=t.recent_message_id)
    assert recent.body_preview == "second"


def test_list_threads_orders_by_recent_message_internal_date_desc(db):
    _seed_user(db)
    for i, ts in enumerate([3_000_000, 1_000_000, 2_000_000]):
        inbox_repo.upsert_thread(db, user_id="u1", gmail_thread_id=f"gT{i}", subject=f"s{i}", bucket_id=None)
        inbox_repo.upsert_message(
            db, user_id="u1", gmail_thread_id=f"gT{i}", gmail_message_id=f"gM{i}",
            gmail_internal_date=ts, gmail_history_id=str(ts),
            to_addr=None, from_addr=None, body_preview=str(i),
        )
    db.commit()
    threads = inbox_repo.list_threads(db, user_id="u1", limit=10, offset=0)
    assert [t.gmail_id for t in threads] == ["gT0", "gT2", "gT1"]
