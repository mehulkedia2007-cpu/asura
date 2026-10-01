"""Fail closed: quote presence alone cannot establish a feedback claim."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from daari.agent.llm import complete


class Feedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    point: str = Field(min_length=1, max_length=300)
    quote: str = Field(min_length=1, max_length=240)
    fix: str = Field(min_length=1, max_length=400)
    severity: Literal["info", "practice"]
    source: Literal["text", "prosody"] = "text"
    code: str


FORBIDDEN = re.compile(r"guarantee|will (?:be hired|get selected)|better than|top \d|excellent|perfect|amazing|brilliant|ఖచ్చితంగా ఉద్యోగం|नौकरी पक्की", re.IGNORECASE)


def validate(items: list[dict], transcript: str, allowed: list[dict]) -> list[dict]:
    checked = []
    allowed_by_code = {row["code"]: row for row in allowed}
    for raw in items:
        try:
            row = Feedback.model_validate(raw).model_dump()
        except ValidationError:
            continue
        if not row["quote"].strip() or row["quote"] not in transcript or FORBIDDEN.search(row["point"] + " " + row["fix"]):
            continue
        # Only computed findings are admissible; a model cannot attach a real
        # quote to an unrelated claim. Final wording is the reviewed template.
        expected = allowed_by_code.get(row["code"])
        if expected and row["source"] == expected["source"]:
            checked.append({**expected, "quote": row["quote"]})
    return list({row["code"]: row for row in checked}.values())[:6]


async def guarded_draft(transcript: str, allowed: list[dict]) -> tuple[list[dict], str]:
    import json
    messages = [{"role": "system", "content": "Return JSON {items:[...]} with 3 to 6 feedback items. "
                 "Use only supplied computed feedback codes and quote verbatim from the transcript. Never praise or predict hiring."},
                {"role": "user", "content": json.dumps({"transcript": transcript, "computed": allowed}, ensure_ascii=False)}]
    for attempt in range(2):
        result, _, _ = await complete(messages, [])
        if result:
            try:
                body = json.loads(result.get("content") or "{}")
                items = body.get("items", [])
                valid = validate(items, transcript, allowed)
                if 3 <= len(valid) <= 6 and len(valid) == len(items):
                    return valid, "guarded_model" if attempt == 0 else "guarded_rewrite"
            except (ValueError, TypeError, AttributeError):
                pass
        messages.append({"role": "user", "content": "Rewrite once with exactly the computed findings and valid verbatim quotes."})
    return validate(allowed, transcript, allowed), "metrics_template"
