"""Stateless P2 engine API. Profiles and CAT state are supplied by the caller."""

from dataclasses import asdict
from uuid import UUID

import numpy as np
from daari_core import assess, profile, telemetry
from daari_core.graph import build as build_graph
from daari_core.match import Candidate, match
from daari_core.roadmap import diff
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from daari.agent.registry import (
    AssessArgs,
    LearnArgs,
    MatchArgs,
    PathArgs,
    ShockArgs,
    schemas,
)
from daari.embeddings import get_embeddings
from daari.items_loader import get_item_bank
from daari.personas import rural, student
from daari.taxonomy_loader import get_taxonomy
from daari.vector_store import save_profile

router = APIRouter(prefix="/engine", tags=["P2 engine"])


class ProfileSaveArgs(BaseModel):
    profile_id: UUID
    held: dict[str, int]
    se: dict[str, float] = Field(default_factory=dict)


def _validate_held(held: dict[str, int]) -> None:
    unknown = set(held) - set(get_taxonomy().skills)
    if unknown:
        raise HTTPException(422, f"Unknown skills: {sorted(unknown)}")
    if any(not 1 <= level <= 5 for level in held.values()):
        raise HTTPException(422, "Skill levels must be 1–5")


def _path(args: PathArgs):
    _validate_held(args.held)
    taxonomy = get_taxonomy()
    if args.goal not in taxonomy.roles:
        raise HTTPException(422, f"Unknown goal: {args.goal}")
    if set(args.demand) - set(taxonomy.skills):
        raise HTTPException(422, "Demand references an unknown skill")
    adapter = student if args.persona == "student" else rural
    telemetry.count(args.persona, "roadmap")
    return adapter.get_path(taxonomy, args.held, args.goal, args.demand)


def _path_data(path, hours_per_week: float) -> dict:
    return {**asdict(path), "weeks": round(path.weeks_at(hours_per_week), 2)}


def _vector_data(
    before: dict[str, int], after: dict[str, int], goal: str,
    updated_skill: str, updated_se: float,
) -> dict:
    embeddings = get_embeddings()
    taxonomy = get_taxonomy()
    target = np.mean([embeddings[s] for s in taxonomy.roles[goal].required_skills], axis=0)
    result: dict = {"before_version": None, "after_version": None, "cosine_shift": None}
    if before:
        old, old_version = profile.vector({s: (v, 0.2) for s, v in before.items()}, embeddings)
        result["before_version"] = old_version
    else:
        old = None
    if after:
        new, new_version = profile.vector(
            {s: (v, updated_se if s == updated_skill else 0.2) for s, v in after.items()},
            embeddings,
        )
        result["after_version"] = new_version
        if old is not None:
            result["cosine_shift"] = round(profile.cosine_shift(old, new, target), 4)
    return result


@router.get("/catalog")
def catalog() -> dict:
    taxonomy = get_taxonomy()
    return {
        "skills": [asdict(s) for s in taxonomy.skills.values()],
        "roles": [asdict(r) for r in taxonomy.roles.values()],
        "tools": schemas(),
        "embedding_kind": "prerequisite-feature-seed",
    }


@router.post("/profile")
async def store_profile(args: ProfileSaveArgs) -> dict:
    _validate_held(args.held)
    if not args.held:
        raise HTTPException(422, "A profile vector requires a held skill")
    if set(args.se) - set(args.held) or any(not 0 <= value < 1 for value in args.se.values()):
        raise HTTPException(422, "Uncertainty must be between 0 and 1 for a held skill")
    version = await save_profile(str(args.profile_id), args.held, args.se)
    return {"profile_id": str(args.profile_id), "vector_version": version}


@router.post("/roadmap")
def roadmap(args: PathArgs) -> dict:
    return _path_data(_path(args), args.hours_per_week)


@router.post("/simulate-skill-update")
def simulate(args: LearnArgs) -> dict:
    taxonomy = get_taxonomy()
    if args.skill not in taxonomy.skills:
        raise HTTPException(422, f"Unknown skill: {args.skill}")
    before = _path(args)
    updated = dict(args.held)
    updated[args.skill] = max(updated.get(args.skill, 0), args.level)
    after = _path(args.model_copy(update={"held": updated}))
    return {
        "before": _path_data(before, args.hours_per_week),
        "after": _path_data(after, args.hours_per_week),
        "diff": asdict(diff(before, after, "learner")),
        "profile_vector": _vector_data(args.held, updated, args.goal, args.skill, args.se),
        "held_after": updated,
    }


