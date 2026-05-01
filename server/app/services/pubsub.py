"""Async pub/sub dispatcher.

One persistent task per uvicorn worker process. Subscribes to per-user channels
on demand (SSE endpoint calls `subscribe(user_id)` on first connection for that
user, `unsubscribe(user_id)` on last disconnect). Reads messages and routes
them into the local in-memory queues registered by SSE handlers.

Backpressure: if a queue is full (slow consumer), drop the message rather than
blocking the dispatcher. Per the homepage spec, slow consumers are tolerated.

IMPORTANT: `get_async_redis` is accessed via the `redis_client` module attribute
(not imported directly) so that test monkeypatches on
`app.services.redis_client.get_async_redis` take effect inside this module.
"""

import asyncio
import logging
from app.services import sse_connections
from app.services import redis_client as redis_client_module


log = logging.getLogger(__name__)


class PubSubDispatcher:
    def __init__(self) -> None:
        self._pubsub = None
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        # Set on first subscribe(). Until then, the dispatcher task waits and
        # touches no network — important so tests that boot the FastAPI lifespan
        # without redis (e.g. existing auth tests) keep working.
        self._has_subscription = asyncio.Event()

    async def start(self) -> None:
        async with self._lock:
            if self._task is not None:
                return
            self._task = asyncio.create_task(self._run(), name="pubsub-dispatcher")
            log.info("pubsub: dispatcher task created")

    async def stop(self) -> None:
        async with self._lock:
            if self._task is None:
                return
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
            if self._pubsub is not None:
                try:
                    await self._pubsub.aclose()
                except Exception:
                    pass
                self._pubsub = None

    async def subscribe(self, user_id: str) -> None:
        if self._pubsub is None:
            # Access via module attribute so monkeypatches on the module take effect.
            self._pubsub = redis_client_module.get_async_redis().pubsub()
        channel = f"user:{user_id}"
        log.info("pubsub: subscribing to channel %s", channel)
        await self._pubsub.subscribe(channel)
        self._has_subscription.set()

    async def unsubscribe(self, user_id: str) -> None:
        if self._pubsub is None:
            return
        channel = f"user:{user_id}"
        log.info("pubsub: unsubscribing from channel %s", channel)
        await self._pubsub.unsubscribe(channel)

    async def _run(self) -> None:
        # Wait until at least one channel is subscribed before touching the network.
        log.info("pubsub: dispatcher waiting on first subscription")
        await self._has_subscription.wait()
        log.info("pubsub: dispatcher entering listen loop")
        assert self._pubsub is not None
        try:
            async for raw in self._pubsub.listen():
                # Skip subscribe/unsubscribe confirmation frames; only process real messages.
                msg_type = raw.get("type") if raw else None
                if raw is None or msg_type != "message":
                    log.debug("pubsub: skipping frame type=%s", msg_type)
                    continue
                channel = raw.get("channel", "")
                if not channel.startswith("user:"):
                    log.debug("pubsub: skipping non-user channel=%s", channel)
                    continue
                user_id = channel[len("user:"):]
                data = raw.get("data")
                queues = list(sse_connections.iter_queues(user_id))
                log.info("pubsub: message on channel=%s type=%s routed to %d queues", channel, msg_type, len(queues))
                for queue in queues:
                    try:
                        # Use put_nowait so a slow consumer can't block the dispatcher loop.
                        queue.put_nowait(data)
                    except asyncio.QueueFull:
                        log.warning("dropping pubsub message for %s; queue full", user_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("pubsub dispatcher crashed")


# Module-level singleton, started by FastAPI lifespan.
_dispatcher = PubSubDispatcher()


async def start() -> None:
    await _dispatcher.start()


async def stop() -> None:
    await _dispatcher.stop()


async def subscribe(user_id: str) -> None:
    await _dispatcher.subscribe(user_id)


async def unsubscribe(user_id: str) -> None:
    await _dispatcher.unsubscribe(user_id)
