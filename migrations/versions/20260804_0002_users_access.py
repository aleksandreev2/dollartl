"""users, consent and global bans

Revision ID: 20260804_0002
Revises: 20260804_0001
Create Date: 2026-08-04 20:45:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260804_0002"
down_revision: str | None = "20260804_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_username", sa.String(64), nullable=True),
        sa.Column("telegram_first_name", sa.String(255), nullable=True),
        sa.Column("telegram_last_name", sa.String(255), nullable=True),
        sa.Column("anonymous_id", sa.BigInteger(), sa.Identity(start=1000), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("anonymous_id", name="uq_users_anonymous_id"),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )
    for column in (
        "telegram_id",
        "telegram_username",
        "anonymous_id",
        "is_active",
        "last_seen_at",
    ):
        op.create_index(f"ix_users_{column}", "users", [column])

    op.create_table(
        "user_consents",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("consent_type", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(40), nullable=False, server_default="telegram_bot"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_consents_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_consents"),
        sa.UniqueConstraint(
            "user_id",
            "consent_type",
            "version",
            name="uq_user_consents_user_type_version",
        ),
    )
    op.create_index("ix_user_consents_user_id", "user_consents", ["user_id"])
    op.create_index("ix_user_consents_consent_type", "user_consents", ["consent_type"])

    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(24), nullable=True),
        sa.Column("locale", sa.String(10), nullable=False, server_default="en"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_settings_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_settings"),
        sa.UniqueConstraint("user_id", name="uq_user_settings_user_id"),
    )
    op.create_index("ix_user_settings_user_id", "user_settings", ["user_id"])

    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "new_title_announcements",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "service_notifications",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_notification_preferences_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notification_preferences"),
        sa.UniqueConstraint("user_id", name="uq_notification_preferences_user_id"),
    )
    op.create_index(
        "ix_notification_preferences_user_id",
        "notification_preferences",
        ["user_id"],
    )

    op.create_table(
        "bans",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("ban_type", sa.String(20), nullable=False),
        sa.Column(
            "starts_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_reason", sa.Text(), nullable=False),
        sa.Column("reason_template", sa.String(80), nullable=True),
        sa.Column("internal_note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_admin_id", sa.BigInteger(), nullable=False),
        sa.Column("last_notice_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unbanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unbanned_by_admin_id", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("ban_type IN ('temporary', 'permanent')", name="ck_bans_ban_type"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_bans_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bans"),
    )
    for column in ("user_id", "ban_type", "expires_at", "is_active"):
        op.create_index(f"ix_bans_{column}", "bans", [column])

    op.create_table(
        "ban_history",
        sa.Column("ban_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ban_id"], ["bans.id"], name="fk_ban_history_ban_id_bans", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ban_history"),
    )
    for column in ("ban_id", "action", "actor_telegram_id", "created_at"):
        op.create_index(f"ix_ban_history_{column}", "ban_history", [column])


def downgrade() -> None:
    op.drop_table("ban_history")
    op.drop_table("bans")
    op.drop_table("notification_preferences")
    op.drop_table("user_settings")
    op.drop_table("user_consents")
    op.drop_table("users")
