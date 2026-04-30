from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.config import get_settings
from app.db.models import User
from app.services import crypto, google_oauth


def _ensure_fresh_access_token(db: Session, user: User) -> str:
    """Returns a usable access token for `user`, refreshing and persisting if needed."""
    if (
        user.gmail_access_token
        and user.gmail_access_token_expires_at
        and user.gmail_access_token_expires_at > datetime.now(timezone.utc) + timedelta(seconds=60)
    ):
        return crypto.decrypt(user.gmail_access_token)

    if not user.gmail_refresh_token:
        raise RuntimeError("user has no refresh token; must re-auth")

    refresh_plain = crypto.decrypt(user.gmail_refresh_token)
    refreshed = google_oauth.refresh_access_token(refresh_token=refresh_plain)
    user.gmail_access_token = crypto.encrypt(refreshed.access_token)
    user.gmail_access_token_expires_at = refreshed.expires_at
    db.commit()
    return refreshed.access_token


def _credentials(access_token: str, refresh_token: str | None) -> Credentials:
    s = get_settings()
    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=s.google_client_id,
        client_secret=s.google_client_secret,
        scopes=google_oauth.SCOPES,
    )


def fetch_profile_summary(db: Session, user: User) -> dict:
    """Returns Gmail profile + first three message subjects to prove read access works."""
    access_token = _ensure_fresh_access_token(db, user)
    refresh_plain = crypto.decrypt(user.gmail_refresh_token) if user.gmail_refresh_token else None
    creds = _credentials(access_token, refresh_plain)
    gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)

    profile = gmail.users().getProfile(userId="me").execute()
    listing = gmail.users().messages().list(userId="me", maxResults=3).execute()
    subjects: list[str] = []
    for m in listing.get("messages", []):
        full = (
            gmail.users()
            .messages()
            .get(userId="me", id=m["id"], format="metadata", metadataHeaders=["Subject"])
            .execute()
        )
        headers = full.get("payload", {}).get("headers", [])
        subj = next((h["value"] for h in headers if h["name"].lower() == "subject"), "(no subject)")
        subjects.append(subj)

    return {
        "email": profile.get("emailAddress"),
        "messages_total": profile.get("messagesTotal"),
        "threads_total": profile.get("threadsTotal"),
        "recent_subjects": subjects,
    }