@router.post("/market-shock")
def market_shock(args: ShockArgs) -> dict:
    if args.skill not in get_taxonomy().skills:
        raise HTTPException(422, f"Unknown skill: {args.skill}")
    before = _path(args)
    # One listing contributes once to skill share; a shock adds N relevant
    # listings to the observed window, capped by the same 2x demand bound.
    import math

    demand = dict(args.demand)
    share = args.added_listings / (args.total_listings + args.added_listings)
    demand[args.skill] = min(2.0, max(demand.get(args.skill, 1.0), 1.0 + math.log1p(10 * share)))
    after = _path(args.model_copy(update={"demand": demand}))
    return {
        "before": _path_data(before, args.hours_per_week),
        "after": _path_data(after, args.hours_per_week),
        "diff": asdict(diff(before, after, "market")),
        "demand_after": demand,
    }


@router.post("/match")
def match_role(args: MatchArgs) -> dict:
    _validate_held(args.held)
    taxonomy = get_taxonomy()
    if args.goal not in taxonomy.roles:
        raise HTTPException(422, f"Unknown goal: {args.goal}")
    role = taxonomy.roles[args.goal]
    candidate = Candidate(
        id=role.id, title=role.label_en, org="DAARI role taxonomy", location="",
        required_skills=role.required_skills, source=role.source,
        source_url=role.source, fetched_at="taxonomy-seed",
    )
    telemetry.count(args.persona, "match")
    embeddings = get_embeddings()
    result = match(taxonomy, args.held, [candidate], graph=build_graph(taxonomy, embeddings), embeddings=embeddings)[0]
    return asdict(result)


class AnswerArgs(AssessArgs):
    item_id: str
    answer: str


def _item_payload(item: assess.Item | None, locale: str) -> dict | None:
    if item is None:
        return None
    # English-language skill questions intentionally remain in English. For
    # other skills, never silently present an untranslated prompt as localized.
    requested = locale if item.skill_id != "spoken_english" else "en"
    text = getattr(item, f"text_{requested}", "") if requested != "en" else item.text
    return {
        "id": item.id,
        "text": text or item.text,
        "source": item.source,
        "display_language": requested if text or requested == "en" else "en",
    }


def _state(args: AssessArgs) -> assess.AssessState:
    if args.skill not in get_taxonomy().skills:
        raise HTTPException(422, f"Unknown skill: {args.skill}")
    return assess.AssessState(
        theta=args.theta,
        se=args.se if args.se is not None else assess.SE_MAX,
        answered=tuple((item_id, correct) for item_id, correct in args.answered),
    )


@router.post("/assess/next")
def assess_next(args: AssessArgs) -> dict:
    state = _state(args)
    bank = [item for item in get_item_bank() if item.skill_id == args.skill]
    item = None if assess.should_stop(state) else assess.next_item(
        state, bank, frozenset(item_id for item_id, _ in state.answered)
    )
    return {
        "state": asdict(state), "done": item is None,
        "item": _item_payload(item, args.locale),
    }


@router.post("/assess/answer")
def assess_answer(args: AnswerArgs) -> dict:
    state = _state(args)
    bank = [item for item in get_item_bank() if item.skill_id == args.skill]
    expected = None if assess.should_stop(state) else assess.next_item(
        state, bank, frozenset(item_id for item_id, _ in state.answered)
    )
    if expected is None or expected.id != args.item_id:
        raise HTTPException(422, "Item is not the current assessment question")
    localized_answer = (
        getattr(expected, f"answer_{args.locale}", "") if args.locale != "en" else ""
    )
    accepted_answers = {expected.answer.strip().casefold()}
    if localized_answer.strip():
        accepted_answers.add(localized_answer.strip().casefold())
    correct = args.answer.strip().casefold() in accepted_answers
    updated = assess.update(state, expected, correct)
    telemetry.count("shared", "assess")
    localized_rationale = (
        getattr(expected, f"rationale_{args.locale}", "") if args.locale != "en" else ""
    )
    return {
        "state": asdict(updated), "correct": correct,
        "rationale": localized_rationale or expected.rationale,
        "expected_answer": localized_answer or expected.answer,
        "done": assess.should_stop(updated) or len(updated.answered) >= len(bank),
        "level": max(1, min(5, round(updated.theta + 3))), "se": updated.se,
    }
