import secrets
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from app.config import get_settings


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
    if not cookie_value or not url_value:
        return False
    try:
        unsigned = _get().loads(url_value, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return False
    return secrets.compare_digest(unsigned, cookie_value)
