"""P3 live-source API. All displayed records carry a URL and fetch stamp."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from daari import leads, schemes
from daari.portal_sources import probe_all
from daari.scheme_index import coverage
from daari.taxonomy_loader import get_taxonomy

router = APIRouter(prefix="/engine", tags=["P3 live data"])


class LeadSearch(BaseModel):
    query: str = Field(min_length=1, max_length=100)
    place: str = Field(min_length=1, max_length=150)
    held: dict[str, int] = Field(default_factory=dict)
    refresh: bool = False
    since: datetime | None = None


class SchemeSearch(BaseModel):
    query: str = Field(min_length=1, max_length=100)
    profile: dict = Field(default_factory=dict)
    refresh: bool = False
    locale: Literal["en", "te", "hi"] = "en"


@router.post("/leads/search")
async def search_leads(args: LeadSearch) -> dict:
    try:
        if set(args.held) - set(get_taxonomy().skills):
            raise ValueError("held references an unknown skill")
        if any(not 1 <= level <= 5 for level in args.held.values()):
            raise ValueError("skill levels must be 1–5")
        return await leads.search(args.query, args.place, args.held, args.refresh, args.since)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/schemes/search")
async def search_schemes(args: SchemeSearch) -> dict:
    try:
        return await schemes.search(args.query, args.profile, args.refresh, args.locale)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/schemes/coverage")
async def scheme_coverage() -> dict:
    return await coverage()


@router.get("/schemes/sources")
async def scheme_sources(refresh: bool = False) -> dict:
    return {"sources": await probe_all(refresh)}
