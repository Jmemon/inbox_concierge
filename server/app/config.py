from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# server/app/config.py -> parents[2] is the repo root; falls back gracefully if .env is absent (Railway injects env vars directly).
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    session_secret: str = Field(alias="SESSION_SECRET")
    encryption_key: str = Field(alias="ENCRYPTION_KEY")
    session_ttl_seconds: int = Field(default=60 * 60 * 24 * 30, alias="SESSION_TTL_SECONDS")
    google_client_id: str = Field(alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(alias="GOOGLE_REDIRECT_URI")
    cookie_domain: str | None = Field(default=None, alias="COOKIE_DOMAIN")
    # On Railway, ENV is "production"; locally unset → development.
    env: str = Field(default="development", alias="ENV")

    @property
    def cookie_secure(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
