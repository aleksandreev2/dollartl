from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dollartl.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BoostyLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "boosty_links"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    boosty_user_id: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    boosty_username: Mapped[str | None] = mapped_column(String(255), index=True)
    tier_id: Mapped[str | None] = mapped_column(String(120), index=True)
    tier_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="unverified", index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_successful_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    membership_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    grace_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    grace_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_error_code: Mapped[str | None] = mapped_column(String(120))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    access_revision: Mapped[int] = mapped_column(Integer, default=0)


class BoostyVerificationCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "boosty_verification_codes"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    force_check_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    detected_boosty_user_id: Mapped[str | None] = mapped_column(String(120), index=True)
    detected_boosty_username: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)


class BoostySyncRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "boosty_sync_runs"

    run_type: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scanned_count: Mapped[int] = mapped_column(Integer, default=0)
    matched_count: Mapped[int] = mapped_column(Integer, default=0)
    changed_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class BoostySyncError(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "boosty_sync_errors"

    sync_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("boosty_sync_runs.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    error_code: Mapped[str] = mapped_column(String(120), index=True)
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class BoostyAccessPeriod(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "boosty_access_periods"

    boosty_link_id: Mapped[UUID] = mapped_column(
        ForeignKey("boosty_links.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), index=True)
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    reason: Mapped[str] = mapped_column(String(120))
    sync_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("boosty_sync_runs.id", ondelete="SET NULL"), index=True
    )


class BoostyAccessEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "boosty_access_events"
    __table_args__ = (
        UniqueConstraint(
            "boosty_link_id", "access_revision", "event_type",
            name="uq_boosty_access_events_link_revision_type",
        ),
    )

    boosty_link_id: Mapped[UUID] = mapped_column(
        ForeignKey("boosty_links.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    access_revision: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)


class BoostyCredentialState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "boosty_credential_state"

    singleton_key: Mapped[str] = mapped_column(String(40), unique=True, default="primary")
    encrypted_payload: Mapped[str] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BoostyProviderState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "boosty_provider_state"

    singleton_key: Mapped[str] = mapped_column(String(40), unique=True, default="primary")
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    circuit_open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(120))
    last_error_message: Mapped[str | None] = mapped_column(Text)
