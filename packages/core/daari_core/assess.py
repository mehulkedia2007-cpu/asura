"""daari_core.assess — 1PL Rasch CAT: item selection, ability update, stopping (§7.6).

Pure: stdlib only (math). No I/O, no clock, no randomness (core.md). The
caller (the API lane) parses `data/items/items.json` into `Item`s; this
module never touches the network.

`Item`'s field names mirror items.json's own keys (`id`, `skill_id`, `band`,
`text`, `answer`, `source`, `rationale`) rather than an invented shape — the
seed file has no `options`/`prompt_te`/`prompt_hi` fields, so this dataclass
does not invent them (data.md: "a node without a source is not a node").

1PL: P(correct) = 1 / (1 + exp(-(theta - band))). Fisher information
I = P(1-P).

`update` is one Fisher-scoring (Newton-Raphson) step per response against a
running precision, not a replay of the full answered history: `AssessState`
stores only `(item_id, correct)` pairs, never each item's `band`, so there is
nothing to replay against. A fixed prior precision `RIDGE` (equivalent to a
Bayesian prior N(0, 1/RIDGE)) stands in for "the score from every prior item
is already zeroed at the current theta" — the standard justification for a
sequential MLE update — and keeps an all-correct run from diverging to +inf.
Every Fisher information term is >= 0, so total precision only grows and SE
is non-increasing *by construction*, not by numerical luck: that is exactly
the invariant `tests/test_assess.py` holds with hypothesis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

RIDGE = 0.5  # prior precision, prior mean 0 — the ridge that stops all-correct from diverging
THETA_MIN, THETA_MAX = -4.0, 4.0
SE_MAX = 1.0 / math.sqrt(RIDGE)


@dataclass(frozen=True)
class Item:
    id: str
    skill_id: str
    band: float
    text: str
    answer: str
    source: str
    rationale: str = ""
    text_te: str = ""
    text_hi: str = ""
    answer_te: str = ""
    answer_hi: str = ""
    rationale_te: str = ""
    rationale_hi: str = ""


@dataclass(frozen=True)
class AssessState:
    theta: float
    se: float
    answered: tuple[tuple[str, bool], ...] = ()


def start(theta0: float = 0.0) -> AssessState:
    """A fresh CAT session at `theta0`, SE at its prior maximum."""
    return AssessState(theta=theta0, se=SE_MAX, answered=())


def _p_correct(theta: float, band: float) -> float:
    return 1.0 / (1.0 + math.exp(-(theta - band)))


def next_item(
    state: AssessState,
    bank: list[Item] | tuple[Item, ...],
    exclude: frozenset[str] = frozenset(),
) -> Item | None:
    """The bank item with max Fisher information at `state.theta`, excluding
    `exclude`. Deterministic: ties break on item id. `None` if nothing is left."""
    candidates = [it for it in bank if it.id not in exclude]
    if not candidates:
        return None

    def info(it: Item) -> float:
        p = _p_correct(state.theta, it.band)
        return p * (1.0 - p)

    return min(candidates, key=lambda it: (-info(it), it.id))


def update(state: AssessState, item: Item, correct: bool) -> AssessState:
    """One Fisher-scoring step incorporating `item`'s response. See module
    docstring for why this needs no history beyond the running (theta, se)."""
    prev_precision = 1.0 / (state.se**2)
    p = _p_correct(state.theta, item.band)
    information = p * (1.0 - p)
    score = (1.0 if correct else 0.0) - p
    new_precision = prev_precision + information

    theta_new = state.theta + score / new_precision
    theta_new = min(max(theta_new, THETA_MIN), THETA_MAX)
    se_new = min(1.0 / math.sqrt(new_precision), SE_MAX)

    return AssessState(theta=theta_new, se=se_new, answered=state.answered + ((item.id, correct),))


def should_stop(state: AssessState, max_items: int = 6, se_target: float = 0.4) -> bool:
    """`max_items` is a hard cap, not a hint — this always returns True once
    `max_items` responses are in, regardless of SE, so the CAT loop always
    terminates."""
    return len(state.answered) >= max_items or state.se < se_target
