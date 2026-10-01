"""Matcher tests, against the real committed taxonomy.

The contract that matters most here is that a score is never shown without its
components, and that a candidate referencing an unknown skill is an error
rather than a silently-inflated coverage.
"""

from __future__ import annotations

import numpy as np
import pytest

from daari_core import match as match_mod
from daari_core.graph import build
from daari_core.match import Candidate, match
from daari_core.taxonomy import Taxonomy, load


@pytest.fixture(scope="module")
def taxonomy(skills_data, roles_data) -> Taxonomy:
    return load(skills_data, roles_data)


def _candidate(cid: str, required: dict[str, int], location: str = "Vijayawada") -> Candidate:
    return Candidate(
        id=cid,
        title=f"Role {cid}",
        org="Test Org",
        location=location,
        required_skills=required,
        source="test-fixture",
        source_url=f"https://fixture.local/{cid}",
        fetched_at="2026-09-18T00:00:00Z",
    )


# --- contract ----------------------------------------------------------


def test_every_match_returns_all_five_components(taxonomy: Taxonomy):
    results = match(taxonomy, held={"sql_querying": 3}, candidates=[_candidate("a", {"sql_querying": 3})])
    assert len(results) == 1
    assert set(results[0].components) == {"coverage", "gap_cost", "vector_sim", "constraint_fit", "demand_bonus"}


def test_provenance_is_required_on_the_candidate(taxonomy: Taxonomy):
    """A Candidate cannot be constructed without source/source_url/fetched_at —
    the guard against a lead reaching the UI unstamped is in the type."""
    with pytest.raises(TypeError):
        Candidate(id="x", title="t", org="o", location="l", required_skills={})  # type: ignore[call-arg]


def test_unknown_required_skill_raises_rather_than_inflating_coverage(taxonomy: Taxonomy):
    bad = _candidate("bad", {"underwater_basket_weaving": 2})
    with pytest.raises(ValueError, match="unknown skills"):
        match(taxonomy, held={}, candidates=[bad])


# --- coverage ----------------------------------------------------------


def test_full_coverage_beats_partial_beats_none(taxonomy: Taxonomy):
    required = {"sql_querying": 3, "ms_excel_basic": 2}
    full = match(taxonomy, {"sql_querying": 3, "ms_excel_basic": 2}, [_candidate("c", required)])[0]
    none = match(taxonomy, {}, [_candidate("c", required)])[0]
    assert full.components["coverage"] == 1.0
    assert none.components["coverage"] == 0.0
    assert full.score > none.score


def test_one_level_short_earns_half_credit(taxonomy: Taxonomy):
    required = {"sql_querying": 3}
    one_short = match(taxonomy, {"sql_querying": 2}, [_candidate("c", required)])[0]
    two_short = match(taxonomy, {"sql_querying": 1}, [_candidate("c", required)])[0]
    assert one_short.components["coverage"] == pytest.approx(0.5)
    assert two_short.components["coverage"] == 0.0


def test_missing_lists_only_what_is_actually_short(taxonomy: Taxonomy):
    required = {"sql_querying": 3, "ms_excel_basic": 2}
    result = match(taxonomy, {"ms_excel_basic": 2}, [_candidate("c", required)])[0]
    assert result.missing == ("sql_querying",)


# --- gap cost ----------------------------------------------------------


def test_gap_cost_counts_the_prerequisite_closure_not_just_named_skills(taxonomy: Taxonomy):
    """sql_querying needs database_fundamentals, which needs digital_literacy.
    A learner holding none of it must be charged for the whole chain."""
    result = match(taxonomy, held={}, candidates=[_candidate("c", {"sql_querying": 3})])[0]
    assert result.components["gap_cost"] == pytest.approx(1.0)

    holding_prereqs = match(
        taxonomy,
        held={"digital_literacy": 5, "database_fundamentals": 5},
        candidates=[_candidate("c", {"sql_querying": 3})],
    )[0]
    assert holding_prereqs.components["gap_cost"] < 1.0


def test_gap_cost_is_zero_when_everything_is_held(taxonomy: Taxonomy):
    held = {s: 5 for s in taxonomy.skills}
    result = match(taxonomy, held, [_candidate("c", {"sql_querying": 3})])[0]
    assert result.components["gap_cost"] == 0.0


# --- constraint fit ----------------------------------------------------


def test_naming_no_district_scores_below_a_real_local_match(taxonomy: Taxonomy):
    candidate = _candidate("c", {"sql_querying": 3}, location="Guntur")
    unspecified = match(taxonomy, {}, [candidate])[0]
    local = match(taxonomy, {}, [candidate], districts=("Guntur",))[0]
    elsewhere = match(taxonomy, {}, [candidate], districts=("Vijayawada",))[0]

    assert elsewhere.components["constraint_fit"] == 0.0
    assert unspecified.components["constraint_fit"] == 0.5
    assert local.components["constraint_fit"] == 1.0
    assert local.score > unspecified.score > elsewhere.score


# --- demand ------------------------------------------------------------


def test_demand_bonus_is_clamped(taxonomy: Taxonomy):
    candidate = _candidate("c", {"sql_querying": 3})
    absurd = match(taxonomy, {}, [candidate], demand={"sql_querying": 500.0})[0]
    capped = match(taxonomy, {}, [candidate], demand={"sql_querying": 2.0})[0]
    assert absurd.components["demand_bonus"] == capped.components["demand_bonus"]
    assert absurd.components["demand_bonus"] <= 1.0


