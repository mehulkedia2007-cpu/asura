"""Deterministic graph-feature vectors for the committed P2 taxonomy.

The representation uses one dimension per canonical skill. Each skill marks
itself and its prerequisites, so related skills share coordinates. It is a
small, reproducible seed representation, not a learned fastembed model.
"""

from functools import lru_cache

import numpy as np
from daari_core.taxonomy import Taxonomy

from daari.taxonomy_loader import get_taxonomy


@lru_cache(maxsize=1)
def get_embeddings() -> dict[str, np.ndarray]:
    taxonomy: Taxonomy = get_taxonomy()
    ids = sorted(taxonomy.skills)
    index = {skill: i for i, skill in enumerate(ids)}
    groups = sorted({"_".join(skill.split("_")[:2]) for skill in ids})
    group_index = {group: len(ids) + i for i, group in enumerate(groups)}
    output: dict[str, np.ndarray] = {}
    for skill in ids:
        value = np.zeros(len(ids) + len(groups), dtype=float)
        value[index[skill]] = 1.0
        group = "_".join(skill.split("_")[:2])
        if sum(other.startswith(f"{group}_") for other in ids) > 1:
            value[group_index[group]] = 2.0
        frontier = [(skill, 0)]
        visited = {skill}
        while frontier:
            current, depth = frontier.pop()
            for prereq in taxonomy.skills[current].prereqs:
                if prereq not in visited:
                    visited.add(prereq)
                    value[index[prereq]] = 0.5 ** (depth + 1)
                    frontier.append((prereq, depth + 1))
        output[skill] = value / np.linalg.norm(value)
    return output
