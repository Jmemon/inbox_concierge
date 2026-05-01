"""Anthropic client wrapper.

Owns one AsyncAnthropic per worker process + one asyncio.Semaphore(N) bound
to a long-lived background event loop, plus a run_in_loop sync bridge for
Celery callers. Lazy-init per fork. call_messages returns "" on any error
so per-thread classify failures degrade to no-fit instead of crashing a batch.
"""

import asyncio
import logging
import threading
from typing import Any
from anthropic import AsyncAnthropic
from app.config import get_settings

log = logging.getLogger(__name__)

_state: dict[str, Any] = {"loop": None, "thread": None, "sem": None, "client": None}
_init_lock = threading.Lock()


def _ensure_initialized() -> None:
    if _state["loop"] is not None:
        return
    with _init_lock:
        if _state["loop"] is not None:
            return
        loop = asyncio.new_event_loop()
        ready = threading.Event()

        def _run() -> None:
            asyncio.set_event_loop(loop)
            ready.set()
            loop.run_forever()

        thread = threading.Thread(target=_run, name="llm-loop", daemon=True)
        thread.start()
        ready.wait()

        s = get_settings()
        sem = asyncio.run_coroutine_threadsafe(
            _build_semaphore(s.anthropic_concurrency), loop
        ).result()
        client = AsyncAnthropic(api_key=s.anthropic_api_key)
        _state.update(loop=loop, thread=thread, sem=sem, client=client)
        log.info("llm.client: initialized loop + semaphore(n=%d)", s.anthropic_concurrency)


async def _build_semaphore(n: int) -> asyncio.Semaphore:
    return asyncio.Semaphore(n)


def run_in_loop(coro):
    _ensure_initialized()
    return asyncio.run_coroutine_threadsafe(coro, _state["loop"]).result()


async def call_messages(*, model: str, system: str, user: str, max_tokens: int = 1024) -> str:
    _ensure_initialized()
    sem: asyncio.Semaphore = _state["sem"]
    client: AsyncAnthropic = _state["client"]
    async with sem:
        try:
            resp = await client.messages.create(
                model=model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}],
            )
            return "".join(b.text for b in resp.content if hasattr(b, "text"))
        except Exception:
            log.exception("anthropic messages.create failed")
            return ""


def reset_for_tests() -> None:
    if _state["loop"] is not None:
        try:
            _state["loop"].call_soon_threadsafe(_state["loop"].stop)
        except Exception:
            pass
    _state.update(loop=None, thread=None, sem=None, client=None)
