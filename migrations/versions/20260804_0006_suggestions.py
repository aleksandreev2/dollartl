"""title suggestions and quotas

Revision ID: 20260804_0006
Revises: 20260804_0005c
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260804_0006"
down_revision: str | None = "20260804_0005c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "suggestion_rule_consents",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_suggestion_rule_consents"),
        sa.UniqueConstraint(
            "user_id",
            "version",
            name="uq_suggestion_rule_consents_user_version",
        ),
    )
    op.create_index(
        "ix_suggestion_rule_consents_user_id",
        "suggestion_rule_consents",
        ["user_id"],
    )
    op.create_index(
        "ix_suggestion_rule_consents_version",
        "suggestion_rule_consents",
        ["version"],
    )

    op.create_table(
        "title_suggestions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("original_title", sa.String(500), nullable=True),
        sa.Column("normalized_title", sa.String(500), nullable=True),
        sa.Column("detected_language", sa.String(80), nullable=True),
        sa.Column("chapter_count", sa.Integer(), nullable=True),
        sa.Column("publication_status", sa.String(30), nullable=True),
        sa.Column(
            "requested_chapter_start",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("requested_chapter_end", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column(
            "vip_snapshot",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("public_reason", sa.Text(), nullable=True),
        sa.Column("internal_note", sa.Text(), nullable=True),
        sa.Column("linked_title_id", sa.Uuid(), nullable=True),
        sa.Column(
            "duplicate_review_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('draft', 'under_review', 'accepted', 'translated', 'rejected')",
            name="ck_title_suggestions_status",
        ),
        sa.CheckConstraint(
            "publication_status IS NULL OR publication_status IN "
            "('ongoing', 'completed', 'hiatus', 'unknown')",
            name="ck_title_suggestions_publication_status",
        ),
        sa.CheckConstraint(
            "chapter_count IS NULL OR chapter_count >= 1",
            name="ck_title_suggestions_chapter_count",
        ),
        sa.CheckConstraint(
            "requested_chapter_start >= 1",
            name="ck_title_suggestions_scope_start",
        ),
        sa.CheckConstraint(
            "requested_chapter_end IS NULL OR "
            "requested_chapter_end >= requested_chapter_start",
            name="ck_title_suggestions_scope_order",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["linked_title_id"],
            ["titles.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_title_suggestions"),
    )
    for column in (
        "user_id",
        "original_title",
        "normalized_title",
        "detected_language",
        "publication_status",
        "status",
        "vip_snapshot",
        "linked_title_id",
        "duplicate_review_required",
        "submitted_at",
    ):
        op.create_index(
            f"ix_title_suggestions_{column}",
            "title_suggestions",
            [column],
        )

    op.create_table(
        "suggestion_sources",
        sa.Column("suggestion_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("source_order", sa.Integer(), nullable=False, server_default="0"),
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
            ["suggestion_id"],
            ["title_suggestions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_suggestion_sources"),
        sa.UniqueConstraint(
            "suggestion_id",
            "normalized_url",
            name="uq_suggestion_sources_suggestion_url",
        ),
    )
    for column in ("suggestion_id", "normalized_url"):
        op.create_index(
            f"ix_suggestion_sources_{column}",
            "suggestion_sources",
            [column],
        )

    op.create_table(
        "suggestion_files",
        sa.Column("suggestion_id", sa.Uuid(), nullable=False),
        sa.Column("file_kind", sa.String(20), nullable=False),
        sa.Column("object_key", sa.String(700), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("telegram_file_id", sa.String(500), nullable=True),
        sa.Column("telegram_file_unique_id", sa.String(255), nullable=True),
        sa.Column(
            "validation_status",
            sa.String(30),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("validation_message", sa.Text(), nullable=True),
        sa.Column(
            "inspection",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
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
        sa.CheckConstraint(
            "file_kind IN ('raw', 'cover')",
            name="ck_suggestion_files_kind",
        ),
        sa.CheckConstraint(
            "validation_status IN ('pending', 'valid', 'warning', 'rejected')",
            name="ck_suggestion_files_validation",
        ),
        sa.ForeignKeyConstraint(
            ["suggestion_id"],
            ["title_suggestions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_suggestion_files"),
        sa.UniqueConstraint(
            "suggestion_id",
            "file_kind",
            name="uq_suggestion_files_suggestion_kind",
        ),
        sa.UniqueConstraint("object_key", name="uq_suggestion_files_object_key"),
    )
    for column in (
        "suggestion_id",
        "file_kind",
        "object_key",
        "sha256",
        "telegram_file_unique_id",
        "validation_status",
    ):
        op.create_index(
            f"ix_suggestion_files_{column}",
            "suggestion_files",
            [column],
        )

    op.create_table(
        "suggestion_status_history",
        sa.Column("suggestion_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(30), nullable=True),
        sa.Column("to_status", sa.String(30), nullable=False),
        sa.Column("public_reason", sa.Text(), nullable=True),
        sa.Column("internal_note", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_admin_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["suggestion_id"],
            ["title_suggestions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_suggestion_status_history"),
    )
    for column in (
        "suggestion_id",
        "to_status",
        "actor_user_id",
        "actor_admin_id",
        "created_at",
    ):
        op.create_index(
            f"ix_suggestion_status_history_{column}",
            "suggestion_status_history",
            [column],
        )

    op.create_table(
        "suggestion_quota_usage",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("suggestion_id", sa.Uuid(), nullable=False),
        sa.Column("quota_month", sa.Date(), nullable=False),
        sa.Column(
            "consumed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("restored_by_admin_id", sa.BigInteger(), nullable=True),
        sa.Column("restore_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["suggestion_id"],
            ["title_suggestions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_suggestion_quota_usage"),
        sa.UniqueConstraint(
            "suggestion_id",
            name="uq_suggestion_quota_usage_suggestion",
        ),
    )
    for column in ("user_id", "suggestion_id", "quota_month", "restored_at"):
        op.create_index(
            f"ix_suggestion_quota_usage_{column}",
            "suggestion_quota_usage",
            [column],
        )

    op.create_table(
        "duplicate_candidates",
        sa.Column("suggestion_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_type", sa.String(30), nullable=False),
        sa.Column("candidate_suggestion_id", sa.Uuid(), nullable=True),
        sa.Column("candidate_title_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="100"),
        sa.Column(
            "resolved",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("resolution", sa.String(40), nullable=True),
        sa.Column("resolved_by_admin_id", sa.BigInteger(), nullable=True),
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
        sa.CheckConstraint(
            "candidate_type IN ('suggestion', 'published_title')",
            name="ck_duplicate_candidates_type",
        ),
        sa.ForeignKeyConstraint(
            ["suggestion_id"],
            ["title_suggestions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_suggestion_id"],
            ["title_suggestions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_title_id"],
            ["titles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_duplicate_candidates"),
    )
    for column in (
        "suggestion_id",
        "candidate_type",
        "candidate_suggestion_id",
        "candidate_title_id",
        "resolved",
    ):
        op.create_index(
            f"ix_duplicate_candidates_{column}",
            "duplicate_candidates",
            [column],
        )


def downgrade() -> None:
    for table in (
        "duplicate_candidates",
        "suggestion_quota_usage",
        "suggestion_status_history",
        "suggestion_files",
        "suggestion_sources",
        "title_suggestions",
        "suggestion_rule_consents",
    ):
        op.drop_table(table)
