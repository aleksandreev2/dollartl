"""resilience, backups, heartbeats and webhook receipts

Revision ID: 20260804_0008
Revises: 20260804_0007
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260804_0008"
down_revision: str | None = "20260804_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backup_runs",
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("trigger_type", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("requested_by_admin_id", sa.BigInteger(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("database_object_key", sa.String(700), nullable=True),
        sa.Column("manifest_object_key", sa.String(700), nullable=True),
        sa.Column("storage_manifest_object_key", sa.String(700), nullable=True),
        sa.Column("plaintext_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("encrypted_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("plaintext_sha256", sa.String(64), nullable=True),
        sa.Column("encrypted_sha256", sa.String(64), nullable=True),
        sa.Column("database_archive_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("restore_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("storage_replication_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verification_details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source_object_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("replicated_object_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("replicated_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("telegram_delivery_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('queued','running','succeeded','failed','cancelled')", name="ck_backup_runs_backup_runs_status"),
        sa.CheckConstraint("trigger_type IN ('scheduled','manual','migration')", name="ck_backup_runs_backup_runs_trigger_type"),
        sa.CheckConstraint("telegram_delivery_status IN ('pending','sent','linked','failed','skipped')", name="ck_backup_runs_backup_runs_telegram_delivery_status"),
        sa.PrimaryKeyConstraint("id", name="pk_backup_runs"),
        sa.UniqueConstraint("database_object_key", name="uq_backup_runs_database_object_key"),
        sa.UniqueConstraint("manifest_object_key", name="uq_backup_runs_manifest_object_key"),
        sa.UniqueConstraint("storage_manifest_object_key", name="uq_backup_runs_storage_manifest_object_key"),
    )
    for column in (
        "status", "trigger_type", "requested_by_admin_id", "started_at", "completed_at",
        "plaintext_sha256", "encrypted_sha256", "telegram_delivery_status", "created_at",
    ):
        op.create_index(f"ix_backup_runs_{column}", "backup_runs", [column])

    op.create_table(
        "service_heartbeats",
        sa.Column("service_name", sa.String(50), nullable=False),
        sa.Column("instance_id", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="starting"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('starting','healthy','degraded','stopping')", name="ck_service_heartbeats_service_heartbeats_status"),
        sa.PrimaryKeyConstraint("id", name="pk_service_heartbeats"),
        sa.UniqueConstraint("service_name", "instance_id", name="uq_service_heartbeats_service_instance"),
    )
    for column in ("service_name", "instance_id", "status", "last_seen_at", "created_at"):
        op.create_index(f"ix_service_heartbeats_{column}", "service_heartbeats", [column])

    op.create_table(
        "telegram_update_receipts",
        sa.Column("update_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="processing"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('processing','completed','failed')", name="ck_telegram_update_receipts_telegram_update_receipts_status"),
        sa.PrimaryKeyConstraint("id", name="pk_telegram_update_receipts"),
        sa.UniqueConstraint("update_id", name="uq_telegram_update_receipts_update_id"),
    )
    for column in ("update_id", "status", "started_at", "completed_at", "created_at"):
        op.create_index(f"ix_telegram_update_receipts_{column}", "telegram_update_receipts", [column])


def downgrade() -> None:
    op.drop_table("telegram_update_receipts")
    op.drop_table("service_heartbeats")
    op.drop_table("backup_runs")
