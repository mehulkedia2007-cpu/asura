"""Rural entry point; the same core engine serves this persona."""

from daari_core.roadmap import Path, compute
from daari_core.taxonomy import Taxonomy


def get_path(taxonomy: Taxonomy, held: dict[str, int], goal: str, demand: dict[str, float]) -> Path:
    return compute(taxonomy, held, goal, demand)
