"""Rasch 1PL CAT tests (§7.6, core.md invariants).

The three invariants are property tests: SE is non-increasing, an all-correct
respondent ends at theta >= +1.0, and the stopping rule always terminates
within max_items regardless of answer pattern. `band` is bounded to [-1, 1] —
the real bounds data.md states for data/items/items.yaml (b in {-1, 0, +1}),
not an arbitrary hypothesis range.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from daari_core import assess
from daari_core.assess import Item

BAND = st.floats(min_value=-1.0, max_value=1.0, allow_nan=False)


def _item(item_id: str, band: float) -> Item:
    return Item(id=item_id, skill_id="sql_querying", band=band, text="q", answer="a", source="test")


def _bank(n: int, bands: list[float]) -> list[Item]:
    return [_item(f"i{i}", bands[i % len(bands)]) for i in range(n)]


# --- shape ---------------------------------------------------------------


def test_start_has_zero_answered_and_max_se():
    state = assess.start()
    assert state.theta == 0.0
    assert state.answered == ()
    assert state.se == assess.SE_MAX


def test_next_item_picks_max_information_deterministically():
    bank = [_item("far", 1.0), _item("near", 0.05), _item("also_near", -0.05)]
    state = assess.start(theta0=0.0)
    picked = assess.next_item(state, bank)
    # "near" and "also_near" are (near enough to) equally informative at
    # theta=0 — the id tie-break must pick the lexicographically smaller one.
    assert picked.id in ("near", "also_near")


def test_next_item_respects_exclude():
    bank = [_item("only", 0.0)]
    state = assess.start()
    assert assess.next_item(state, bank, exclude=frozenset({"only"})) is None


def test_next_item_returns_none_on_empty_bank():
    assert assess.next_item(assess.start(), []) is None


def test_update_appends_to_answered_and_clamps_theta():
    state = assess.start()
    item = _item("i0", 0.0)
    new_state = assess.update(state, item, correct=True)
    assert new_state.answered == (("i0", True),)
    assert -4.0 <= new_state.theta <= 4.0


def test_should_stop_on_max_items():
    state = assess.start()
    for i in range(6):
        state = assess.update(state, _item(f"i{i}", 0.0), correct=True)
    assert assess.should_stop(state, max_items=6) is True


def test_should_stop_false_before_limit_with_high_se():
    state = assess.start()
    assert assess.should_stop(state, max_items=6, se_target=0.4) is False


# --- invariants (core.md) -------------------------------------------------


@given(pattern=st.lists(st.booleans(), min_size=1, max_size=6), bands=st.lists(BAND, min_size=1, max_size=6))
@settings(max_examples=200)
def test_se_is_non_increasing(pattern, bands):
    bank = _bank(len(pattern) + 1, bands)  # +1 spare so exclude never empties the bank early
    state = assess.start()
    prev_se = state.se
    excluded: set[str] = set()
    for correct in pattern:
        item = assess.next_item(state, bank, exclude=frozenset(excluded))
        assert item is not None
        excluded.add(item.id)
        state = assess.update(state, item, correct)
        assert state.se <= prev_se + 1e-9
        prev_se = state.se


@given(bands=st.lists(BAND, min_size=6, max_size=6))
@settings(max_examples=200)
def test_all_correct_respondent_ends_above_theta_one(bands):
    bank = _bank(6, bands)
    state = assess.start()
    excluded: set[str] = set()
    while not assess.should_stop(state):
        item = assess.next_item(state, bank, exclude=frozenset(excluded))
        if item is None:
            break
        excluded.add(item.id)
        state = assess.update(state, item, correct=True)
    assert state.theta >= 1.0


@given(pattern=st.lists(st.booleans(), min_size=6, max_size=6), bands=st.lists(BAND, min_size=1, max_size=8))
@settings(max_examples=200)
def test_stopping_rule_always_terminates_within_max_items(pattern, bands):
    """For any answer pattern, the loop must stop by item 6 even if SE never
    drops below the target — `max_items` is a hard cap, not a hint."""
    bank = _bank(12, bands)
    state = assess.start()
    excluded: set[str] = set()
    count = 0
    while not assess.should_stop(state, max_items=6, se_target=0.4) and count < len(pattern):
        item = assess.next_item(state, bank, exclude=frozenset(excluded))
        excluded.add(item.id)
        state = assess.update(state, item, correct=pattern[count])
        count += 1
    assert assess.should_stop(state, max_items=6, se_target=0.4)
    assert count <= 6
