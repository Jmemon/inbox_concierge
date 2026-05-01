from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from googleapiclient.errors import HttpError
from app.db.models import Base, User
from app.services import inbox_repo
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

    assert ids == ["gT1"]
    [thread] = inbox_repo.list_threads(db, user_id="u1", limit=10, offset=0)
    assert thread.gmail_id == "gT1"
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

    assert ids == ["gT1"]
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
