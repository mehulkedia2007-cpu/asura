"""P3 live-source API. All displayed records carry a URL and fetch stamp."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from daari import leads, schemes
from daari.portal_sources import probe_all
from daari.scheme_index import browse, coverage
from daari.taxonomy_loader import get_taxonomy

router = APIRouter(prefix="/engine", tags=["P3 live data"])


class LeadSearch(BaseModel):
    query: str = Field(min_length=1, max_length=100)
    place: str = Field(min_length=1, max_length=150)
    held: dict[str, int] = Field(default_factory=dict)
    refresh: bool = False
    since: datetime | None = None
    include_remote: bool = False
    job_type: Literal["local", "government"] = "local"


class SchemeSearch(BaseModel):
    query: str = Field(min_length=1, max_length=100)
    profile: dict = Field(default_factory=dict)
    refresh: bool = False
    locale: Literal["en", "te", "hi"] = "en"
    scheme_id: str | None = Field(default=None, max_length=150)


@router.post("/leads/search")
async def search_leads(args: LeadSearch) -> dict:
    try:
        if set(args.held) - set(get_taxonomy().skills):
            raise ValueError("held references an unknown skill")
        if any(not 1 <= level <= 5 for level in args.held.values()):
            raise ValueError("skill levels must be 1–5")
        if args.job_type == "government":
            from daari.government_jobs import search
            return await search(args.query, args.place, args.refresh)
        return await leads.search(args.query, args.place, args.held, args.refresh, args.since, args.include_remote)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/schemes/search")
async def search_schemes(args: SchemeSearch) -> dict:
    try:
        if not args.refresh:
            saved = await schemes.search_saved(args.query, args.profile, args.scheme_id)
            if saved is not None:
                return saved
        refreshed = await schemes.search(args.query, args.profile, args.refresh, args.locale)
        if args.scheme_id:
            selected = await schemes.search_saved(args.query, args.profile, args.scheme_id)
            if selected is not None:
                selected["source_errors"] = refreshed["source_errors"]
                return selected
        return refreshed
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/schemes/options")
async def scheme_options() -> dict:
    return {"schemes": [{key: r.get(key) for key in ("id", "name_en", "name_te", "state", "url", "fetched_at")}
                        for r in await browse()]}


@router.get("/schemes/coverage")
async def scheme_coverage() -> dict:
    return await coverage()


@router.get("/schemes/sources")
async def scheme_sources(refresh: bool = False) -> dict:
    return {"sources": await probe_all(refresh)}
