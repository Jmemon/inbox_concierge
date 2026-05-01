import asyncio
from app.realtime import sse_connections


def test_first_and_last_connection_signaling():
    sse_connections.reset()
    q1, q2 = asyncio.Queue(), asyncio.Queue()
    assert sse_connections.add("u1", q1) is True    # first ever for u1
    assert sse_connections.add("u1", q2) is False   # second tab, not first
    assert sse_connections.remove("u1", q1) is False  # one tab still open
    assert sse_connections.remove("u1", q2) is True   # last one out
