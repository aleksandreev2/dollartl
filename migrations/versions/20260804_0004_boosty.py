"""Boosty links, verification, access periods and synchronization

Revision ID: 20260804_0004
Revises: 20260804_0003
Create Date: 2026-08-04 22:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260804_0004"
down_revision: str | None = "20260804_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "boosty_links",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("boosty_user_id", sa.String(120), nullable=True),
        sa.Column("boosty_username", sa.String(255), nullable=True),
        sa.Column("tier_id", sa.String(120), nullable=True),
        sa.Column("tier_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="unverified"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("membership_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(120), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("access_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('unverified', 'active_vip', 'grace_period', 'expired', 'verification_error')",
            name="ck_boosty_links_status",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_boosty_links_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_boosty_links"),
        sa.UniqueConstraint("boosty_user_id", name="uq_boosty_links_boosty_user_id"),
        sa.UniqueConstraint("user_id", name="uq_boosty_links_user_id"),
    )
    for column in (
        "user_id",
        "boosty_user_id",
        "boosty_username",
        "tier_id",
        "status",
        "last_checked_at",
        "grace_ends_at",
    ):
        op.create_index(f"ix_boosty_links_{column}", "boosty_links", [column])

    op.create_table(
        "boosty_verification_codes",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("force_check_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("detected_boosty_user_id", sa.String(120), nullable=True),
        sa.Column("detected_boosty_username", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'matched', 'expired', 'conflict', 'failed')",
            name="ck_boosty_verification_codes_status",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_boosty_verification_codes_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_boosty_verification_codes"),
        sa.UniqueConstraint("code", name="uq_boosty_verification_codes_code"),
    )
    for column in (
        "user_id",
        "code",
        "status",
        "expires_at",
        "force_check_requested_at",
        "detected_boosty_user_id",
    ):
        op.create_index(
            f"ix_boosty_verification_codes_{column}", "boosty_verification_codes", [column]
        )

    op.create_table(
        "boosty_sync_runs",
        sa.Column("run_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scanned_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("changed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "run_type IN ('verification', 'membership', 'manual')",
            name="ck_boosty_sync_runs_run_type",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'success', 'failed', 'partial')",
            name="ck_boosty_sync_runs_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_boosty_sync_runs"),
    )
    for column in ("run_type", "status", "started_at"):
        op.create_index(f"ix_boosty_sync_runs_{column}", "boosty_sync_runs", [column])

    op.create_table(
        "boosty_sync_errors",
        sa.Column("sync_run_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.String(120), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["sync_run_id"], ["boosty_sync_runs.id"], name="fk_boosty_sync_errors_sync_run_id_boosty_sync_runs", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_boosty_sync_errors_user_id_users", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_boosty_sync_errors"),
    )
    for column in ("sync_run_id", "user_id", "error_code", "created_at"):
        op.create_index(f"ix_boosty_sync_errors_{column}", "boosty_sync_errors", [column])

    op.create_table(
        "boosty_access_periods",
        sa.Column("boosty_link_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(120), nullable=False),
        sa.Column("sync_run_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["boosty_link_id"], ["boosty_links.id"], name="fk_boosty_access_periods_boosty_link_id_boosty_links", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_boosty_access_periods_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["sync_run_id"], ["boosty_sync_runs.id"], name="fk_boosty_access_periods_sync_run_id_boosty_sync_runs", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_boosty_access_periods"),
    )
    for column in ("boosty_link_id", "user_id", "status", "starts_at", "ends_at", "sync_run_id"):
        op.create_index(f"ix_boosty_access_periods_{column}", "boosty_access_periods", [column])

    op.create_table(
        "boosty_access_events",
        sa.Column("boosty_link_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("access_revision", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["boosty_link_id"], ["boosty_links.id"], name="fk_boosty_access_events_boosty_link_id_boosty_links", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_boosty_access_events_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_boosty_access_events"),
        sa.UniqueConstraint(
            "boosty_link_id", "access_revision", "event_type",
            name="uq_boosty_access_events_link_revision_type",
        ),
    )
    for column in ("boosty_link_id", "user_id", "event_type", "sent_at"):
        op.create_index(f"ix_boosty_access_events_{column}", "boosty_access_events", [column])

    op.create_table(
        "boosty_provider_state",
        sa.Column("singleton_key", sa.String(40), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("circuit_open_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(120), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_boosty_provider_state"),
        sa.UniqueConstraint("singleton_key", name="uq_boosty_provider_state_singleton_key"),
    )
    op.create_index(
        "ix_boosty_provider_state_circuit_open_until",
        "boosty_provider_state",
        ["circuit_open_until"],
    )

    op.create_table(
        "boosty_credential_state",
        sa.Column("singleton_key", sa.String(40), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_boosty_credential_state"),
        sa.UniqueConstraint("singleton_key", name="uq_boosty_credential_state_singleton_key"),
    )


def downgrade() -> None:
    op.drop_table("boosty_credential_state")
    op.drop_table("boosty_provider_state")
    op.drop_table("boosty_access_events")
    op.drop_table("boosty_access_periods")
    op.drop_table("boosty_sync_errors")
    op.drop_table("boosty_sync_runs")
    op.drop_table("boosty_verification_codes")
    op.drop_table("boosty_links")
