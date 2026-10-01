"""Deterministic embedding fixture for tests (D18).

`daari_core` never loads a model or touches the network — embeddings are
always caller-supplied arrays. This fixture is the test-layer stand-in for
"the caller": `seeded_embedding(skill_id)` derives a reproducible unit
vector from the skill id's sha256 hash, so the same id always yields the
same vector, in this run and every future one, with no external model.

Two skill-id pairs are hand-set (not hash-derived) so the graph adjacency
test (cosine >= 0.75) has real signal on both sides of the threshold:
  - ("data_visualization_tableau", "data_visualization_powerbi") -> cosine
    exactly 0.85 (above 0.75: should land an adjacency edge).
  - ("mobile_app_usage", "route_navigation_gps") -> cosine exactly 0.30
    (below 0.75: should NOT land an adjacency edge).
Each hand-set pair lives on its own orthogonal pair of axes so it can't
accidentally collide with the other pair or with the hash-derived space.
"""

import hashlib

import numpy as np

DIM = 32

# axes 0,1 hand the "above threshold" pair its own 2-D subspace;
# axes 2,3 hand the "below threshold" pair its own, orthogonal, 2-D subspace.
_ABOVE_COSINE = 0.85
_BELOW_COSINE = 0.30


def _axis_vector(dim: int, axis: int) -> np.ndarray:
    v = np.zeros(dim)
    v[axis] = 1.0
    return v


def _rotated_vector(dim: int, axis_a: int, axis_b: int, cosine: float) -> np.ndarray:
    """Unit vector at exactly `cosine` similarity to `_axis_vector(dim, axis_a)`."""
    v = np.zeros(dim)
    v[axis_a] = cosine
    v[axis_b] = float(np.sqrt(1.0 - cosine**2))
    return v


_HAND_SET: dict[str, np.ndarray] = {
    "data_visualization_tableau": _axis_vector(DIM, 0),
    "data_visualization_powerbi": _rotated_vector(DIM, 0, 1, _ABOVE_COSINE),
    "mobile_app_usage": _axis_vector(DIM, 2),
    "route_navigation_gps": _rotated_vector(DIM, 2, 3, _BELOW_COSINE),
}


def seeded_embedding(skill_id: str) -> np.ndarray:
    """A deterministic unit vector for `skill_id`.

    Hand-set pairs (see module docstring) return their fixed vector; every
    other id is derived from `sha256(skill_id)` via `numpy`'s PCG64 RNG, so
    two calls with the same id always return the identical array.
    """
    if skill_id in _HAND_SET:
        return _HAND_SET[skill_id].copy()
    seed = int(hashlib.sha256(skill_id.encode()).hexdigest(), 16) % (2**32)
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(DIM)
    return vec / np.linalg.norm(vec)
