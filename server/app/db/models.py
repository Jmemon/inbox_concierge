from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    gmail_refresh_token: Mapped[str | None] = mapped_column(Text)  # encrypted at rest
    gmail_access_token: Mapped[str | None] = mapped_column(Text)   # encrypted at rest
    gmail_access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gmail_last_history_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user")


class UserSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # secrets.token_urlsafe(32) -> 43 chars
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="sessions")
