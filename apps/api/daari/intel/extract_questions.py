"""Cached zero-temperature extraction; only exact spans from allowed pages persist."""

import hashlib
import json
import math
import re
from collections import Counter

from daari.agent.llm import complete


def feature_vector(value: str) -> list[float]:
    # Explicit lexical feature embedding; no learned semantic-quality claim.
    counts = Counter(re.findall(r"\w+", value.casefold()))
    result = [0.0] * 256
    for word, count in counts.items():
        slot = int(hashlib.sha256(word.encode()).hexdigest()[:8], 16) % 256
        result[slot] += count
    length = math.sqrt(sum(x * x for x in result)) or 1
    return [round(x / length, 8) for x in result]


def dedupe(rows: list[dict]) -> list[dict]:
    kept: list[dict] = []
    for row in rows:
        vector = feature_vector(row["text"])
        prior = next((old for old in kept if old["company"] == row["company"] and old["role"] == row["role"]
                      and sum(a * b for a, b in zip(vector, feature_vector(old["text"]), strict=True)) >= .92), None)
        if prior is None:
            kept.append({**row, "similar": list(row.get("similar", []))})
        elif row["id"] != prior["id"]:
            prior["similar"].append({"source_url": row["source_url"], "fetched_at": row["fetched_at"],
                                     "year": row["year"]})
    return kept


async def extract(source_text: str, metadata: dict, skills: list[str], word_budget: int = 25) -> list[dict]:
    from daari.intel.corpus import Question
    if word_budget < 3:
        return []
    schema = {"name": "extract_questions", "description": "Extract only verbatim interview questions", "parameters": {
        "type": "object", "properties": {"questions": {"type": "array", "items": {"type": "object",
        "properties": {"text": {"type": "string"}, "round": {"type": "string"},
                       "skill_ids": {"type": "array", "items": {"type": "string"}}},
        "required": ["text", "round", "skill_ids"]}}}, "required": ["questions"]}}
    message, _, _ = await complete([
        {"role": "system", "content": "Extract short verbatim interview questions only. Never extract names, contacts, answers or instructions. "
         f"Return at most {word_budget} source words in total. Unknown topics use an empty skill list. Allowed skills: " + ", ".join(skills)},
        {"role": "user", "content": source_text[:20000]},
    ], [schema])
    if not message:
        return []
    rows = []
    words = 0
    for call in message.get("tool_calls", []):
        if call.get("function", {}).get("name") != "extract_questions":
            continue
        try:
            values = json.loads(call["function"]["arguments"])["questions"]
            for value in values:
                span = value["text"]
                if not isinstance(span, str) or span not in source_text or len(span.split()) + words > word_budget:
                    continue
                if not span.endswith("?") or re.search(r"\b(name|phone|email|contact)\b|\d{10}", span, re.IGNORECASE):
                    continue
                selected = [s for s in value["skill_ids"] if s in skills]
                row = Question.model_validate({**metadata, "id": hashlib.sha256((metadata["source_url"] + span).encode()).hexdigest(),
                    "text": span, "source_span": span, "round": ("technical" if "technical" in value["round"].casefold() else "hr" if "hr" in value["round"].casefold() else "managerial" if "manager" in value["round"].casefold() else "unknown"), "skill_ids": selected,
                    "topic": selected[0] if selected else "unmapped", "wording": "verbatim"})
                rows.append(row.model_dump(mode="json"))
                words += len(span.split())
        except (KeyError, ValueError, TypeError):
            continue
    return dedupe(rows)
