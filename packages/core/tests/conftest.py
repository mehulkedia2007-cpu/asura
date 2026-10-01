"""Shared test fixtures.

Loads the real T0/T0b seed files (`data/taxonomy/skills.json`,
`data/taxonomy/roles.json`, `data/items/items.json`) into plain parsed
lists of dicts — the shape `daari_core.taxonomy.load()` consumes.

JSON parsing happens here, in the test/caller layer, never inside
`daari_core` itself (core.md purity: no I/O in core). This is also what
proves the seed file *format* is real: the tests load the actual files
under `data/`, not an in-test literal.
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"


def _load_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def skills_data() -> list[dict]:
    return _load_json(DATA_DIR / "taxonomy" / "skills.json")


@pytest.fixture(scope="session")
def roles_data() -> list[dict]:
    return _load_json(DATA_DIR / "taxonomy" / "roles.json")


@pytest.fixture(scope="session")
def items_data() -> list[dict]:
    return _load_json(DATA_DIR / "items" / "items.json")
