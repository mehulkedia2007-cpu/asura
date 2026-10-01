"""Run after `alembic upgrade head`: python -m daari.seed_vectors."""

import asyncio

from daari.vector_store import sync_catalog_vectors


async def main() -> None:
    skills, roles = await sync_catalog_vectors()
    print(f"Stored {skills} skill and {roles} role vectors")


if __name__ == "__main__":
    asyncio.run(main())
