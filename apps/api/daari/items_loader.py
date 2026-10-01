"""daari.items_loader — CAT item bank, loaded from committed data.

Like `taxonomy_loader` and `leads`, all I/O lives here; `daari_core.assess`
never touches JSON or the network (core.md).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from daari_core.assess import Item

REPO_ROOT = Path(__file__).resolve().parents[3]
ITEMS_FILE = REPO_ROOT / "data" / "items" / "items.json"


@lru_cache(maxsize=1)
def get_item_bank() -> tuple[Item, ...]:
    if not ITEMS_FILE.exists():
        raise FileNotFoundError(f"item bank missing: {ITEMS_FILE}")
    with ITEMS_FILE.open("r", encoding="utf-8") as f:
        rows = json.load(f)
    if not rows:
        raise ValueError(f"item bank is empty: {ITEMS_FILE}")
    items = tuple(
        Item(
            id=row["id"],
            skill_id=row["skill_id"],
            band=float(row["band"]),
            text=row["text"],
            answer=row["answer"],
            # Every row carries either a `source` citation or a stated
            # `rationale` (data.md: "a node without a source is not a
            # node" — the two_wheeler_* items use rationale instead).
            source=row.get("source", row.get("rationale", "")),
            rationale=row.get("rationale", ""),
            text_te=row.get("text_te", ""),
            text_hi=row.get("text_hi", ""),
            answer_te=row.get("answer_te", ""),
            answer_hi=row.get("answer_hi", ""),
            rationale_te=row.get("rationale_te", ""),
            rationale_hi=row.get("rationale_hi", ""),
        )
        for row in rows
    )
    ids = [i.id for i in items]
    if len(ids) != len(set(ids)):
        raise ValueError("item bank has duplicate ids")
    return items
