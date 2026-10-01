"""Timestamped P3 source cache and geocoding cache."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_p3_sources"
down_revision = "0002_p2_vectors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_snapshots",
        sa.Column("cache_key", sa.String(300), primary_key=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "geocodes",
        sa.Column("place_key", sa.String(300), primary_key=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("geocodes")
    op.drop_table("source_snapshots")
