from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, BigInteger
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


class Bucket(Base):
    __tablename__ = "buckets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # null user_id => default bucket shared by all users
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    criteria: Mapped[str] = mapped_column(Text, nullable=False, default="")


class InboxThread(Base):
    __tablename__ = "inbox_threads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    gmail_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(Text)
    bucket_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("buckets.id"))
    # recent_message_id can't FK at row-create time (chicken/egg); it's a soft pointer.
    recent_message_id: Mapped[str | None] = mapped_column(String(36))


class InboxMessage(Base):
    __tablename__ = "inbox_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(36), ForeignKey("inbox_threads.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    gmail_id: Mapped[str] = mapped_column(String(64), nullable=False)
    gmail_thread_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # int64 ms since epoch, mirrors Gmail's MessagePart.internalDate
    gmail_internal_date: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    gmail_history_id: Mapped[str] = mapped_column(String(64), nullable=False)
    to_addr: Mapped[str | None] = mapped_column(Text)
    from_addr: Mapped[str | None] = mapped_column(Text)
    body_preview: Mapped[str | None] = mapped_column(String(200))
