"""Restore searchable descriptions/tags from retained official source snapshots."""

import hashlib
import json

from alembic import op
from sqlalchemy import text

revision = "0006_p3_search_context"
down_revision = "0005_p3_source_checks"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    additions = {}
    snapshots = conn.execute(
        text("""
        SELECT payload FROM source_snapshots
        WHERE cache_key LIKE 'myscheme:en:%' ORDER BY fetched_at
    """)
    ).scalars()
    for payload in snapshots:
        for item in (payload.get("data") or {}).get("hits", {}).get("items", []):
            fields = item.get("fields", item)
            slug = fields.get("slug")
            description = fields.get("briefDescriptionEng") or fields.get(
                "briefDescription"
            )
            if slug and isinstance(description, str):
                additions[slug] = {
                    "summary_en": description,
                    "tags": fields.get("tags") or [],
                }
    for scheme_id, record in conn.execute(
        text("SELECT scheme_id, record FROM scheme_records")
    ).all():
        if scheme_id not in additions:
            continue
        # Backfill missing context only; do not change eligibility or freshness.
        record.update(
            {k: v for k, v in additions[scheme_id].items() if not record.get(k)}
        )
        conn.execute(
            text(
                "UPDATE scheme_records SET record=CAST(:record AS jsonb) WHERE scheme_id=:id"
            ),
            {"id": scheme_id, "record": json.dumps(record, ensure_ascii=False)},
        )
        row = conn.execute(
            text(
                "SELECT content FROM scheme_chunks WHERE scheme_id=:id AND locale='en'"
            ),
            {"id": scheme_id},
        ).first()
        if row:
            content = record["summary_en"] + "\n" + row[0]
            conn.execute(
                text("""
                UPDATE scheme_chunks SET content=:content, content_hash=:hash,
                    embedding=NULL, embedding_kind=NULL WHERE scheme_id=:id AND locale='en'
            """),
                {
                    "id": scheme_id,
                    "content": content,
                    "hash": hashlib.sha256(content.encode()).hexdigest(),
                },
            )


def downgrade():
    # Retain recovered source context; removing it would lose source data again.
    pass
