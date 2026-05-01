import logging
import secrets
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from app.config import get_settings


log = logging.getLogger(__name__)
_serializer: URLSafeTimedSerializer | None = None


def _get() -> URLSafeTimedSerializer:
    global _serializer
    if _serializer is None:
        _serializer = URLSafeTimedSerializer(get_settings().session_secret, salt="oauth-state")
    return _serializer


def make_state() -> tuple[str, str]:
    """Returns (raw, signed). Set raw as a short-lived cookie, send signed in the URL."""
    raw = secrets.token_urlsafe(16)
    signed = _get().dumps(raw)
    return raw, signed


def verify_state(*, cookie_value: str | None, url_value: str | None, max_age_seconds: int = 600) -> bool:
    if not cookie_value:
        log.warning("verify_state failed: oauth_state cookie missing on callback request")
        return False
    if not url_value:
        log.warning("verify_state failed: state url param missing")
        return False
    try:
        unsigned = _get().loads(url_value, max_age=max_age_seconds)
    except SignatureExpired:
        log.warning("verify_state failed: signed state expired (>%ds old)", max_age_seconds)
        return False
    except BadSignature as exc:
        log.warning("verify_state failed: bad signature on url state (%s) — likely SESSION_SECRET mismatch", exc)
        return False
    if not secrets.compare_digest(unsigned, cookie_value):
        log.warning(
            "verify_state failed: signed url value doesn't match cookie (likely a stale cookie from a prior login attempt)"
        )
        return False
    return True
