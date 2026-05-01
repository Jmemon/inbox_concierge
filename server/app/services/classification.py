"""Classification pipeline.

V1 is a deterministic dummy: hash(thread_id) modulo bucket count. This keeps
the homepage demo populated across all default buckets without any LLM calls.
The signature is shaped so an LLM-backed implementation can swap in later
without changing callers in workers/gmail_sync.py.
"""

import hashlib
from app.services.message_parser import ParsedThread


def classify(thread: ParsedThread, available_bucket_ids: list[str]) -> str:
    if not available_bucket_ids:
        raise ValueError("classify needs at least one available bucket id")
    digest = hashlib.sha1(thread.gmail_thread_id.encode()).digest()
    idx = int.from_bytes(digest[:4], "big") % len(available_bucket_ids)
    return available_bucket_ids[idx]
