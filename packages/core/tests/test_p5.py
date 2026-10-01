from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from daari_core.interview_metrics import measure, weakest_star
from daari_core.prep import required_path, schedule
from daari_core.roadmap import Path, Step


def test_metrics_are_indicators_with_exact_boundaries():
    metrics = measure("During a project my goal was clear. I built SQL reports and reduced errors by 20%.", 60, ("SQL", "Excel"))
    assert metrics["star_coverage"] == 1
    assert metrics["quantifiers"] == ["20%"]
    assert metrics["keyword_coverage"] == .5
    assert weakest_star(metrics) is None
    assert measure("human umbrella sqlish")["filler_count"] == 0
    assert measure("అంటే ప్రాజెక్ట్ లక్ష్యం చేశాను ఫలితం")["star_coverage"] == 1
    assert measure("")["wpm"] is None


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_duration_rejects_invalid(value):
    with pytest.raises(ValueError):
        measure("answer", value)


@given(st.lists(st.integers(min_value=1, max_value=30), min_size=1, max_size=10),
       st.integers(min_value=0, max_value=40), st.integers(min_value=1, max_value=16))
def test_schedule_conserves_hours_and_order(hours, days, pace):
    steps = tuple(Step(str(i), str(i), str(i), str(i), h, 1, (), (), "source", 1) for i,h in enumerate(hours))
    path = Path("goal", "goal", "goal", steps, sum(hours))
    start = date(2026, 9, 26)
    plan = schedule(path, start, start+timedelta(days=days), pace)
    allocated = sum(a["hours"] for row in plan["days"] for a in row["allocations"])
    assert allocated + plan["shortfall_hours"] == sum(hours)
    assert allocated <= days*pace
    assert all(sum(a["hours"] for a in row["allocations"]) <= pace for row in plan["days"])
    assert all(date.fromisoformat(row["date"]) < start+timedelta(days=days) for row in plan["days"])
    skills = [int(a["skill"]) for row in plan["days"] for a in row["allocations"]]
    assert skills == sorted(skills)


def test_prep_unions_corpus_skills_without_mutation(skills_data, roles_data):
    from daari_core.taxonomy import load
    taxonomy = load(skills_data, roles_data)
    goal = next(iter(taxonomy.roles))
    extra = next((s for s in taxonomy.skills if s not in taxonomy.roles[goal].required_skills), None)
    if extra is None:
        pytest.skip("fixture has no extra skill")
    before = dict(taxonomy.roles[goal].required_skills)
    result = required_path(taxonomy, {}, goal, {extra: 5}, {})
    assert extra in {s.skill for s in result.steps}
    assert taxonomy.roles[goal].required_skills == before
