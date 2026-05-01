from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlencode
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from app.config import get_settings


SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.readonly",
]


@dataclass
class ExchangedTokens:
    access_token: str
    refresh_token: str | None
    expires_at: datetime
    email: str
    name: str | None


@dataclass
class RefreshedTokens:
    access_token: str
    expires_at: datetime


def _flow() -> Flow:
    s = get_settings()
    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": s.google_client_id,
                "client_secret": s.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [s.google_redirect_uri],
            }
        },
        scopes=SCOPES,
        redirect_uri=s.google_redirect_uri,
    )


def build_authorize_url(*, state: str) -> str:
    s = get_settings()
    # Build the URL by hand so this function stays pure (no network) and unit-testable.
    params = {
        "response_type": "code",
        "client_id": s.google_client_id,
        "redirect_uri": s.google_redirect_uri,
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return "https://accounts.google.com/o/oauth2/auth?" + urlencode(params)


def _exchange(code: str) -> Credentials:
    flow = _flow()
    flow.fetch_token(code=code)
    return flow.credentials


def _fetch_userinfo(creds: Credentials) -> dict:
    service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
    return service.userinfo().get().execute()


def exchange_code(*, code: str) -> ExchangedTokens:
    creds = _exchange(code)
    userinfo = _fetch_userinfo(creds)
    expiry = creds.expiry  # naive UTC per google library
    expires_at = expiry.replace(tzinfo=timezone.utc) if expiry.tzinfo is None else expiry
    return ExchangedTokens(
        access_token=creds.token,
        refresh_token=creds.refresh_token,
        expires_at=expires_at,
        email=userinfo["email"],
        name=userinfo.get("name"),
    )


def _refresh(refresh_token: str) -> Credentials:
    s = get_settings()
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=s.google_client_id,
        client_secret=s.google_client_secret,
        scopes=SCOPES,
    )
    creds.refresh(GoogleAuthRequest())
    return creds


def refresh_access_token(*, refresh_token: str) -> RefreshedTokens:
    creds = _refresh(refresh_token)
    expiry = creds.expiry
    expires_at = expiry.replace(tzinfo=timezone.utc) if expiry.tzinfo is None else expiry
    return RefreshedTokens(access_token=creds.token, expires_at=expires_at)