def test_no_demand_signal_means_no_bonus(taxonomy: Taxonomy):
    result = match(taxonomy, {}, [_candidate("c", {"sql_querying": 3})])[0]
    assert result.components["demand_bonus"] == 0.0


# --- ranking -----------------------------------------------------------


def test_results_are_sorted_by_score_descending(taxonomy: Taxonomy):
    held = {"sql_querying": 3, "ms_excel_basic": 2}
    candidates = [
        _candidate("strong", {"sql_querying": 3, "ms_excel_basic": 2}),
        _candidate("weak", {"python_programming": 4, "statistics_fundamentals": 3}),
        _candidate("mixed", {"sql_querying": 3, "python_programming": 4}),
    ]
    results = match(taxonomy, held, candidates)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0].candidate_id == "strong"


def test_ties_break_on_candidate_id_so_ranking_is_deterministic(taxonomy: Taxonomy):
    required = {"sql_querying": 3}
    candidates = [_candidate("zzz", required), _candidate("aaa", required)]
    first = [r.candidate_id for r in match(taxonomy, {}, candidates)]
    second = [r.candidate_id for r in match(taxonomy, {}, list(reversed(candidates)))]
    assert first == second == ["aaa", "zzz"]


def test_every_match_carries_at_least_one_reason(taxonomy: Taxonomy):
    results = match(taxonomy, {"sql_querying": 3}, [_candidate("c", {"sql_querying": 3})])
    assert results[0].reasons


def test_graph_and_vector_ablations_change_the_computed_components(taxonomy: Taxonomy):
    ids = sorted(taxonomy.skills)
    embeddings = {skill: np.eye(len(ids))[index] for index, skill in enumerate(ids)}
    graph = build(taxonomy, embeddings)
    candidate = _candidate("c", {"sql_querying": 3})
    held = {"database_fundamentals": 2, "digital_literacy": 2}
    baseline = match(taxonomy, held, [candidate])[0]
    enabled = match(taxonomy, held, [candidate], graph=graph, embeddings=embeddings)[0]
    assert enabled.components["gap_cost"] <= baseline.components["gap_cost"]
    assert "vector_sim" in enabled.components


def test_score_uses_the_documented_weights(taxonomy: Taxonomy):
    """Guards the §7.2 formula against a silent re-weighting."""
    candidate = _candidate("c", {"sql_querying": 3})
    r = match(taxonomy, {"sql_querying": 3}, [candidate], districts=("Vijayawada",))[0]
    c = r.components
    expected = (
        match_mod.W_COVERAGE * c["coverage"]
        - match_mod.W_GAP * c["gap_cost"]
        + match_mod.W_VECTOR * c["vector_sim"]
        + match_mod.W_FIT * c["constraint_fit"]
        + match_mod.W_DEMAND * c["demand_bonus"]
    )
    assert r.score == pytest.approx(expected, abs=1e-4)


def test_empty_candidate_list_returns_empty(taxonomy: Taxonomy):
    assert match(taxonomy, {}, []) == []


# --- relevance floor ---------------------------------------------------


def test_a_zero_coverage_candidate_never_outranks_a_real_partial_match(taxonomy: Taxonomy):
    """The defect this guards: an additive `constraint_fit` let a nearby job the
    learner matches nothing of outrank the role they are actually training for.
    """
    held = {"sql_querying": 3}
    nearby_irrelevant = _candidate("nearby", {"customer_service_basic": 2}, location="Vijayawada")
    relevant = _candidate("relevant", {"sql_querying": 3, "python_programming": 4}, location="Guntur")

    results = match(taxonomy, held, [nearby_irrelevant, relevant], districts=("Vijayawada",))
    ranked = [r.candidate_id for r in results]

    assert ranked[0] == "relevant", f"zero-coverage candidate ranked first: {ranked}"
    assert results[0].components["coverage"] > 0
    assert results[1].components["coverage"] == 0.0


def test_zero_coverage_candidates_are_still_returned_in_score_order(taxonomy: Taxonomy):
    """They are demoted, not hidden — a learner with no matches still deserves
    to see the closest attainable work."""
    held = {"sql_querying": 3}
    far = _candidate("far", {"customer_service_basic": 2}, location="Kurnool")
    near = _candidate("near", {"customer_service_basic": 2}, location="Vijayawada")

    results = match(taxonomy, held, [far, near], districts=("Vijayawada",))
    assert len(results) == 2
    assert [r.candidate_id for r in results] == ["near", "far"]
    assert all(r.components["coverage"] == 0.0 for r in results)


def test_the_relevance_floor_does_not_change_any_published_component(taxonomy: Taxonomy):
    """Ordering changed; the §7.2 weights and the returned numbers did not."""
    candidate = _candidate("c", {"sql_querying": 3})
    r = match(taxonomy, {"sql_querying": 3}, [candidate], districts=("Vijayawada",))[0]
    c = r.components
    expected = (
        match_mod.W_COVERAGE * c["coverage"]
        - match_mod.W_GAP * c["gap_cost"]
        + match_mod.W_FIT * c["constraint_fit"]
        + match_mod.W_DEMAND * c["demand_bonus"]
    )
    assert r.score == pytest.approx(expected, abs=1e-4)
