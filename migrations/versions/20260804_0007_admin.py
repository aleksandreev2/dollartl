"""admin Mini App, broadcasts and mandatory raw files

Revision ID: 20260804_0007
Revises: 20260804_0006
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260804_0007"
down_revision: str | None = "20260804_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "broadcasts",
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("audience_type", sa.String(30), nullable=False),
        sa.Column("title_id", sa.Uuid(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("photo_object_key", sa.String(500), nullable=True),
        sa.Column("photo_content_type", sa.String(120), nullable=True),
        sa.Column("button_text", sa.String(64), nullable=True),
        sa.Column("button_url", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("selected_user_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_by_admin_id", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('draft','scheduled','processing','completed','failed','cancelled')", name="ck_broadcasts_broadcasts_status"),
        sa.CheckConstraint("audience_type IN ('all','active_vip','vip_grace','standard','title_followers','selected')", name="ck_broadcasts_broadcasts_audience_type"),
        sa.ForeignKeyConstraint(["title_id"], ["titles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_broadcasts"),
    )
    for column in ("status", "audience_type", "title_id", "scheduled_at", "created_at"):
        op.create_index(f"ix_broadcasts_{column}", "broadcasts", [column])

    op.create_table(
        "broadcast_recipients",
        sa.Column("broadcast_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('pending','sent','failed','skipped')", name="ck_broadcast_recipients_broadcast_recipients_status"),
        sa.ForeignKeyConstraint(["broadcast_id"], ["broadcasts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_broadcast_recipients"),
        sa.UniqueConstraint("broadcast_id", "user_id", name="uq_broadcast_recipients_broadcast_user"),
    )
    for column in ("broadcast_id", "user_id", "status", "sent_at", "created_at"):
        op.create_index(f"ix_broadcast_recipients_{column}", "broadcast_recipients", [column])

    op.create_table(
        "admin_uploads",
        sa.Column("object_key", sa.String(500), nullable=False),
        sa.Column("purpose", sa.String(50), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by_admin_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_admin_uploads"),
        sa.UniqueConstraint("object_key", name="uq_admin_uploads_object_key"),
    )
    for column in ("object_key", "purpose", "sha256", "created_at", "is_active"):
        op.create_index(f"ix_admin_uploads_{column}", "admin_uploads", [column])

    op.execute("""
    CREATE OR REPLACE FUNCTION require_valid_suggestion_raw_file()
    RETURNS trigger AS $$
    BEGIN
      IF NEW.status <> 'draft' AND (TG_OP = 'INSERT' OR OLD.status = 'draft') THEN
        IF NOT EXISTS (
          SELECT 1 FROM suggestion_files
          WHERE suggestion_id = NEW.id
            AND file_kind = 'raw'
            AND validation_status = 'valid'
        ) THEN
          RAISE EXCEPTION 'A valid raw file is required before submitting a title suggestion';
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)
    op.execute("""
    CREATE TRIGGER enforce_suggestion_raw_file
    BEFORE INSERT OR UPDATE OF status ON title_suggestions
    FOR EACH ROW EXECUTE FUNCTION require_valid_suggestion_raw_file();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS enforce_suggestion_raw_file ON title_suggestions")
    op.execute("DROP FUNCTION IF EXISTS require_valid_suggestion_raw_file()")
    for table in ("admin_uploads", "broadcast_recipients", "broadcasts"):
        op.drop_table(table)
