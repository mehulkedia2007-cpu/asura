"""Conservative, cached eligibility extraction from government source text."""

import json
import re
from typing import Any

import httpx
from daari_core.eligibility import FIELDS, OPS

from daari.config import settings
from daari.source_cache import read, write


def validate(raw: Any, text: str) -> tuple[dict, bool]:
    """Reject unsupported fields, operators and snippets, and incomplete coverage."""
    if not isinstance(raw, dict):
        return {"all": [], "any": []}, False
    rules: dict[str, list[dict]] = {"all": [], "any": []}
    for group in ("all", "any"):
        candidates = raw.get(group, [])
        if not isinstance(candidates, list):
            return {"all": [], "any": []}, False
        for rule in candidates:
            if not isinstance(rule, dict) or rule.get("field") not in FIELDS or rule.get("op") not in OPS:
                return {"all": [], "any": []}, False
            snippet = rule.get("snippet")
            if not isinstance(snippet, str) or snippet.strip() not in text or "value" not in rule:
                return {"all": [], "any": []}, False
            if rule["op"] == "in" and not isinstance(rule["value"], list):
                return {"all": [], "any": []}, False
            if rule["op"] in {"lte", "gte"}:
                value = rule["value"]
                if not isinstance(value, (int, float, str)):
                    return {"all": [], "any": []}, False
                try:
                    float(value)
                except (TypeError, ValueError):
                    return {"all": [], "any": []}, False
                if re.sub(r"\D", "", str(value)) not in re.sub(r"\D", "", snippet):
                    return {"all": [], "any": []}, False
            elif rule["op"] in {"eq", "ne", "in"}:
                values = rule["value"] if rule["op"] == "in" else [rule["value"]]
                if any(not isinstance(value, str) or value.casefold() not in snippet.casefold()
                       for value in values):
                    return {"all": [], "any": []}, False
            rules[group].append({"field": rule["field"], "op": rule["op"],
                                 "value": rule["value"], "snippet": snippet.strip()})
    if not (rules["all"] or rules["any"]):
        return rules, False
    # A model cannot declare coverage complete while leaving a listed condition
    # without a source span. Headings and empty lines do not impose conditions.
    clauses = [re.sub(r"^\s*(?:\d+[.)]|[-*+>])\s*", "", line).strip(" *#")
               for line in text.splitlines()]
    clauses = [line for line in clauses if len(line) >= 18 and not line.endswith(":")]
    spans = [item["snippet"] for group in rules.values() for item in group]
    covered = all(any(line in span or span in line for span in spans) for line in clauses)
    return rules, bool(raw.get("complete") is True and covered)


async def extract(scheme_id: str, content_hash: str, eligibility_text: str) -> tuple[dict, bool, str | None]:
    key = f"scheme-rules:{scheme_id}:{content_hash}"
    cached = await read(key)
    if cached:
        payload = cached["payload"]
        return payload["rules"], payload["complete"], None
    if not settings.GEMINI_API_KEY or not eligibility_text.strip():
        return {"all": [], "any": []}, False, "no_model_or_text"
    prompt = (
        "Extract only eligibility conditions explicitly stated in the source below. "
        "Return JSON with keys all, any, complete. Each rule has field, op, value, snippet. "
        f"Allowed fields: {', '.join(sorted(FIELDS))}. Allowed ops: {', '.join(sorted(OPS))}. "
        "Copy each snippet exactly from the source. Use all for required conditions, any only for alternatives. "
        "Set complete=false if a condition cannot be represented, is ambiguous, or source text has multiple beneficiary groups. "
        "Do not infer a person's eligibility. Do not use outside knowledge.\n\nSOURCE:\n"
        + eligibility_text[:12000]
    )
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent",
                headers={"x-goog-api-key": settings.GEMINI_API_KEY},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}},
            )
            response.raise_for_status()
            body = response.json()
        answer = body["candidates"][0]["content"]["parts"][0]["text"]
        rules, complete = validate(json.loads(answer), eligibility_text)
        await write(key, "scheme_rules", {"rules": rules, "complete": complete})
        return rules, complete, None
    except httpx.HTTPStatusError as exc:
        return {"all": [], "any": []}, False, f"http_{exc.response.status_code}"
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        # Never log the request URL, headers, or response body: keys and source
        # text may be present. A caller falls back to unknown eligibility.
        return {"all": [], "any": []}, False, type(exc).__name__
