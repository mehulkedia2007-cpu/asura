"""P5 typed tools: corpus, confirmed prep, and anonymous interview practice."""

import base64
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from daari import leads
from daari.intel import corpus
from daari.intel.fetchers import refresh
from daari.interview import session
from daari.interview.feedback import feedback
from daari.interview.guard import guarded_draft
from daari.p2 import _validate_held
from daari.prep.notice import extract
from daari.prep.pack import PackArgs, build
from daari.voice.asr import transcribe

router = APIRouter(prefix="/engine", tags=["P5 interview intelligence"])
Locale = Literal["en", "te", "hi"]


class QuestionsArgs(BaseModel):
    company: str = Field(max_length=100)
    role: str = Field(max_length=100)
    query: str = Field(default="", max_length=100)
    round: str = Field(default="", max_length=30)
    year: int | None = Field(default=None, ge=2000, le=2100)


class NoticeArgs(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class StartArgs(BaseModel):
    company: str = Field(default="", max_length=100)
    role: str = Field(default="", max_length=100)
    goal: str = "data_analyst"
    locale: Locale = "en"
    job_query: str | None = Field(default=None, max_length=100)
    place: str = Field(default="Guntur", max_length=100)
    held: dict[str, int] = Field(default_factory=dict)


class FeedbackArgs(BaseModel):
    use_model: bool = False
    transcript: str = Field(min_length=1, max_length=12000, pattern=r"\S")
    locale: Locale = "en"
    duration_seconds: float | None = Field(default=None, gt=0, le=1800, allow_inf_nan=False)
    keywords: list[str] = Field(default_factory=list, max_length=30)


class AnswerArgs(FeedbackArgs):
    session_id: UUID
    question_id: str = Field(max_length=150)


class SessionArgs(BaseModel):
    session_id: UUID


class AudioArgs(BaseModel):
    audio: str = Field(default="", max_length=6_000_000)
    browser_final: str = Field(default="", max_length=12000)
    mime: Literal["audio/webm", "audio/mp4", "audio/wav", "audio/mpeg"] = "audio/webm"
    locale: Locale = "en"


@router.get("/questions/companies")
def companies() -> dict:
    return {"companies": corpus.companies(), "scope": "general_seed_not_verified_college_recruiters"}


@router.post("/questions/search")
async def get_company_questions(args: QuestionsArgs) -> dict:
    return await corpus.search(args.company, args.role, args.query, args.round, args.year)


@router.post("/questions/refresh")
async def refresh_questions(args: QuestionsArgs) -> dict:
    return {"refresh": await refresh(args.company, args.role),
            **await get_company_questions(args)}


@router.post("/prep/notice")
def notice(args: NoticeArgs) -> dict:
    return extract(args.text)


@router.post("/prep/pack")
async def build_prep_pack(args: PackArgs) -> dict:
    return await build(args)


@router.post("/interview/start")
async def start_interview(args: StartArgs) -> dict:
    _validate_held(args.held)
    session.bank(args.goal, args.locale)
    jd = None
    if args.job_query:
        result = await leads.search(args.job_query, args.place, args.held)
        safe = [row for row in result.get("leads", []) if row.get("scam", {}).get("score", 1) < .5]
        if safe:
            lead = safe[0]
            jd = {"source_url": lead["source_url"], "fetched_at": lead["fetched_at"],
                  "source_span": lead.get("description") or lead["title"],
                  "skill_ids": list(lead.get("required_skills", {}))}
    return await session.start(args.company, args.role, args.goal, args.locale, jd)


@router.post("/interview/feedback")
async def interview_feedback(args: FeedbackArgs) -> dict:
    result = feedback(args.transcript, args.locale, args.duration_seconds, tuple(args.keywords))
    if args.use_model:
        result["feedback"], result["mode"] = await guarded_draft(args.transcript, result["feedback"])
    return result


@router.post("/interview/answer")
async def answer(args: AnswerArgs) -> dict:
    return await session.answer(args.session_id, args.question_id, args.transcript, args.duration_seconds)


@router.post("/interview/history")
async def history(args: SessionArgs) -> dict:
    return await session.history(args.session_id)


@router.post("/interview/delete")
async def delete(args: SessionArgs) -> dict:
    return await session.delete(args.session_id)


@router.post("/interview/transcribe")
async def audio(args: AudioArgs) -> dict:
    try:
        decoded = base64.b64decode(args.audio, validate=True)
    except ValueError as exc:
        raise HTTPException(422, "Invalid audio") from exc
    text, provider = await transcribe(decoded, args.mime, args.locale, args.browser_final)
    return {"transcript": text, "provider": provider, "confirmation_required": True}
