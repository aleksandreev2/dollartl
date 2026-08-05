"""catalog revisions and file inspection metadata

Revision ID: 20260805_0010
Revises: 20260804_0009
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0010"
down_revision: str | None = "20260804_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "file_version_inspections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("file_version_id", sa.Uuid(), nullable=False),
        sa.Column("inspection", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["file_version_id"], ["file_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_version_id"),
    )
    op.create_index("ix_file_version_inspections_file_version_id", "file_version_inspections", ["file_version_id"], unique=True)
    op.create_index("ix_file_version_inspections_created_at", "file_version_inspections", ["created_at"])
    op.create_table(
        "title_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["title_id"], ["titles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("title_id", "revision", name="uq_title_revisions_title_revision"),
    )
    op.create_index("ix_title_revisions_title_id", "title_revisions", ["title_id"])
    op.create_index("ix_title_revisions_actor_telegram_id", "title_revisions", ["actor_telegram_id"])
    op.create_index("ix_title_revisions_created_at", "title_revisions", ["created_at"])
    op.create_table(
        "release_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_id", "revision", name="uq_release_revisions_release_revision"),
    )
    op.create_index("ix_release_revisions_release_id", "release_revisions", ["release_id"])
    op.create_index("ix_release_revisions_actor_telegram_id", "release_revisions", ["actor_telegram_id"])
    op.create_index("ix_release_revisions_created_at", "release_revisions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_release_revisions_created_at", table_name="release_revisions")
    op.drop_index("ix_release_revisions_actor_telegram_id", table_name="release_revisions")
    op.drop_index("ix_release_revisions_release_id", table_name="release_revisions")
    op.drop_table("release_revisions")
    op.drop_index("ix_title_revisions_created_at", table_name="title_revisions")
    op.drop_index("ix_title_revisions_actor_telegram_id", table_name="title_revisions")
    op.drop_index("ix_title_revisions_title_id", table_name="title_revisions")
    op.drop_table("title_revisions")
    op.drop_index("ix_file_version_inspections_created_at", table_name="file_version_inspections")
    op.drop_index("ix_file_version_inspections_file_version_id", table_name="file_version_inspections")
    op.drop_table("file_version_inspections")
