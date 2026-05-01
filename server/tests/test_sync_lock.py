import fakeredis
import pytest
from app.services import sync_lock


@pytest.fixture
def fake_redis(monkeypatch):
    r = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr("app.services.redis_client.get_redis", lambda: r)
    return r


def test_acquire_returns_true_then_false_until_released(fake_redis):
    assert sync_lock.acquire("u1") is True
    assert sync_lock.acquire("u1") is False
    sync_lock.release("u1")
    assert sync_lock.acquire("u1") is True


def test_acquire_locks_per_user_independently(fake_redis):
    assert sync_lock.acquire("u1") is True
    assert sync_lock.acquire("u2") is True
    assert sync_lock.acquire("u1") is False
    assert sync_lock.acquire("u2") is False
