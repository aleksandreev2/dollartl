"""translation ratings

Revision ID: 20260804_0005b
Revises: 20260804_0005a
"""
from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260804_0005b"
down_revision: str | None = "20260804_0005a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "translation_rating_categories",
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_translation_rating_categories"),
        sa.UniqueConstraint("code", name="uq_translation_rating_categories_code"),
    )
    op.create_index("ix_translation_rating_categories_code", "translation_rating_categories", ["code"])
    op.create_index("ix_translation_rating_categories_is_active", "translation_rating_categories", ["is_active"])
    op.create_table(
        "translation_ratings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("vip_snapshot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(30), nullable=False, server_default="new"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("score BETWEEN 1 AND 5", name="ck_translation_ratings_score"),
        sa.CheckConstraint(
            "status IN ('new', 'reviewed', 'in_progress', 'fixed', 'dismissed')",
            name="ck_translation_ratings_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_translation_ratings"),
        sa.UniqueConstraint("user_id", "release_id", name="uq_translation_ratings_user_release"),
    )
    for column in ("user_id", "release_id", "score", "vip_snapshot", "status", "is_deleted"):
        op.create_index(f"ix_translation_ratings_{column}", "translation_ratings", [column])
    op.create_table(
        "translation_rating_category_links",
        sa.Column("rating_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["rating_id"], ["translation_ratings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["translation_rating_categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_translation_rating_category_links"),
        sa.UniqueConstraint("rating_id", "category_id", name="uq_translation_rating_category_link"),
    )
    op.create_index("ix_translation_rating_category_links_rating_id", "translation_rating_category_links", ["rating_id"])
    op.create_index("ix_translation_rating_category_links_category_id", "translation_rating_category_links", ["category_id"])
    op.create_table(
        "translation_rating_revisions",
        sa.Column("rating_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("category_codes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("vip_snapshot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["rating_id"], ["translation_ratings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_translation_rating_revisions"),
    )
    op.create_index("ix_translation_rating_revisions_rating_id", "translation_rating_revisions", ["rating_id"])
    op.create_index("ix_translation_rating_revisions_created_at", "translation_rating_revisions", ["created_at"])
    op.create_table(
        "translation_rating_status_history",
        sa.Column("rating_id", sa.Uuid(), nullable=False),
        sa.Column("old_status", sa.String(30), nullable=True),
        sa.Column("new_status", sa.String(30), nullable=False),
        sa.Column("admin_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["rating_id"], ["translation_ratings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_translation_rating_status_history"),
    )
    for column in ("rating_id", "new_status", "created_at"):
        op.create_index(f"ix_translation_rating_status_history_{column}", "translation_rating_status_history", [column])
    categories = sa.table(
        "translation_rating_categories",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("label", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    labels = {
        "accuracy": "Translation Accuracy",
        "unnatural": "Unnatural English",
        "grammar": "Grammar or Punctuation",
        "terminology": "Inconsistent Terminology",
        "names": "Names or Pronouns",
        "missing": "Missing or Duplicated Text",
        "formatting": "Formatting or Layout",
        "pdf": "PDF Problem",
        "epub": "EPUB Problem",
        "other": "Other",
        "no_issues": "No Issues Found",
    }
    op.bulk_insert(
        categories,
        [{"id": uuid4(), "code": code, "label": label, "is_active": True} for code, label in labels.items()],
        multiinsert=False,
    )


def downgrade() -> None:
    for table in (
        "translation_rating_status_history",
        "translation_rating_revisions",
        "translation_rating_category_links",
        "translation_ratings",
        "translation_rating_categories",
    ):
        op.drop_table(table)
