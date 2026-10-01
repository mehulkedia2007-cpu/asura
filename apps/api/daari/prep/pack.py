"""A pack is computed only from confirmed user fields and dated corpus evidence."""

from dataclasses import asdict
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from daari_core import telemetry
from daari_core.match import Candidate, match
from daari_core.prep import required_path, schedule
from fastapi import HTTPException
from pydantic import BaseModel, Field

from daari.intel.corpus import search
from daari.p2 import _validate_held
from daari.taxonomy_loader import get_taxonomy


class PackArgs(BaseModel):
    confirmed: bool = False
    company: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    interview_date: date
    goal: str = "data_analyst"
    held: dict[str, int] = Field(default_factory=dict)
    hours_per_day: float = Field(default=2, gt=0, le=16, allow_inf_nan=False)
    demand: dict[str, float] = Field(default_factory=dict)
    confirmed_fields: dict[str, str | list[str] | None] = Field(default_factory=dict)


async def build(args: PackArgs) -> dict:
    if not args.confirmed:
        raise HTTPException(422, "Confirm notice fields before building a pack")
    taxonomy = get_taxonomy()
    if args.goal not in taxonomy.roles:
        raise HTTPException(422, "Unknown goal")
    _validate_held(args.held)
    if set(args.demand) - set(taxonomy.skills):
        raise HTTPException(422, "Unknown demand skill")
    corpus = await search(args.company, args.role)
    path = required_path(taxonomy, args.held, args.goal, corpus["stats"]["top_topics"], args.demand)
    try:
        plan = schedule(path, datetime.now(ZoneInfo("Asia/Kolkata")).date(), args.interview_date, args.hours_per_day)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    by_round: dict[str, list] = {}
    for question in sorted(corpus["questions"], key=lambda r: (r["as_of"], r["id"]), reverse=True):
        by_round.setdefault(question["round"], []).append(question)
    required = dict(taxonomy.roles[args.goal].required_skills)
    for skill in corpus["stats"]["top_topics"]:
        if skill in taxonomy.skills:
            required[skill] = max(required.get(skill, 0), taxonomy.skills[skill].level)
    candidate = Candidate(args.goal, taxonomy.roles[args.goal].label_en, args.company, "", required,
                          "taxonomy_and_candidate_reports", "", datetime.now(UTC).isoformat())
    matching = asdict(match(taxonomy, args.held, [candidate])[0])
    telemetry.count("shared", "prep")
    return {"company": corpus["company"], "role": corpus["role"], "coverage": corpus["stats"],
            "plan": plan, "match": matching, "required_skills": required,
            "questions_by_round": by_round, "confirmed_fields": args.confirmed_fields,
            "created_at": datetime.now(UTC).isoformat(), "goal": args.goal,
            "trace": [{"tool": "match_roles"}, {"tool": "required_path"}, {"tool": "schedule"}],
            "mock_seed": {"company": args.company, "role": args.role, "goal": args.goal},
            "export_mode": "on_screen"}
