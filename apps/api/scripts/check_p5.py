"""Local DB integration: ordered answers, capability history, expiry and deletion."""
import asyncio
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text

from daari.db import engine
from daari.interview import session


async def main() -> None:
    ids = []
    try:
        first = await session.start("tcs", "Prime", "data_analyst", "en")
        sid = UUID(first["id"])
        ids.append(sid)
        assert len(first["questions"]) == 5
        question = first["questions"][0]["id"]
        answers = await asyncio.gather(
            session.answer(sid, question, "I built a report.", 30),
            session.answer(sid, question, "I built a report.", 30), return_exceptions=True)
        assert sum(isinstance(row, HTTPException) and row.status_code == 409 for row in answers) == 1
        saved = await session.history(sid)
        assert len(saved["attempts"]) == 1 and saved["current"] == 1
        other = await session.start("unknown", "none", "delivery_executive", "te")
        other_id = UUID(other["id"])
        ids.append(other_id)
        assert other["coverage"]["coverage"] == "none"
        assert all(q["kind"] == "practice" for q in other["questions"])
        assert not (await session.history(other_id))["attempts"]
        async with engine.begin() as conn:
            await conn.execute(text("UPDATE interview_sessions SET expires_at=now()-interval '1 second' WHERE id=:id"), {"id": sid})
        try:
            await session.history(sid)
            raise AssertionError("expired session readable")
        except HTTPException as exc:
            assert exc.status_code == 404
        await session.delete(other_id)
        try:
            await session.history(other_id)
            raise AssertionError("deleted session readable")
        except HTTPException as exc:
            assert exc.status_code == 404
        print("P5 DB integration passed: concurrent answer conflict, history isolation, expiry, deletion")
    finally:
        for sid in ids:
            await session.delete(sid)
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
