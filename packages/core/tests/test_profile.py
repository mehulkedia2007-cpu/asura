"""Failing tests for daari_core.profile (T4), written before the
implementation.

The cosine-shift invariant is exercised two ways:
  - a Hypothesis property test over the case that's actually provable in
    full generality for ARBITRARY vectors: when the newly learned skill's
    embedding *is* (proportional to) the goal direction, moving weight
    onto it can never reduce cosine-similarity to that goal. (Derived by
    hand: for p(u) = (1-u)*before + u*goal_hat with goal_hat a unit vector,
    d/du cos(p(u), goal_hat) has the same sign as (||before||^2 -
    (before . goal_hat)^2) * (1 - u), which is >= 0 by Cauchy-Schwarz for
    every u in [0, 1]. So this direction of the invariant is a real
    theorem, not a coincidence of the fixture.)
  - concrete cases for the general, real-world shape (a multi-skill goal
    where the learned skill is only one of several required skills). That
    general case is NOT provable for arbitrary embeddings — a skill whose
    embedding is adversarially unrelated to the goal's other components
    could, in principle, pull the average the wrong way — so it is checked
    on representative concrete values rather than asserted as a universal
    property. (Comment per T4: hypothesis would strengthen this once real,
    semantically-clustered multilingual embeddings replace the random
    fixture — unrelated skills would then reliably have low cosine to any
    goal they aren't part of.)
"""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from daari_core import profile
from tests.fixtures.embeddings import seeded_embedding

DIM = 8


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def test_vector_is_weighted_mean_with_weight_level_times_one_minus_se():
    embeddings = {"a": np.array([1.0, 0.0]), "b": np.array([0.0, 1.0])}
    held = {"a": (3, 0.2), "b": (5, 0.5)}  # weights: 3*0.8=2.4, 5*0.5=2.5

    vec, _version = profile.vector(held, embeddings)

    weight_a, weight_b = 3 * (1 - 0.2), 5 * (1 - 0.5)
    expected = (weight_a * embeddings["a"] + weight_b * embeddings["b"]) / (weight_a + weight_b)
    assert np.allclose(vec, expected)


def test_vector_fingerprint_changes_on_every_skill_update():
    embeddings = {"a": np.array([1.0, 0.0]), "b": np.array([0.0, 1.0])}

    _vec1, version1 = profile.vector({"a": (3, 0.2)}, embeddings)
    _vec2, version2 = profile.vector({"a": (3, 0.2), "b": (2, 0.1)}, embeddings)
    _vec3, version3 = profile.vector({"a": (4, 0.1), "b": (2, 0.1)}, embeddings)

    assert len({version1, version2, version3}) == 3


def test_core_requires_caller_supplied_embeddings():
    """core loads no model, ever — a held skill with no embedding is a
    caller bug, not something to silently default or fetch around."""
    held = {"a": (3, 0.2), "missing_skill": (2, 0.3)}
    embeddings = {"a": np.array([1.0, 0.0])}

    with pytest.raises((KeyError, ValueError)):
        profile.vector(held, embeddings)


@st.composite
def _profile_and_goal(draw):
    """A random `before` weighted-mean vector and a random unit goal
    direction, plus a positive weight to add for the skill whose
    embedding *is* that goal direction."""
    dim = DIM
    raw = draw(
        st.lists(st.floats(min_value=-5.0, max_value=5.0, allow_nan=False), min_size=dim, max_size=dim)
    )
    before = np.array(raw)
    if np.linalg.norm(before) < 1e-6:
        before = before + 1e-3  # avoid a degenerate zero profile
    goal_raw = draw(
        st.lists(st.floats(min_value=-5.0, max_value=5.0, allow_nan=False), min_size=dim, max_size=dim)
    )
    goal = np.array(goal_raw)
    if np.linalg.norm(goal) < 1e-6:
        goal = goal + np.array([1e-3] * dim)
    weight_on_new_skill = draw(st.floats(min_value=0.05, max_value=20.0, allow_nan=False))
    prior_weight = draw(st.floats(min_value=0.05, max_value=20.0, allow_nan=False))
    return before, goal, prior_weight, weight_on_new_skill


@given(_profile_and_goal())
def test_cosine_shift_toward_goal_is_non_negative_after_learning_a_required_skill(data):
    before, goal, prior_weight, weight_on_new_skill = data
    goal_hat = goal / np.linalg.norm(goal)

    # "Learning a required skill whose embedding is the goal direction" —
    # profile_after is the weighted mean of the prior profile and the new
    # skill's embedding (goal_hat itself).
    after = (prior_weight * before + weight_on_new_skill * goal_hat) / (prior_weight + weight_on_new_skill)

    if np.linalg.norm(after) < 1e-9 or np.linalg.norm(before) < 1e-9:
        return  # degenerate (near-zero) vector: cosine undefined, not the case under test

    shift = profile.cosine_shift(before, after, goal)
    assert shift >= -1e-9  # tolerate float noise, never a real decrease


def test_cosine_shift_concrete_multi_skill_goal_moves_toward_zero_or_positive():
    """Representative concrete case: goal is the mean of several required
    skills (sql_querying, python_programming, statistics_fundamentals);
    the learner adds sql_querying, one of those three, to their held
    skills. Not a universal property (see module docstring) — a concrete
    regression case on real fixture embeddings.
    """
    goal_skills = ["sql_querying", "python_programming", "statistics_fundamentals"]
    goal = np.mean([seeded_embedding(s) for s in goal_skills], axis=0)

    embeddings = {s: seeded_embedding(s) for s in goal_skills + ["ms_excel_basic"]}

    before_held = {"ms_excel_basic": (3, 0.3)}
    before_vec, _ = profile.vector(before_held, embeddings)

    after_held = {"ms_excel_basic": (3, 0.3), "sql_querying": (2, 0.6)}
    after_vec, _ = profile.vector(after_held, embeddings)

    shift = profile.cosine_shift(before_vec, after_vec, goal)
    assert shift >= 0


def test_diff_of_identical_vectors_has_zero_shift():
    v = seeded_embedding("python_programming")
    goal = seeded_embedding("sql_querying")
    assert profile.cosine_shift(v, v, goal) == pytest.approx(0.0, abs=1e-9)
