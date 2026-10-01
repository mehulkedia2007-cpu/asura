"""daari_core.graph — the skill graph built from a Taxonomy plus
caller-supplied embeddings and (optionally) live PMI co-occurrence stats.

Pure: numpy + networkx + stdlib only, no I/O, no randomness, no clock.
Embeddings are always supplied by the caller (D18) — this module never
loads a model. `pmi=None` (no live listings yet) builds prereq + adjacency
edges only; `edges_added_today` then reports 0 with an explicit reason
(§13 cut 10), never a hidden number.

Uses `MultiDiGraph`, not a plain `DiGraph`: a prereq edge and an adjacency
(or transferability) edge can legitimately exist between the same pair of
skills, and a simple `DiGraph` would silently drop one when the other is
added. Downstream gap-cost work in match.py needs shortest
path "over all three edge types" (build plan §7.3) to see all of them.
"""

import itertools
from dataclasses import dataclass

import networkx as nx
import numpy as np

from daari_core.taxonomy import Taxonomy

ADJACENCY_COSINE_THRESHOLD = 0.75
ADJACENCY_WEIGHT_FACTOR = 0.3

TRANSFER_PMI_THRESHOLD = 1.0
TRANSFER_COUNT_THRESHOLD = 5
TRANSFER_PMI_CAP = 3.0
TRANSFER_WEIGHT_DISCOUNT_CAP = 0.5

TRANSFERABILITY_OFF_REASON = "transferability off"


@dataclass(frozen=True)
class Graph:
    nx: nx.MultiDiGraph
    edges_added_today: int
    edges_added_today_reason: str | None = None


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _require_embedding(embeddings: dict[str, np.ndarray], skill_id: str) -> np.ndarray:
    if skill_id not in embeddings:
        raise KeyError(f"no embedding supplied for skill {skill_id!r} — daari_core loads no model, ever")
    return embeddings[skill_id]


def build(
    taxonomy: Taxonomy,
    embeddings: dict[str, np.ndarray],
    pmi: dict[tuple[str, str], tuple[float, int]] | None = None,
) -> Graph:
    g: nx.MultiDiGraph = nx.MultiDiGraph()
    skill_ids = sorted(taxonomy.skills)
    for skill_id in skill_ids:
        g.add_node(skill_id)

    # Prerequisite edges: prereq -> skill, weight = the skill's hours
    # (the cost of learning it once its prereq is held).
    for skill_id in skill_ids:
        node = taxonomy.skills[skill_id]
        for prereq_id in node.prereqs:
            g.add_edge(prereq_id, skill_id, kind="prereq", weight=float(node.hours))

    # Adjacency edges: cosine(embedding_a, embedding_b) >= 0.75, both
    # directions (adjacency is symmetric), weight = 0.3 * avg(hours).
    for a, b in itertools.combinations(skill_ids, 2):
        vec_a = _require_embedding(embeddings, a)
        vec_b = _require_embedding(embeddings, b)
        if _cosine(vec_a, vec_b) >= ADJACENCY_COSINE_THRESHOLD:
            avg_hours = (taxonomy.skills[a].hours + taxonomy.skills[b].hours) / 2.0
            weight = ADJACENCY_WEIGHT_FACTOR * avg_hours
            g.add_edge(a, b, kind="adjacency", weight=weight)
            g.add_edge(b, a, kind="adjacency", weight=weight)

    # Transferability edges: learned at runtime from live listings (PMI).
    # None means no live data was supplied this build — report 0 with a
    # reason, not a hidden number.
    edges_added_today = 0
    reason: str | None = TRANSFERABILITY_OFF_REASON if pmi is None else None
    if pmi is not None:
        for a, b in sorted(pmi):
            pmi_value, count = pmi[(a, b)]
            if pmi_value >= TRANSFER_PMI_THRESHOLD and count >= TRANSFER_COUNT_THRESHOLD:
                if a not in taxonomy.skills or b not in taxonomy.skills:
                    raise ValueError(f"pmi references unknown skill pair ({a!r}, {b!r})")
                discount = min(pmi_value / TRANSFER_PMI_CAP, TRANSFER_WEIGHT_DISCOUNT_CAP)
                weight = taxonomy.skills[b].hours * (1 - discount)
                g.add_edge(a, b, kind="transferability", weight=weight)
                edges_added_today += 1

    return Graph(nx=g, edges_added_today=edges_added_today, edges_added_today_reason=reason)
