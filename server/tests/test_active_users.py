import time
import fakeredis
import pytest
from app.realtime import active_users


@pytest.fixture
def fake_redis(monkeypatch):
    r = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr("app.realtime.redis_client.get_redis", lambda: r)
    return r


def test_purge_expired_drops_old_entries_only(fake_redis):
    fake_redis.zadd("active_users", {"u_expired": time.time() - 1})
    fake_redis.zadd("active_users", {"u_fresh": time.time() + 60})
    active_users.purge_expired()
    members = set(active_users.list_active())
    assert "u_expired" not in members and "u_fresh" in members


def test_refresh_extends_expiry_for_existing_member(fake_redis):
    active_users.add("u1", ttl_seconds=10)
    score_before = fake_redis.zscore("active_users", "u1")
    active_users.refresh("u1", ttl_seconds=300)
    score_after = fake_redis.zscore("active_users", "u1")
    assert score_after > score_before
