import pytest
from app.db.models import Bucket
from app.gmail.parser import ParsedMessage, ParsedThread
from app.llm import classify as classify_mod, client as llm_client


def _t(tid="gT1"):
    m = ParsedMessage(gmail_message_id=f"m_{tid}", gmail_thread_id=tid,
                      gmail_internal_date=1, gmail_history_id="1",
                      subject="s", from_addr="a@b", to_addr="me",
                      body_text="b", body_preview="b")
    return ParsedThread(gmail_thread_id=tid, subject="s", recent_internal_date=1, messages=[m])


def _b(id_, name): return Bucket(id=id_, user_id=None, name=name, criteria="x", is_deleted=False)


@pytest.fixture(autouse=True)
def _reset(): llm_client.reset_for_tests(); yield; llm_client.reset_for_tests()


def test_classify_preserves_order_and_handles_no_fit_stability(monkeypatch):
    answers = iter(['{"bucket_name": "X"}', '{"bucket_name": null}', '{"bucket_name": "GHOST"}'])
    async def _fake(**kw): return next(answers)
    monkeypatch.setattr(llm_client, "call_messages", _fake)

    out = classify_mod.classify(
        [_t("gT1"), _t("gT2"), _t("gT3")],
        [_b("b1", "X")],
        [None, "b1", "b1"],   # second is existing, third has unknown name from model
    )
    # T1: name "X" → b1. T2: null → keep existing b1. T3: unknown name → keep existing b1.
    assert out == ["b1", "b1", "b1"]


def test_classify_empty_or_no_buckets():
    assert classify_mod.classify([], [_b("b1", "X")], []) == []
    assert classify_mod.classify([_t()], [], [None]) == [None]
