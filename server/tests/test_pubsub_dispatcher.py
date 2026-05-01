import asyncio
import json
import pytest
import fakeredis.aioredis
from app.services import pubsub, sse_connections


@pytest.mark.asyncio
async def test_dispatcher_routes_messages_to_local_queues(monkeypatch):
    sse_connections.reset()
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.services.redis_client.get_async_redis", lambda: fake)
    monkeypatch.setattr("app.services.pubsub._dispatcher", pubsub.PubSubDispatcher())

    q = asyncio.Queue()
    sse_connections.add("u1", q)
    await pubsub.subscribe("u1")
    await pubsub.start()

    await fake.publish("user:u1", json.dumps({"thread_ids": ["t1"]}))

    msg = await asyncio.wait_for(q.get(), timeout=1.0)
    assert json.loads(msg) == {"thread_ids": ["t1"]}

    await pubsub.stop()
