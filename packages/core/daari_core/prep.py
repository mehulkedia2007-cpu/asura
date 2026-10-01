"""Pure placement planning: shared roadmap, prerequisite-safe daily allocation."""

import math
from dataclasses import asdict, replace
from datetime import date, timedelta

from daari_core.roadmap import Path, compute
from daari_core.taxonomy import Taxonomy


def required_path(taxonomy: Taxonomy, held: dict[str, int], goal: str,
                  topic_frequency: dict[str, int], demand: dict[str, float]) -> Path:
    role = taxonomy.roles[goal]
    required = dict(role.required_skills)
    for skill, frequency in topic_frequency.items():
        if skill in taxonomy.skills and frequency > 0:
            required[skill] = max(required.get(skill, 0), taxonomy.skills[skill].level)
    augmented = Taxonomy(taxonomy.skills, {**taxonomy.roles, goal: replace(role, required_skills=required)})
    maximum = max(topic_frequency.values(), default=1) or 1
    weights = {skill: min(2.0, max(1.0, demand.get(skill, 1.0)) + topic_frequency.get(skill, 0) / maximum)
               for skill in taxonomy.skills}
    return compute(augmented, held, goal, weights)


def schedule(path: Path, start: date, interview_date: date, hours_per_day: float) -> dict:
    if not math.isfinite(hours_per_day) or not 0 < hours_per_day <= 16:
        raise ValueError("hours_per_day must be in (0, 16]")
    days = (interview_date - start).days
    if days < 0 or days > 366:
        raise ValueError("interview date must be within the next 366 days")
    rows: list[dict] = []
    remaining = {step.skill: step.hours for step in path.steps}
    index = 0
    for offset in range(days):
        available = hours_per_day
        allocations = []
        while available > 1e-8 and index < len(path.steps):
            step = path.steps[index]
            hours = min(available, remaining[step.skill])
            if hours > 0:
                allocations.append({"skill": step.skill, "hours": round(hours, 4),
                                    "label_en": step.label_en, "label_te": step.label_te, "label_hi": step.label_hi})
            remaining[step.skill] -= hours
            available -= hours
            if remaining[step.skill] <= 1e-8:
                index += 1
        if allocations:
            rows.append({"date": (start + timedelta(days=offset)).isoformat(), "allocations": allocations})
    unscheduled = [{"skill": skill, "hours": round(hours, 4)} for skill, hours in remaining.items() if hours > 1e-8]
    return {"start_date": start.isoformat(), "interview_date": interview_date.isoformat(),
            "available_days": days, "hours_per_day": hours_per_day, "required_hours": path.total_hours,
            "capacity_hours": days * hours_per_day, "shortfall_hours": round(sum(r["hours"] for r in unscheduled), 4),
            "feasible": not unscheduled, "days": rows, "unscheduled": unscheduled,
            "roadmap": asdict(path)}
