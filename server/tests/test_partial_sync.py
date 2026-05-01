from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from googleapiclient.errors import HttpError
from app.db.models import Base, User
from app.inbox import inbox_repo
from app.workers import gmail_sync


def _seed_user(db, *, history_id="100"):
    Base.metadata.create_all(db.get_bind())
    u = User(
        id="u1", email="a@b.com", created_at=datetime.now(timezone.utc),
        gmail_last_history_id=history_id,
    )
    db.add(u)
    db.commit()
    return u


def _fake_thread_payload(*, tid="gT1", mid="gM1", history_id="200", subject="hi", body=""):
    return {
        "id": tid, "messages": [{
            "id": mid, "threadId": tid, "internalDate": "1700000000000",
            "historyId": history_id,
            "payload": {
                "mimeType": "text/plain",
                "headers": [{"name": "Subject", "value": subject}],
                "body": {"data": body},
            },
        }],
    }


def test_partial_sync_uses_passed_records_without_calling_history(db):
    """When history_records is given, partial_sync must NOT call users.history.list."""
    u = _seed_user(db)
    gmail = MagicMock()
    gmail.users().threads().get().execute.return_value = _fake_thread_payload(tid="gT1", history_id="200")

    records = [{"id": "200", "messagesAdded": [{"message": {"id": "gM1", "threadId": "gT1"}}]}]

    with patch("app.workers.gmail_sync.get_gmail_client", return_value=gmail):
        ids = gmail_sync.partial_sync_inbox(
            db, user=u, history_records=records, new_history_id="200",
        )

    [thread] = inbox_repo.list_threads(db, user_id="u1", limit=10, offset=0)
    assert thread.gmail_id == "gT1"
    # The worker returns internal InboxThread.id (UUID hex), not gmail_thread_id.
    # /api/threads/batch filters by InboxThread.id, so SSE-published ids must
    # match that column.
    assert ids == [thread.id]
    assert db.get(User, "u1").gmail_last_history_id == "200"
    # Critical: history.list MUST NOT have been called when records were passed.
    gmail.users().history().list.assert_not_called()


def test_partial_sync_calls_history_when_records_none(db):
    """When history_records is None, partial_sync must fetch via history.list."""
    u = _seed_user(db)
    gmail = MagicMock()
    gmail.users().history().list.return_value.execute.return_value = {
        "history": [{"id": "200", "messagesAdded": [{"message": {"id": "gM1", "threadId": "gT1"}}]}],
        "historyId": "200",
    }
    gmail.users().threads().get().execute.return_value = _fake_thread_payload()

    with patch("app.workers.gmail_sync.get_gmail_client", return_value=gmail):
        ids = gmail_sync.partial_sync_inbox(db, user=u)

    [thread] = inbox_repo.list_threads(db, user_id="u1", limit=10, offset=0)
    assert ids == [thread.id]  # internal InboxThread.id, not gmail_thread_id
    gmail.users().history().list.assert_called()


def test_partial_sync_returns_empty_when_records_empty(db):
    """Empty records list short-circuits before any thread fetch."""
    u = _seed_user(db)
    gmail = MagicMock()

    with patch("app.workers.gmail_sync.get_gmail_client", return_value=gmail):
        ids = gmail_sync.partial_sync_inbox(
            db, user=u, history_records=[], new_history_id="100",
        )

    assert ids == []
    gmail.users().threads().get.assert_not_called()


def test_fetch_history_records_translates_404_to_history_gone_error(db):
    """fetch_history_records must raise HistoryGoneError on a 404 from gmail."""
    u = _seed_user(db)

    class _FakeResp:
        status = 404
        reason = "Not Found"

    gmail = MagicMock()
    gmail.users().history().list.return_value.execute.side_effect = HttpError(
        resp=_FakeResp(), content=b'{"error": "not found"}'
    )

    with patch("app.workers.gmail_sync.get_gmail_client", return_value=gmail):
        with pytest.raises(gmail_sync.HistoryGoneError):
            gmail_sync.fetch_history_records(gmail, start_history_id=u.gmail_last_history_id)


