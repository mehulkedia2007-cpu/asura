"""The embeddings test fixture (D18) must itself be deterministic: this is
what lets `test_graph.py` treat its output as a stable, reproducible input
rather than a random one. Proven here, once, so every other test can rely
on it without re-checking.
"""

import numpy as np

from tests.fixtures.embeddings import seeded_embedding


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def test_seeded_embedding_is_deterministic_across_calls():
    first = seeded_embedding("python_programming")
    second = seeded_embedding("python_programming")
    assert np.array_equal(first, second)


def test_seeded_embedding_differs_across_ids():
    a = seeded_embedding("python_programming")
    b = seeded_embedding("sql_querying")
    assert not np.array_equal(a, b)


def test_hand_set_pair_lands_above_cosine_threshold():
    a = seeded_embedding("data_visualization_tableau")
    b = seeded_embedding("data_visualization_powerbi")
    assert _cosine(a, b) >= 0.75


def test_hand_set_pair_lands_below_cosine_threshold():
    a = seeded_embedding("mobile_app_usage")
    b = seeded_embedding("route_navigation_gps")
    assert _cosine(a, b) < 0.75
