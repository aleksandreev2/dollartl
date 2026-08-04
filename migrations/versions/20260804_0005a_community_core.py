"""community comments and moderation

Revision ID: 20260804_0005a
Revises: 20260804_0004
"""
from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260804_0005a"
down_revision: str | None = "20260804_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("download_thanks_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_user_settings_download_thanks_at",
        "user_settings",
        ["download_thanks_at"],
    )
    op.create_table(
        "moderation_rules",
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("replacement", sa.String(40), nullable=False, server_default="***"),
        sa.Column("applies_to_comments", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("applies_to_nicknames", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("applies_to_feedback", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_moderation_rules"),
        sa.UniqueConstraint("code", name="uq_moderation_rules_code"),
    )
    for column in ("code", "category", "is_active"):
        op.create_index(f"ix_moderation_rules_{column}", "moderation_rules", [column])
    op.create_table(
        "moderation_allowlist",
        sa.Column("normalized_value", sa.String(255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_moderation_allowlist"),
        sa.UniqueConstraint("normalized_value", name="uq_moderation_allowlist_normalized_value"),
    )
    op.create_index("ix_moderation_allowlist_normalized_value", "moderation_allowlist", ["normalized_value"])
    op.create_index("ix_moderation_allowlist_is_active", "moderation_allowlist", ["is_active"])
    op.create_table(
        "comments",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("title_id", sa.Uuid(), nullable=True),
        sa.Column("release_id", sa.Uuid(), nullable=True),
        sa.Column("original_body", sa.Text(), nullable=False),
        sa.Column("public_body", sa.Text(), nullable=False),
        sa.Column("replacement_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vip_snapshot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_admin_id", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("target_type IN ('title', 'release')", name="ck_comments_target_type"),
        sa.CheckConstraint(
            "(target_type = 'title' AND title_id IS NOT NULL AND release_id IS NULL) OR "
            "(target_type = 'release' AND release_id IS NOT NULL AND title_id IS NULL)",
            name="ck_comments_target_reference",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["title_id"], ["titles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_comments"),
    )
    for column in ("user_id", "target_type", "title_id", "release_id", "vip_snapshot", "is_deleted"):
        op.create_index(f"ix_comments_{column}", "comments", [column])
    op.create_table(
        "comment_revisions",
        sa.Column("comment_id", sa.Uuid(), nullable=False),
        sa.Column("original_body", sa.Text(), nullable=False),
        sa.Column("public_body", sa.Text(), nullable=False),
        sa.Column("replacement_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("editor_user_id", sa.Uuid(), nullable=True),
        sa.Column("editor_admin_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["editor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_comment_revisions"),
    )
    for column in ("comment_id", "editor_user_id", "created_at"):
        op.create_index(f"ix_comment_revisions_{column}", "comment_revisions", [column])
    op.create_table(
        "moderation_matches",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=True),
        sa.Column("surface", sa.String(30), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=True),
        sa.Column("entity_id", sa.String(100), nullable=True),
        sa.Column("matched_hash", sa.String(64), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["moderation_rules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_moderation_matches"),
    )
    for column in ("user_id", "rule_id", "surface", "entity_type", "entity_id", "matched_hash", "created_at"):
        op.create_index(f"ix_moderation_matches_{column}", "moderation_matches", [column])
    rules = sa.table(
        "moderation_rules",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("category", sa.String()),
        sa.column("pattern", sa.Text()),
        sa.column("replacement", sa.String()),
        sa.column("applies_to_comments", sa.Boolean()),
        sa.column("applies_to_nicknames", sa.Boolean()),
        sa.column("applies_to_feedback", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        rules,
        [
            {
                "id": uuid4(),
                "code": "nword",
                "category": "racist_slur",
                "pattern": r"(?i)(?<![a-z0-9])n[\W_]*[i1!|][\W_]*[g69q][\W_]*[g69q][\W_]*[e3][\W_]*r?s?(?![a-z0-9])",
                "replacement": "***",
                "applies_to_comments": True,
                "applies_to_nicknames": True,
                "applies_to_feedback": True,
                "is_active": True,
            },
            {
                "id": uuid4(),
                "code": "racist_slur_2",
                "category": "racist_slur",
                "pattern": r"(?i)(?<![a-z0-9])c[\W_]*h[\W_]*[i1][\W_]*n[\W_]*k(?![a-z0-9])",
                "replacement": "***",
                "applies_to_comments": True,
                "applies_to_nicknames": True,
                "applies_to_feedback": True,
                "is_active": True,
            },
        ],
        multiinsert=False,
    )


def downgrade() -> None:
    for table in ("moderation_matches", "comment_revisions", "comments", "moderation_allowlist", "moderation_rules"):
        op.drop_table(table)
    op.drop_index("ix_user_settings_download_thanks_at", table_name="user_settings")
    op.drop_column("user_settings", "download_thanks_at")
