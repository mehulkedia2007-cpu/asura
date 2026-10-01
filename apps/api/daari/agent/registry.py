"""P2 tool schemas. Later agent loops must call these typed tools."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


class PathArgs(BaseModel):
    persona: Literal["student", "rural"] = "student"
    held: dict[str, int] = Field(default_factory=dict)
    goal: str
    demand: dict[str, float] = Field(default_factory=dict)
    hours_per_week: float = Field(default=10, gt=0)


class LearnArgs(PathArgs):
    skill: str
    level: int = Field(ge=1, le=5)
    se: float = Field(default=0.2, ge=0, lt=1)


class ShockArgs(PathArgs):
    skill: str
    added_listings: int = Field(ge=0)
    total_listings: int = Field(default=100, gt=0)


class MatchArgs(BaseModel):
    held: dict[str, int] = Field(default_factory=dict)
    goal: str
    persona: Literal["student", "rural"] = "student"


class AssessArgs(BaseModel):
    skill: str
    locale: Literal["en", "te", "hi"] = "en"
    theta: float = 0
    se: float | None = None
    answered: list[tuple[str, bool]] = Field(default_factory=list)


@dataclass(frozen=True)
class Tool:
    name: str
    args: type[BaseModel]
    description: str


TOOLS = (
    Tool("get_roadmap", PathArgs, "Calculate a skill path for a goal"),
    Tool("simulate_skill_update", LearnArgs, "Show path and vector change after learning"),
    Tool("market_shock", ShockArgs, "Show path change after listing demand rises"),
    Tool("match_roles", MatchArgs, "Rank a goal role with explained components"),
    Tool("assess_next_item", AssessArgs, "Choose the next Rasch assessment item"),
)


def schemas() -> list[dict]:
    return [
        {"name": tool.name, "description": tool.description, "parameters": tool.args.model_json_schema()}
        for tool in TOOLS
    ]
