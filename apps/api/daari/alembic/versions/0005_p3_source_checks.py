"""Persist government source health, including unavailable sources."""

from alembic import op

revision = "0005_p3_source_checks"
down_revision = "0004_p3_scheme_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE source_checks (
            source_id text PRIMARY KEY,
            status text NOT NULL,
            error text,
            links integer NOT NULL DEFAULT 0,
            checked_at timestamptz NOT NULL
        )
    """)


def downgrade() -> None:
    op.drop_table("source_checks")
