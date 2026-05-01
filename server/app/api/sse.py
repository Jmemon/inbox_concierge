"""SSE endpoint.

Spec deviation: the spec writes /sse/{userId} but every other endpoint derives
the user from the session cookie. We do the same here so a tab can't subscribe
to someone else's stream by guessing a uuid.
"""

import asyncio
import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from app.db.models import User
from app.deps import get_current_user
from app.services import active_users, pubsub, sse_connections
from app.workers import tasks


router = APIRouter(prefix="/api", tags=["sse"])
log = logging.getLogger(__name__)

QUEUE_MAXSIZE = 100
HEARTBEAT_SECONDS = 20
ACTIVE_USERS_TTL_SECONDS = 60


@router.get("/sse")
async def sse(request: Request, user: User = Depends(get_current_user)):
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
    is_first = sse_connections.add(user.id, queue)

    if is_first:
        await pubsub.subscribe(user.id)
        active_users.add(user.id, ttl_seconds=ACTIVE_USERS_TTL_SECONDS)

    # Kickoff sync immediately so first inbox fetch sees fresh data.
    if user.gmail_last_history_id:
        tasks.poll_new_messages.apply_async(args=[user.id], countdown=0)
    else:
        tasks.full_sync_inbox_task.apply_async(args=[user.id], countdown=0)

    user_id = user.id  # capture before user goes out of scope across awaits

    async def event_stream():
        elapsed = 0.0
        try:
            while True:
                # Poll for disconnect in 1s slices so browser-tab-close is detected
                # quickly without blocking for the full HEARTBEAT_SECONDS window.
                # This also lets the TestClient disconnect properly in tests.
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=1.0)
                    elapsed = 0.0
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    elapsed += 1.0
                    if elapsed >= HEARTBEAT_SECONDS:
                        elapsed = 0.0
                        # keepalive frame + active-users TTL refresh
                        active_users.refresh(user_id, ttl_seconds=ACTIVE_USERS_TTL_SECONDS)
                        yield ": keepalive\n\n"
        finally:
            was_last = sse_connections.remove(user_id, queue)
            if was_last:
                try:
                    await pubsub.unsubscribe(user_id)
                except Exception:
                    log.exception("pubsub unsubscribe failed for %s", user_id)
                active_users.remove(user_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
