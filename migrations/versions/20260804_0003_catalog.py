"""catalogue, releases, files and publications

Revision ID: 20260804_0003
Revises: 20260804_0002
Create Date: 2026-08-04 21:20:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260804_0003"
down_revision: str | None = "20260804_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "manual_download_access", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_index(
        "ix_users_manual_download_access", "users", ["manual_download_access"]
    )
    op.add_column(
        "user_settings",
        sa.Column("pending_deep_link_token", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_user_settings_pending_deep_link_token",
        "user_settings",
        ["pending_deep_link_token"],
    )

    op.create_table(
        "titles",
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("english_title", sa.String(255), nullable=False),
        sa.Column("original_title", sa.String(255), nullable=False),
        sa.Column("original_language", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("publication_status", sa.String(20), nullable=False, server_default="ongoing"),
        sa.Column("cover_object_key", sa.String(500), nullable=True),
        sa.Column("cover_content_type", sa.String(100), nullable=True),
        sa.Column("boosty_url", sa.Text(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_chapter", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_admin_id", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "publication_status IN ('ongoing', 'completed', 'hiatus')",
            name="ck_titles_publication_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_titles"),
        sa.UniqueConstraint("slug", name="uq_titles_slug"),
    )
    for column in (
        "slug",
        "english_title",
        "original_title",
        "original_language",
        "publication_status",
        "is_published",
        "published_at",
        "latest_chapter",
    ):
        op.create_index(f"ix_titles_{column}", "titles", [column])

    op.create_table(
        "title_aliases",
        sa.Column("title_id", sa.Uuid(), nullable=False),
        sa.Column("alias", sa.String(255), nullable=False),
        sa.Column("normalized_alias", sa.String(255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["title_id"], ["titles.id"], name="fk_title_aliases_title_id_titles", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_title_aliases"),
        sa.UniqueConstraint("title_id", "normalized_alias", name="uq_title_aliases_title_alias"),
    )
    for column in ("title_id", "alias", "normalized_alias"):
        op.create_index(f"ix_title_aliases_{column}", "title_aliases", [column])

    op.create_table(
        "releases",
        sa.Column("title_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_start", sa.Integer(), nullable=False),
        sa.Column("chapter_end", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("boosty_url", sa.Text(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comments_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("validation_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("validation_message", sa.Text(), nullable=True),
        sa.Column(
            "detection_report",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_by_admin_id", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("chapter_start >= 0", name="ck_releases_chapter_start"),
        sa.CheckConstraint("chapter_end >= chapter_start", name="ck_releases_chapter_order"),
        sa.CheckConstraint(
            "validation_status IN ('pending', 'valid', 'warning', 'error', 'overridden')",
            name="ck_releases_validation_status",
        ),
        sa.ForeignKeyConstraint(
            ["title_id"], ["titles.id"], name="fk_releases_title_id_titles", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_releases"),
        sa.UniqueConstraint("title_id", "chapter_start", "chapter_end", name="uq_releases_title_range"),
    )
    for column in (
        "title_id",
        "chapter_start",
        "chapter_end",
        "is_published",
        "published_at",
        "validation_status",
    ):
        op.create_index(f"ix_releases_{column}", "releases", [column])

    op.create_table(
        "release_files",
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("file_kind", sa.String(10), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("file_kind IN ('pdf', 'epub')", name="ck_release_files_file_kind"),
        sa.ForeignKeyConstraint(
            ["release_id"], ["releases.id"], name="fk_release_files_release_id_releases", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_release_files"),
        sa.UniqueConstraint("release_id", "file_kind", name="uq_release_files_release_kind"),
    )
    for column in ("release_id", "file_kind"):
        op.create_index(f"ix_release_files_{column}", "release_files", [column])

    op.create_table(
        "file_versions",
        sa.Column("release_file_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("telegram_file_id", sa.String(500), nullable=True),
        sa.Column("telegram_file_unique_id", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_admin_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["release_file_id"],
            ["release_files.id"],
            name="fk_file_versions_release_file_id_release_files",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_file_versions"),
        sa.UniqueConstraint("object_key", name="uq_file_versions_object_key"),
        sa.UniqueConstraint(
            "release_file_id", "version", name="uq_file_versions_release_file_version"
        ),
    )
    for column in (
        "release_file_id",
        "object_key",
        "sha256",
        "telegram_file_unique_id",
        "is_active",
        "created_at",
    ):
        op.create_index(f"ix_file_versions_{column}", "file_versions", [column])

    op.create_table(
        "user_title_follows",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_title_follows_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["title_id"], ["titles.id"], name="fk_user_title_follows_title_id_titles", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_title_follows"),
        sa.UniqueConstraint("user_id", "title_id", name="uq_user_title_follows_user_title"),
    )
    for column in ("user_id", "title_id", "created_at"):
        op.create_index(f"ix_user_title_follows_{column}", "user_title_follows", [column])

    op.create_table(
        "deep_links",
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("title_id", sa.Uuid(), nullable=True),
        sa.Column("release_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("uses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("target_type IN ('title', 'release')", name="ck_deep_links_target_type"),
        sa.ForeignKeyConstraint(
            ["title_id"], ["titles.id"], name="fk_deep_links_title_id_titles", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["release_id"], ["releases.id"], name="fk_deep_links_release_id_releases", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_deep_links"),
        sa.UniqueConstraint("token", name="uq_deep_links_token"),
    )
    for column in ("token", "target_type", "title_id", "release_id", "is_active", "created_at"):
        op.create_index(f"ix_deep_links_{column}", "deep_links", [column])

    op.create_table(
        "channel_publications",
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.String(100), nullable=False),
        sa.Column("telegram_chat_id", sa.String(100), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_channel_publications"),
        sa.UniqueConstraint("target_type", "target_id", name="uq_channel_publications_target"),
    )
    for column in ("target_type", "target_id", "status"):
        op.create_index(f"ix_channel_publications_{column}", "channel_publications", [column])

    op.create_table(
        "download_events",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("file_version_id", sa.Uuid(), nullable=True),
        sa.Column("delivery_method", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_download_events_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["release_id"], ["releases.id"], name="fk_download_events_release_id_releases", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["file_version_id"], ["file_versions.id"], name="fk_download_events_file_version_id_file_versions", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_download_events"),
    )
    for column in ("user_id", "release_id", "file_version_id", "delivery_method", "status", "created_at"):
        op.create_index(f"ix_download_events_{column}", "download_events", [column])

    op.create_table(
        "outbox_deliveries",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"], ["outbox_events.id"], name="fk_outbox_deliveries_event_id_outbox_events", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_outbox_deliveries_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_deliveries"),
        sa.UniqueConstraint("event_id", "user_id", name="uq_outbox_deliveries_event_user"),
    )
    for column in ("event_id", "user_id", "status"):
        op.create_index(f"ix_outbox_deliveries_{column}", "outbox_deliveries", [column])


def downgrade() -> None:
    op.drop_table("outbox_deliveries")
    op.drop_table("download_events")
    op.drop_table("channel_publications")
    op.drop_table("deep_links")
    op.drop_table("user_title_follows")
    op.drop_table("file_versions")
    op.drop_table("release_files")
    op.drop_table("releases")
    op.drop_table("title_aliases")
    op.drop_table("titles")
    op.drop_index("ix_user_settings_pending_deep_link_token", table_name="user_settings")
    op.drop_column("user_settings", "pending_deep_link_token")
    op.drop_index("ix_users_manual_download_access", table_name="users")
    op.drop_column("users", "manual_download_access")
