"""Optional source-quoted second opinion for ambiguous lead risk signals."""

import hashlib
import json
import re

import httpx

from daari.config import settings
from daari.source_cache import read, write


def validate(payload: dict, source_text: str) -> tuple[float, str | None]:
    if payload.get("risky") is not True:
        return 0.0, None
    quote = payload.get("quote")
    reason = payload.get("reason")
    if (not isinstance(quote, str) or len(quote.split()) < 3 or
            quote.strip() not in source_text or
            reason not in {"Payment pressure", "Off-platform contact", "Unverified guarantee"}):
        return 0.0, None
    if re.search(r"\b(?:no|never|without|do not|don't)\b.{0,35}\b(?:fee|deposit|payment|pay|charge)\b",
                 quote, re.IGNORECASE):
        return 0.0, None
    return 0.2, f"{reason.strip()} — “{quote.strip()}”"


async def second_opinion(description: str, contact: str = "") -> tuple[float, str | None, str | None]:
    text = f"{description}\n{contact}".strip()[:3500]
    if not text or not settings.GEMINI_API_KEY:
        return 0.0, None, None
    digest = hashlib.sha256(text.encode()).hexdigest()
    cached = await read(f"scam-llm:{digest}")
    if cached:
        result = cached["payload"]
        return result["delta"], result["reason"], None
    prompt = (
        "Assess only whether this job listing explicitly pressures an applicant to pay, "
        "move contact exclusively off-platform, or accept an implausible guarantee. "
        "Return JSON {risky:boolean, quote:string, reason:string}. The reason must be exactly "
        "Payment pressure, Off-platform contact, or Unverified guarantee. Quote an exact span "
        "from the listing. Do not mark a warning against scams or a no-fee statement risky. "
        "Do not use outside facts.\nLISTING:\n" + text
    )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent",
                headers={"x-goog-api-key": settings.GEMINI_API_KEY},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}},
            )
            response.raise_for_status()
            answer = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        delta, reason = validate(json.loads(answer), text)
        await write(f"scam-llm:{digest}", "scam_llm", {"delta": delta, "reason": reason})
        return delta, reason, None
    except httpx.HTTPStatusError as exc:
        return 0.0, None, f"http_{exc.response.status_code}"
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        return 0.0, None, "unavailable"
