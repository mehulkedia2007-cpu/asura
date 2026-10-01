"""Apply versioned schema and idempotent reviewed seeds before API publication.

Vercel installs root requirements.txt first. Never copy local credentials or
local rehearsal caches into a deployment. Preview environments need their own
database branch; this command does not import anonymous users or sessions.
"""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/api"), str(ROOT / "packages/core")]

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from daari.config import settings
from daari.db import engine
from daari.intel.corpus import seed, upsert
from daari.vector_store import sync_catalog_vectors


async def seed_catalog() -> None:
    try:
        skills, roles = await sync_catalog_vectors()
        questions = seed()
        await upsert(questions)
        print(f"Catalog ready: {skills} skills, {roles} roles, {len(questions)} reviewed questions")
    finally:
        await engine.dispose()


def main() -> None:
    if settings.VERCEL and make_url(settings.database_url).host in {None, "localhost", "127.0.0.1"}:
        raise RuntimeError("Connect cloud PostgreSQL to this Vercel project before deploying")
    # Runtime excludes apps/web; preserve the actual catalog audit as evidence.
    from daari.evidence import _i18n

    i18n = _i18n()
    if not i18n["passed"]:
        raise RuntimeError("Translation catalog verification failed")
    (ROOT / "evals/i18n_report.json").write_text(json.dumps(i18n, indent=2) + "\n")
    config = Config(str(ROOT / "apps/api/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "apps/api/daari/alembic"))
    command.upgrade(config, "head")
    asyncio.run(seed_catalog())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 — deployment boundary redacts driver credentials
        # Driver errors may contain credential-bearing connection strings.
        print(f"Backend initialization failed: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
