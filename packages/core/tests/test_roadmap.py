"""Roadmap tests, against the real committed taxonomy.

The three invariants in DAARI_BUILD_PLAN.md §7.3 are property tests, not
examples: learning a required skill never lengthens the path, raising demand
never moves a skill later, and diff(p, p) is empty.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from daari_core import roadmap
from daari_core.taxonomy import Taxonomy, load


@pytest.fixture(scope="module")
def taxonomy(skills_data, roles_data) -> Taxonomy:
    return load(skills_data, roles_data)


@pytest.fixture(scope="module")
def skill_ids(taxonomy: Taxonomy) -> list[str]:
    return sorted(taxonomy.skills)


def _full_level(taxonomy: Taxonomy, skill_id: str) -> int:
    return taxonomy.skills[skill_id].level


# --- shape -------------------------------------------------------------


def test_empty_profile_gets_the_whole_closure(taxonomy: Taxonomy):
    path = roadmap.compute(taxonomy, held={}, goal="data_analyst")
    assert path.steps, "a learner holding nothing must get a non-empty path"
    assert path.total_hours == pytest.approx(sum(s.hours for s in path.steps))
    assert path.goal_label_en == "Data Analyst"


def test_every_step_carries_a_computed_reason_and_a_source(taxonomy: Taxonomy):
    path = roadmap.compute(taxonomy, held={}, goal="data_analyst")
    for step in path.steps:
        assert step.why, f"{step.skill} has no why"
        assert step.source, f"{step.skill} has no source — a node without a source is not a node"
        assert step.label_te, f"{step.skill} has no Telugu label"


def test_prereqs_always_precede_their_dependents(taxonomy: Taxonomy):
    path = roadmap.compute(taxonomy, held={}, goal="data_analyst")
    position = {s.skill: i for i, s in enumerate(path.steps)}
    for step in path.steps:
        for prereq in step.prereqs:
            if prereq in position:
                assert position[prereq] < position[step.skill], (
                    f"{prereq} must come before {step.skill}"
                )


def test_unknown_goal_raises(taxonomy: Taxonomy):
    with pytest.raises(ValueError, match="unknown goal role"):
        roadmap.compute(taxonomy, held={}, goal="astronaut")


def test_weeks_at_rejects_a_nonpositive_pace(taxonomy: Taxonomy):
    path = roadmap.compute(taxonomy, held={}, goal="data_analyst")
    assert path.weeks_at(10) == pytest.approx(path.total_hours / 10)
    with pytest.raises(ValueError):
        path.weeks_at(0)


def test_holding_everything_yields_an_empty_path(taxonomy: Taxonomy):
    role = taxonomy.roles["delivery_executive"]
    closure = roadmap._closure(taxonomy, list(role.required_skills))
    held = {s: 5 for s in closure}
    path = roadmap.compute(taxonomy, held=held, goal="delivery_executive")
    assert path.steps == ()
    assert path.total_hours == 0


# --- §7.3 invariants ---------------------------------------------------


@settings(max_examples=60, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(learned=st.sampled_from(["sql_querying", "python_programming", "ms_excel_basic", "digital_literacy"]))
def test_learning_a_required_skill_never_lengthens_the_path(taxonomy: Taxonomy, learned: str):
    before = roadmap.compute(taxonomy, held={}, goal="data_analyst")
    after = roadmap.compute(taxonomy, held={learned: 5}, goal="data_analyst")
    assert len(after.steps) <= len(before.steps)
    assert after.total_hours <= before.total_hours


@settings(max_examples=60, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    boosted=st.sampled_from(["data_visualization_powerbi", "sql_querying", "excel_advanced", "data_cleaning"]),
    weight=st.floats(min_value=1.1, max_value=2.0),
)
def test_raising_demand_never_moves_a_skill_later(taxonomy: Taxonomy, boosted: str, weight: float):
    before = roadmap.compute(taxonomy, held={}, goal="data_analyst")
    after = roadmap.compute(taxonomy, held={}, goal="data_analyst", demand={boosted: weight})

    before_pos = {s.skill: i for i, s in enumerate(before.steps)}
    after_pos = {s.skill: i for i, s in enumerate(after.steps)}
    if boosted in before_pos and boosted in after_pos:
        assert after_pos[boosted] <= before_pos[boosted], (
            f"raising demand for {boosted} moved it later: "
            f"{before_pos[boosted]} -> {after_pos[boosted]}"
        )


def test_diff_of_a_path_against_itself_is_empty(taxonomy: Taxonomy):
    path = roadmap.compute(taxonomy, held={}, goal="data_analyst")
    d = roadmap.diff(path, path)
    assert d.is_empty()
    assert d.cause == "none"


# --- diff --------------------------------------------------------------


def test_learner_diff_reports_the_learned_skill_as_removed(taxonomy: Taxonomy):
    before = roadmap.compute(taxonomy, held={}, goal="data_analyst")
    after = roadmap.compute(taxonomy, held={"sql_querying": 5}, goal="data_analyst")
    d = roadmap.diff(before, after, cause="learner")

    assert "sql_querying" in d.removed
    assert d.added == ()
    assert d.hours_delta < 0, "learning a skill must reduce remaining hours"
    assert d.cause == "learner"


def test_market_diff_reorders_without_changing_the_set(taxonomy: Taxonomy):
    before = roadmap.compute(taxonomy, held={}, goal="data_analyst")
    after = roadmap.compute(
        taxonomy, held={}, goal="data_analyst", demand={"python_programming": 2.0}
    )
    d = roadmap.diff(before, after, cause="market")

    assert d.removed == () and d.added == (), "a market shock changes order, not membership"
    assert d.hours_delta == 0
    assert d.reordered, "a 2x demand shock on the longest skill must reorder the path"
    assert "python_programming" in d.reordered
    assert d.cause == "market"


def test_prerequisites_outrank_demand(taxonomy: Taxonomy):
    """Demand reorders only among skills that are *available* to learn.

    data_visualization_powerbi sits behind data_cleaning, which sits behind
    excel_advanced and sql_querying. No demand weight may pull it in front of
    its own prerequisites — a roadmap that told a learner to start with Power BI
    before SQL would be worse than useless. This is the guard on the Market
    shock demo beat: the shock reorders what it legitimately can, and the
    §6 gate's "moved up N steps" is bounded by the prerequisite chain.
    """
    after = roadmap.compute(
        taxonomy, held={}, goal="data_analyst", demand={"data_visualization_powerbi": 2.0}
    )
    position = {s.skill: i for i, s in enumerate(after.steps)}
    for prereq in ("data_cleaning", "sql_querying", "excel_advanced"):
        assert position[prereq] < position["data_visualization_powerbi"]


def test_demand_is_clamped_so_one_hot_skill_cannot_dominate(taxonomy: Taxonomy):
    capped = roadmap.compute(taxonomy, held={}, goal="data_analyst", demand={"sql_querying": 2.0})
    absurd = roadmap.compute(taxonomy, held={}, goal="data_analyst", demand={"sql_querying": 500.0})
    assert [s.skill for s in capped.steps] == [s.skill for s in absurd.steps]
    assert max(s.demand for s in absurd.steps) <= roadmap.MAX_DEMAND


def test_a_demand_signal_below_neutral_cannot_penalise_a_skill(taxonomy: Taxonomy):
    baseline = roadmap.compute(taxonomy, held={}, goal="data_analyst")
    suppressed = roadmap.compute(taxonomy, held={}, goal="data_analyst", demand={"sql_querying": 0.01})
    assert [s.skill for s in baseline.steps] == [s.skill for s in suppressed.steps]


# --- determinism -------------------------------------------------------


def test_same_inputs_give_identical_output(taxonomy: Taxonomy):
    a = roadmap.compute(taxonomy, held={"sql_querying": 3}, goal="data_analyst", demand={"excel_advanced": 1.5})
    b = roadmap.compute(taxonomy, held={"sql_querying": 3}, goal="data_analyst", demand={"excel_advanced": 1.5})
    assert [s.skill for s in a.steps] == [s.skill for s in b.steps]
    assert a.total_hours == b.total_hours


def test_compute_does_not_mutate_its_arguments(taxonomy: Taxonomy):
    held = {"sql_querying": 3}
    demand = {"excel_advanced": 1.5}
    roadmap.compute(taxonomy, held=held, goal="data_analyst", demand=demand)
    assert held == {"sql_querying": 3}
    assert demand == {"excel_advanced": 1.5}


def test_level_aware_holding_is_not_all_or_nothing(taxonomy: Taxonomy):
    """python_programming is required at level 4; holding level 2 must NOT
    remove it from the path."""
    required_level = taxonomy.roles["data_analyst"].required_skills["python_programming"]
    assert required_level == 4

    under = roadmap.compute(taxonomy, held={"python_programming": 2}, goal="data_analyst")
    at = roadmap.compute(taxonomy, held={"python_programming": 4}, goal="data_analyst")

    assert "python_programming" in [s.skill for s in under.steps]
    assert "python_programming" not in [s.skill for s in at.steps]
