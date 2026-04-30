import time
import pytest
from itsdangerous import BadSignature
from app.services.state_cookie import make_state, verify_state


def test_make_and_verify_roundtrip():
    raw, signed = make_state()
    assert verify_state(cookie_value=raw, url_value=signed) is True


def test_verify_rejects_mismatched_cookie():
    _, signed = make_state()
    other_raw, _ = make_state()
    assert verify_state(cookie_value=other_raw, url_value=signed) is False


def test_verify_rejects_bad_signature():
    raw, signed = make_state()
    tampered = signed[:-2] + "AA"
    assert verify_state(cookie_value=raw, url_value=tampered) is False


def test_verify_rejects_expired(monkeypatch):
    raw, signed = make_state()
    # max_age=0 with a tiny sleep guarantees expiry
    time.sleep(1)
    assert verify_state(cookie_value=raw, url_value=signed, max_age_seconds=0) is False
