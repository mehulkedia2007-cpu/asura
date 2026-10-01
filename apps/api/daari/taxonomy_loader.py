"""daari.taxonomy_loader — reads the committed taxonomy JSON into a `Taxonomy`.

The I/O lives here, in the API layer, and never inside `daari_core`
(core.md: "`load()` takes already-parsed dicts; this module never opens a
file"). This is the seam that keeps the engine pure.

Parsed once per process and cached: the seed files are committed data, not
runtime state, and re-reading them per request would put a disk hit on every
roadmap call for no benefit.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from daari_core.taxonomy import Taxonomy, load

# apps/api/daari/taxonomy_loader.py -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
TAXONOMY_DIR = REPO_ROOT / "data" / "taxonomy"


def _read(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"taxonomy seed missing: {path}. The engine has no built-in fallback data on purpose "
            "— an invented taxonomy is worse than an honest failure."
        )
    with path.open("r", encoding="utf-8") as f:
        parsed = json.load(f)
    if not parsed:
        raise ValueError(f"taxonomy seed is empty: {path}")
    return parsed


@lru_cache(maxsize=1)
def get_taxonomy() -> Taxonomy:
    """The process-wide taxonomy. Raises loudly if the seed files are missing
    or malformed — `daari_core.taxonomy.load` does the validation."""
    return load(
        skills=_read(TAXONOMY_DIR / "skills.json"),
        roles=_read(TAXONOMY_DIR / "roles.json"),
    )
