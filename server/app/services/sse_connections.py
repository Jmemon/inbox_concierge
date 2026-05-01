"""Per-process map of userId → set of asyncio queues.

One queue per browser tab. Lives in module-level state because multiple
fastapi requests on the same uvicorn worker need to see the same map (an SSE
endpoint registers a queue, the pub/sub dispatcher reads from this map to
route incoming messages).

Not safe across multiple uvicorn worker processes — that's intentional. The
pub/sub dispatcher is per-process, so each process subscribes to redis on
behalf of its own queues.
"""

import asyncio
from typing import Iterable


_connections: dict[str, set[asyncio.Queue]] = {}


def add(user_id: str, queue: asyncio.Queue) -> bool:
    """Returns True iff this is the first queue for the user on this process."""
    is_first = user_id not in _connections
    _connections.setdefault(user_id, set()).add(queue)
    return is_first


def remove(user_id: str, queue: asyncio.Queue) -> bool:
    """Returns True iff that was the last queue for the user on this process."""
    queues = _connections.get(user_id)
    if queues is None:
        return False
    queues.discard(queue)
    if not queues:
        _connections.pop(user_id, None)
        return True
    return False


def iter_queues(user_id: str) -> Iterable[asyncio.Queue]:
    return tuple(_connections.get(user_id, ()))


def has_local(user_id: str) -> bool:
    return user_id in _connections


def reset() -> None:
    """Test hook only."""
    _connections.clear()
