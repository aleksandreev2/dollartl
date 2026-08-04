from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dollartl.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BackupRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "backup_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')",
            name="backup_runs_status",
        ),
        CheckConstraint(
            "trigger_type IN ('scheduled','manual','migration')",
            name="backup_runs_trigger_type",
        ),
        CheckConstraint(
            "telegram_delivery_status IN ('pending','sent','linked','failed','skipped')",
            name="backup_runs_telegram_delivery_status",
        ),
    )

    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    trigger_type: Mapped[str] = mapped_column(String(20), default="scheduled", index=True)
    requested_by_admin_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    database_object_key: Mapped[str | None] = mapped_column(String(700), unique=True)
    manifest_object_key: Mapped[str | None] = mapped_column(String(700), unique=True)
    storage_manifest_object_key: Mapped[str | None] = mapped_column(String(700), unique=True)
    plaintext_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    encrypted_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    plaintext_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    encrypted_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    database_archive_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    restore_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    storage_replication_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    source_object_count: Mapped[int] = mapped_column(Integer, default=0)
    replicated_object_count: Mapped[int] = mapped_column(Integer, default=0)
    replicated_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    telegram_delivery_status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    error: Mapped[str | None] = mapped_column(Text)


class ServiceHeartbeat(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_heartbeats"
    __table_args__ = (
        UniqueConstraint(
            "service_name", "instance_id", name="uq_service_heartbeats_service_instance"
        ),
        CheckConstraint(
            "status IN ('starting','healthy','degraded','stopping')",
            name="service_heartbeats_status",
        ),
    )

    service_name: Mapped[str] = mapped_column(String(50), index=True)
    instance_id: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(20), default="starting", index=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class TelegramUpdateReceipt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "telegram_update_receipts"
    __table_args__ = (
        UniqueConstraint("update_id", name="uq_telegram_update_receipts_update_id"),
        CheckConstraint(
            "status IN ('processing','completed','failed')",
            name="telegram_update_receipts_status",
        ),
    )

    update_id: Mapped[int] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(20), default="processing", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_error: Mapped[str | None] = mapped_column(Text)
