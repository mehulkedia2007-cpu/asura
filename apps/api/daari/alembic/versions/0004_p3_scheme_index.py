"""Source-backed scheme records with lexical and 768D semantic search."""

from alembic import op

revision = "0004_p3_scheme_index"
down_revision = "0003_p3_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE scheme_records (
            scheme_id text PRIMARY KEY,
            record jsonb NOT NULL,
            content_hash text NOT NULL,
            fetched_at timestamptz NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE scheme_chunks (
            scheme_id text NOT NULL REFERENCES scheme_records(scheme_id) ON DELETE CASCADE,
            locale text NOT NULL,
            content text NOT NULL,
            content_hash text NOT NULL,
            embedding vector(768),
            embedding_kind text,
            search_tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
            PRIMARY KEY (scheme_id, locale)
        )
    """)
    op.execute("CREATE INDEX scheme_chunks_search_idx ON scheme_chunks USING gin(search_tsv)")
    op.execute("CREATE INDEX scheme_chunks_embedding_idx ON scheme_chunks USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL")


def downgrade() -> None:
    op.drop_table("scheme_chunks")
    op.drop_table("scheme_records")
