"""user reports

Revision ID: 20260804_0005c
Revises: 20260804_0005b
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260804_0005c"
down_revision: str | None = "20260804_0005b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("title_id", sa.Uuid(), nullable=True),
        sa.Column("release_id", sa.Uuid(), nullable=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("assigned_admin_id", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("target_type IN ('title', 'release')", name="ck_reports_target_type"),
        sa.CheckConstraint("status IN ('open', 'in_progress', 'resolved', 'rejected')", name="ck_reports_status"),
        sa.CheckConstraint(
            "(target_type = 'title' AND title_id IS NOT NULL AND release_id IS NULL) OR "
            "(target_type = 'release' AND release_id IS NOT NULL AND title_id IS NULL)",
            name="ck_reports_target_reference",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["title_id"], ["titles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_reports"),
    )
    for column in ("user_id", "target_type", "title_id", "release_id", "category", "status"):
        op.create_index(f"ix_reports_{column}", "reports", [column])
    op.create_table(
        "report_messages",
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("sender_type", sa.String(20), nullable=False),
        sa.Column("sender_user_id", sa.Uuid(), nullable=True),
        sa.Column("sender_admin_id", sa.BigInteger(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("sender_type IN ('user', 'admin')", name="ck_report_messages_sender_type"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_report_messages"),
    )
    for column in ("report_id", "sender_type", "sender_user_id", "created_at"):
        op.create_index(f"ix_report_messages_{column}", "report_messages", [column])
    op.create_table(
        "report_attachments",
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("report_message_id", sa.Uuid(), nullable=True),
        sa.Column("telegram_file_id", sa.String(500), nullable=False),
        sa.Column("telegram_file_unique_id", sa.String(255), nullable=True),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_message_id"], ["report_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_report_attachments"),
    )
    for column in ("report_id", "report_message_id", "telegram_file_unique_id", "created_at"):
        op.create_index(f"ix_report_attachments_{column}", "report_attachments", [column])


def downgrade() -> None:
    for table in ("report_attachments", "report_messages", "reports"):
        op.drop_table(table)
