"""pgvector persistence for the seed embedding model and anonymous profiles."""

import numpy as np
import sqlalchemy as sa
from daari_core.profile import vector
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, insert

from daari.db import engine
from daari.embeddings import get_embeddings
from daari.taxonomy_loader import get_taxonomy

EMBEDDING_KIND = "prerequisite-feature-seed"
DIM = 47  # The committed 24-skill P2 taxonomy. A taxonomy expansion needs a migration.
metadata = sa.MetaData()
profile_vectors = sa.Table(
    "profile_vectors", metadata,
    sa.Column("profile_id", sa.String(64), primary_key=True),
    sa.Column("held", JSONB, nullable=False),
    sa.Column("version", sa.String(16), nullable=False),
    sa.Column("embedding", Vector(DIM), nullable=False),
    sa.Column("embedding_kind", sa.String(64), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)
skill_vectors = sa.Table(
    "skill_vectors", metadata,
    sa.Column("skill_id", sa.String(100), primary_key=True),
    sa.Column("embedding", Vector(DIM), nullable=False),
    sa.Column("embedding_kind", sa.String(64), nullable=False),
)
role_vectors = sa.Table(
    "role_vectors", metadata,
    sa.Column("role_id", sa.String(100), primary_key=True),
    sa.Column("embedding", Vector(DIM), nullable=False),
    sa.Column("embedding_kind", sa.String(64), nullable=False),
)


async def save_profile(profile_id: str, held: dict[str, int], se: dict[str, float]) -> str:
    embeddings = get_embeddings()
    vec, version = vector({s: (level, se.get(s, 0.2)) for s, level in held.items()}, embeddings)
    stmt = insert(profile_vectors).values(
        profile_id=profile_id, held=held, version=version,
        embedding=vec, embedding_kind=EMBEDDING_KIND,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[profile_vectors.c.profile_id],
        set_={
            "held": stmt.excluded.held,
            "version": stmt.excluded.version,
            "embedding": stmt.excluded.embedding,
            "embedding_kind": EMBEDDING_KIND,
            "updated_at": sa.func.now(),
        },
    )
    async with engine.begin() as connection:
        await connection.execute(stmt)
    return version


async def sync_catalog_vectors() -> tuple[int, int]:
    taxonomy = get_taxonomy()
    embeddings = get_embeddings()
    if any(len(value) != DIM for value in embeddings.values()):
        raise ValueError("P2 taxonomy vector dimension changed; migrate pgvector columns first")
    async with engine.begin() as connection:
        for skill_id, embedding in embeddings.items():
            stmt = insert(skill_vectors).values(
                skill_id=skill_id, embedding=embedding, embedding_kind=EMBEDDING_KIND,
            )
            await connection.execute(stmt.on_conflict_do_update(
                index_elements=[skill_vectors.c.skill_id],
                set_={"embedding": stmt.excluded.embedding, "embedding_kind": EMBEDDING_KIND},
            ))
        for role_id, role in taxonomy.roles.items():
            embedding = np.mean([embeddings[s] for s in role.required_skills], axis=0)
            stmt = insert(role_vectors).values(
                role_id=role_id, embedding=embedding, embedding_kind=EMBEDDING_KIND,
            )
            await connection.execute(stmt.on_conflict_do_update(
                index_elements=[role_vectors.c.role_id],
                set_={"embedding": stmt.excluded.embedding, "embedding_kind": EMBEDDING_KIND},
            ))
    return len(embeddings), len(taxonomy.roles)
