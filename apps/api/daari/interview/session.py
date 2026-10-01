"""Anonymous capability sessions, expire after 24h; row locks prevent duplicate turns."""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import text

from daari.config import REPO_ROOT
from daari.db import engine
from daari.intel.corpus import search
from daari.interview.feedback import feedback
from daari.taxonomy_loader import get_taxonomy


def bank(goal: str, locale: str) -> list[dict]:
    taxonomy = get_taxonomy()
    if goal not in taxonomy.roles:
        raise HTTPException(422, "Unknown goal")
    skills = set(taxonomy.roles[goal].required_skills)
    rows = json.loads((REPO_ROOT / "data/interview/bank.json").read_text())
    return [{**row, "text": row.get(f"text_{locale}", row["text"])} for row in rows if skills.intersection(row["skill_ids"])]


async def start(company: str, role: str, goal: str, locale: str, jd: dict | None = None) -> dict:
    practice = bank(goal, locale)
    corpus = await search(company, role)
    chosen = corpus["questions"][:4] if corpus["stats"]["coverage"] == "available" else []
    used = {q["text"] for q in chosen}
    chosen += [q for q in practice if q["text"] not in used][:5-len(chosen)]
    if jd:
        span = jd["source_span"][:300]
        prompts = {"en": "Which experience prepares you for this job requirement?",
                   "te": "ఈ ఉద్యోగ అవసరానికి మీ ఏ అనుభవం ఉపయోగపడుతుంది?",
                   "hi": "इस नौकरी की जरूरत के लिए आपका कौन सा अनुभव उपयोगी है?"}
        chosen = chosen[:4] + [{"id": "live-jd", "text": prompts[locale], "source_span": span,
                               "source_url": jd["source_url"], "fetched_at": jd["fetched_at"],
                               "kind": "jd_practice", "round": "practice", "skill_ids": jd.get("skill_ids", [])}]
    session = {"id": str(uuid4()), "questions": chosen, "attempts": [], "current": 0,
               "company": company, "role": role, "goal": goal, "locale": locale,
               "coverage": corpus["stats"], "jd_status": "anchored" if jd else "not_supplied",
               "expires_at": (datetime.now(UTC) + timedelta(hours=24)).isoformat()}
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM interview_sessions WHERE expires_at <= now()"))
        await conn.execute(text("INSERT INTO interview_sessions(id,payload,expires_at) VALUES (:id,CAST(:body AS jsonb),:expiry)"),
                           {"id": UUID(session["id"]), "body": json.dumps(session), "expiry": datetime.fromisoformat(session["expires_at"])})
    return session


async def history(session_id: UUID) -> dict:
    async with engine.connect() as conn:
        row = (await conn.execute(text("SELECT payload FROM interview_sessions WHERE id=:id AND expires_at > now()"),
                                  {"id": session_id})).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Session missing or expired")
    return row


async def answer(session_id: UUID, question_id: str, transcript: str, duration: float | None) -> dict:
    async with engine.begin() as conn:
        row = (await conn.execute(text("SELECT payload FROM interview_sessions WHERE id=:id AND expires_at > now() FOR UPDATE"),
                                  {"id": session_id})).scalar_one_or_none()
        if row is None:
            raise HTTPException(404, "Session missing or expired")
        if row["current"] >= len(row["questions"]) or row["questions"][row["current"]]["id"] != question_id:
            raise HTTPException(409, "Answer is not for the current question")
        question = row["questions"][row["current"]]
        taxonomy = get_taxonomy()
        keywords = tuple(taxonomy.skills[s].label_en for s in question["skill_ids"] if s in taxonomy.skills)
        result = feedback(transcript, row["locale"], duration, keywords if question["kind"] == "jd_practice" else ())
        row["attempts"].append({"question_id": question_id, "transcript": transcript,
                                "created_at": datetime.now(UTC).isoformat(), **result})
        row["current"] += 1
        await conn.execute(text("UPDATE interview_sessions SET payload=CAST(:body AS jsonb) WHERE id=:id"),
                           {"id": session_id, "body": json.dumps(row)})
    return row


async def delete(session_id: UUID) -> dict:
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM interview_sessions WHERE id=:id"), {"id": session_id})
    return {"deleted": True}