def test_full_sync_inbox_pulls_latest_200_threads_and_writes(db):
    u = _seed_user(db, history_id=None)

    listing = {"threads": [{"id": f"gT{i}"} for i in range(3)]}
    def _thread_fixture(thread_id: str) -> dict:
        return {
            "id": thread_id,
            "messages": [{
                "id": f"m_{thread_id}", "threadId": thread_id,
                "internalDate": "1700000000000",
                "historyId": "999",
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [{"name": "Subject", "value": thread_id}],
                    "body": {"data": ""},
                },
            }],
        }

    gmail = MagicMock()
    gmail.users().threads().list().execute.return_value = listing

    # Capture id from the .get() call args rather than .execute() kwargs —
    # the real Gmail API does not accept id in execute(), only in get().
    def _fake_threads_get(*, userId, id, format):
        inner = MagicMock()
        inner.execute.return_value = _thread_fixture(id)
        return inner
    gmail.users().threads().get.side_effect = _fake_threads_get

    with patch("app.workers.gmail_sync.get_gmail_client", return_value=gmail):
        ids = gmail_sync.full_sync_inbox(db, user=u)

    threads = inbox_repo.list_threads(db, user_id="u1", limit=10, offset=0)
    assert {t.gmail_id for t in threads} == {"gT0", "gT1", "gT2"}
    # full sync returns internal InboxThread.id, not gmail_thread_id (the SSE
    # publish path forwards these to /api/threads/batch which filters by .id).
    assert set(ids) == {t.id for t in threads}
    # full sync must populate last_history_id from the messages it ingested
    assert db.get(User, "u1").gmail_last_history_id == "999"


def test_full_sync_clears_existing_user_inbox_before_repopulating(db):
    """Per spec: 'easy option: throw out what was in there'. Stale rows must
    be deleted; the post-sync state should be exactly what gmail returned."""
    u = _seed_user(db, history_id=None)

    # Seed two stale threads that gmail's listing won't include.
    inbox_repo.upsert_thread(db, user_id="u1", gmail_thread_id="STALE_A", subject="old", bucket_id=None)
    inbox_repo.upsert_message(
        db, user_id="u1", gmail_thread_id="STALE_A", gmail_message_id="m_stale_a",
        gmail_internal_date=1, gmail_history_id="1",
        to_addr=None, from_addr=None, body_preview="old",
    )
    inbox_repo.upsert_thread(db, user_id="u1", gmail_thread_id="STALE_B", subject="old", bucket_id=None)
    db.commit()
    assert {t.gmail_id for t in inbox_repo.list_threads(db, user_id="u1", limit=10, offset=0)} \
        == {"STALE_A", "STALE_B"}

    listing = {"threads": [{"id": "gT_NEW"}]}
    new_thread = {
        "id": "gT_NEW",
        "messages": [{
            "id": "m_new", "threadId": "gT_NEW",
            "internalDate": "1700000000000", "historyId": "500",
            "payload": {
                "mimeType": "text/plain",
                "headers": [{"name": "Subject", "value": "fresh"}],
                "body": {"data": ""},
            },
        }],
    }
    gmail = MagicMock()
    gmail.users().threads().list().execute.return_value = listing
    gmail.users().threads().get().execute.return_value = new_thread

    with patch("app.workers.gmail_sync.get_gmail_client", return_value=gmail):
        ids = gmail_sync.full_sync_inbox(db, user=u)

    [thread] = inbox_repo.list_threads(db, user_id="u1", limit=10, offset=0)
    assert thread.gmail_id == "gT_NEW"
    assert ids == [thread.id]  # internal InboxThread.id, not gmail_thread_id
    surviving = {t.gmail_id for t in inbox_repo.list_threads(db, user_id="u1", limit=10, offset=0)}
    assert surviving == {"gT_NEW"}, f"stale rows leaked into post-sync state: {surviving}"
