"""renumber anonymous users from one

Revision ID: 20260804_0009
Revises: 20260804_0008
Create Date: 2026-08-05 02:10:00
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260804_0009"
down_revision: str | None = "20260804_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _renumber(offset: int) -> None:
    # Move all current values out of the positive range first so the unique
    # constraint cannot collide while row_number() values are assigned.
    op.execute("UPDATE users SET anonymous_id = -ABS(anonymous_id)")
    op.execute(
        f"""
        WITH ranked AS (
            SELECT
                id,
                (ROW_NUMBER() OVER (ORDER BY created_at, id) + {offset})::bigint AS next_id
            FROM users
        )
        UPDATE users AS target
        SET anonymous_id = ranked.next_id
        FROM ranked
        WHERE target.id = ranked.id
        """
    )
    op.execute(
        """
        DO $$
        DECLARE
            sequence_name text;
            next_value bigint;
        BEGIN
            sequence_name := pg_get_serial_sequence('users', 'anonymous_id');
            SELECT COALESCE(MAX(anonymous_id), 0) + 1 INTO next_value FROM users;
            IF sequence_name IS NOT NULL THEN
                EXECUTE format('ALTER SEQUENCE %s RESTART WITH %s', sequence_name, next_value);
            END IF;
        END $$
        """
    )


def upgrade() -> None:
    _renumber(0)


def downgrade() -> None:
    _renumber(999)
