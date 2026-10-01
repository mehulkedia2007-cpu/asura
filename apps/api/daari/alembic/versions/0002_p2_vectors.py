"""P2 profile, skill and role vectors in pgvector.

Revision ID: 0002_p2_vectors
Revises: 0001_baseline
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_p2_vectors"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profile_vectors",
        sa.Column("profile_id", sa.String(64), primary_key=True),
        sa.Column("held", JSONB, nullable=False),
        sa.Column("version", sa.String(16), nullable=False),
        sa.Column("embedding", Vector(47), nullable=False),
        sa.Column("embedding_kind", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "skill_vectors",
        sa.Column("skill_id", sa.String(100), primary_key=True),
        sa.Column("embedding", Vector(47), nullable=False),
        sa.Column("embedding_kind", sa.String(64), nullable=False),
    )
    op.create_table(
        "role_vectors",
        sa.Column("role_id", sa.String(100), primary_key=True),
        sa.Column("embedding", Vector(47), nullable=False),
        sa.Column("embedding_kind", sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("role_vectors")
    op.drop_table("skill_vectors")
    op.drop_table("profile_vectors")
