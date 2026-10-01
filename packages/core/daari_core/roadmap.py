"""daari_core.roadmap — the cheapest path from what a learner holds to a goal role.

Pure: stdlib only. No I/O, no clock, no randomness (core.md). The caller supplies
the taxonomy and the demand weights; this module never fetches listings.

Ordering is a priority-queue Kahn over the prerequisite subgraph induced by the
*missing* skills, with the queue keyed by `hours / demand[skill]` — the build
plan's demand-weighted edge cost (§7.3). A skill the market wants more of has a
lower key, so it surfaces earlier. Ties break on skill id, so the whole thing is
deterministic for a given (held, goal, demand).

Invariants the tests hold (§7.3, core.md):
  - learning a required skill never lengthens the path;
  - raising demand for a skill never moves that skill later;
  - diff(p, p) is empty.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from daari_core.taxonomy import Taxonomy

# A skill with no live demand signal weighs 1.0 — neutral, not zero, so that
# `hours / demand` stays finite and an absent signal never reorders anything.
NEUTRAL_DEMAND = 1.0

# §7.3 caps the demand multiplier at 2x so an IT-heavy listing feed cannot
# dominate the ordering (D-note: §15 finding 10).
MAX_DEMAND = 2.0


@dataclass(frozen=True)
class Step:
    skill: str
    label_en: str
    label_te: str
    label_hi: str
    hours: float
    level: int
    prereqs: tuple[str, ...]
    why: tuple[str, ...]
    source: str
    demand: float


@dataclass(frozen=True)
class Path:
    goal: str
    goal_label_en: str
    goal_label_te: str
    steps: tuple[Step, ...]
    total_hours: float

    def weeks_at(self, hours_per_week: float) -> float:
        """Calendar length at a given study pace. Raises on a non-positive pace
        rather than returning inf — a caller asking for '0 hours a week' has a
        bug, and a silent inf would render as a real number in the UI."""
        if hours_per_week <= 0:
            raise ValueError("hours_per_week must be positive")
        return self.total_hours / hours_per_week


@dataclass(frozen=True)
class Diff:
    removed: tuple[str, ...]
    added: tuple[str, ...]
    reordered: tuple[str, ...]
    hours_delta: float
    cause: str  # "learner" | "market" | "none"

    def is_empty(self) -> bool:
        return not (self.removed or self.added or self.reordered) and self.hours_delta == 0.0


def _required_level(taxonomy: Taxonomy, skill_id: str, role_requirements: dict[str, int]) -> int:
    """The level this skill must reach: the role's stated level if the role names
    it directly, otherwise the node's own level (a prerequisite is 'done' when it
    reaches the depth the taxonomy assigns it)."""
    if skill_id in role_requirements:
        return role_requirements[skill_id]
    return taxonomy.skills[skill_id].level


def _satisfied(held: dict[str, int], skill_id: str, required_level: int) -> bool:
    return held.get(skill_id, 0) >= required_level


def _closure(taxonomy: Taxonomy, required: list[str]) -> set[str]:
    """Every skill reachable by walking prereq edges up from the required set,
    the required skills themselves included."""
    seen: set[str] = set()
    stack = list(required)
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(taxonomy.skills[node].prereqs)
    return seen


def _clamped_demand(demand: dict[str, float] | None, skill_id: str) -> float:
    if not demand:
        return NEUTRAL_DEMAND
    return min(max(demand.get(skill_id, NEUTRAL_DEMAND), NEUTRAL_DEMAND), MAX_DEMAND)


def _why(
    taxonomy: Taxonomy,
    skill_id: str,
    closure: set[str],
    direct_required: set[str],
    role_label: str,
    demand: dict[str, float] | None,
) -> tuple[str, ...]:
    """A computed reason, never invented copy. Every clause here is derived from
    the graph or the demand table the caller passed in."""
    reasons: list[str] = []
    if skill_id in direct_required:
        reasons.append(f"Required for {role_label}")
    dependents = sorted(m for m in closure if m != skill_id and skill_id in taxonomy.skills[m].prereqs)
    reasons.extend(f"Prerequisite for {taxonomy.skills[m].label_en}" for m in dependents[:2])
    weight = _clamped_demand(demand, skill_id)
    if weight > NEUTRAL_DEMAND:
        reasons.append(f"Demand weight {weight:.2f}x in the current listing window")
    if not reasons:
        reasons.append(f"On the path to {role_label}")
    return tuple(reasons)


def compute(
    taxonomy: Taxonomy,
    held: dict[str, int],
    goal: str,
    demand: dict[str, float] | None = None,
) -> Path:
    """The ordered set of skills between `held` and the `goal` role.

    `held` maps skill id -> the level the learner has reached. `demand` maps
    skill id -> a weight >= 1.0 (see `daari_core.demand`); absent entries weigh
    1.0. Neither is mutated.
    """
    if goal not in taxonomy.roles:
        raise ValueError(f"unknown goal role: {goal!r}")
    role = taxonomy.roles[goal]

    direct_required = set(role.required_skills)
    closure = _closure(taxonomy, list(role.required_skills))
    missing = {
        skill_id
        for skill_id in closure
        if not _satisfied(held, skill_id, _required_level(taxonomy, skill_id, role.required_skills))
    }

    # Kahn over the subgraph induced by `missing`: an already-held prerequisite
    # must not block ordering, so only unmet prereqs count as blocking edges.
    blocking = {n: {p for p in taxonomy.skills[n].prereqs if p in missing} for n in missing}
    unblocks: dict[str, list[str]] = {n: [] for n in missing}
    for node, deps in blocking.items():
        for dep in deps:
            unblocks[dep].append(node)

    def key(skill_id: str) -> tuple[float, str]:
        node = taxonomy.skills[skill_id]
        return (node.hours / _clamped_demand(demand, skill_id), skill_id)

    heap = [key(n) for n, deps in blocking.items() if not deps]
    heapq.heapify(heap)
    pending = {n: len(deps) for n, deps in blocking.items()}
    ordered: list[str] = []
    while heap:
        _, skill_id = heapq.heappop(heap)
        ordered.append(skill_id)
        for dependent in unblocks[skill_id]:
            pending[dependent] -= 1
            if pending[dependent] == 0:
                heapq.heappush(heap, key(dependent))

    if len(ordered) != len(missing):
        raise RuntimeError("cycle detected in the skill graph — data/taxonomy is not a DAG")

    steps = tuple(
        Step(
            skill=skill_id,
            label_en=taxonomy.skills[skill_id].label_en,
            label_te=taxonomy.skills[skill_id].label_te,
            label_hi=taxonomy.skills[skill_id].label_hi,
            hours=taxonomy.skills[skill_id].hours,
            level=_required_level(taxonomy, skill_id, role.required_skills),
            prereqs=taxonomy.skills[skill_id].prereqs,
            why=_why(taxonomy, skill_id, closure, direct_required, role.label_en, demand),
            source=taxonomy.skills[skill_id].source,
            demand=_clamped_demand(demand, skill_id),
        )
        for skill_id in ordered
    )
    return Path(
        goal=goal,
        goal_label_en=role.label_en,
        goal_label_te=role.label_te,
        steps=steps,
        total_hours=sum(s.hours for s in steps),
    )


def diff(before: Path, after: Path, cause: str = "learner") -> Diff:
    """What changed between two paths.

    `reordered` compares the *relative* order of the skills present in both
    paths, so a step is not reported as reordered merely because earlier steps
    disappeared — that is the difference between an honest diff and a noisy one.
    """
    before_ids = [s.skill for s in before.steps]
    after_ids = [s.skill for s in after.steps]
    after_pos = {sid: i for i, sid in enumerate(after_ids)}
    before_pos = {sid: i for i, sid in enumerate(before_ids)}

    removed = tuple(sid for sid in before_ids if sid not in after_pos)
    added = tuple(sid for sid in after_ids if sid not in before_pos)

    common_before = [sid for sid in before_ids if sid in after_pos]
    common_after = sorted(common_before, key=lambda sid: after_pos[sid])
    before_rank = {sid: i for i, sid in enumerate(common_before)}
    after_rank = {sid: i for i, sid in enumerate(common_after)}
    reordered = tuple(sid for sid in common_before if before_rank[sid] != after_rank[sid])

    hours_delta = after.total_hours - before.total_hours
    resolved_cause = cause
    if not (removed or added or reordered) and hours_delta == 0.0:
        resolved_cause = "none"
    return Diff(
        removed=removed,
        added=added,
        reordered=reordered,
        hours_delta=hours_delta,
        cause=resolved_cause,
    )
