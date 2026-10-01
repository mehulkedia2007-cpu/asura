"""Fail-closed sentence gate for free prose before rendering or speech.

This first verifier accepts verbatim source-backed sentences. A future semantic
verifier may accept paraphrases, but it must never relax numeric/date checks.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime

_FORBIDDEN = re.compile(
    r"\b(?:guaranteed (?:job|placement|selection)|pay (?:a |the )?(?:fee|deposit) to apply)\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"(?<!\w)\d+(?:[.,]\d+)*(?!\w)")


@dataclass(frozen=True)
class Evidence:
    id: str
    text: str
    source_url: str
    fetched_at: datetime
    as_of: date | None = None


def _sentences(draft: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?।])\s+|\n+", draft) if part.strip()]


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split()).strip(" .!?।")


def verify(draft: str, evidence: list[Evidence], searched: str = "the available sources") -> dict:
    valid = [item for item in evidence if item.source_url.startswith("https://") and item.fetched_at]
    accepted: list[dict] = []
    struck: list[dict] = []
    for sentence in _sentences(draft):
        reason = None
        if _FORBIDDEN.search(sentence):
            reason = "forbidden_claim"
        matching = [item for item in valid if _normalized(sentence) in _normalized(item.text)]
        if not matching and reason is None:
            reason = "unsupported"
        elif matching and reason is None:
            # Exact span support is stricter than number/entity matching, but keep
            # these explicit checks so a later paraphrase layer cannot bypass them.
            numbers = _NUMBER.findall(sentence)
            if not any(all(number in _NUMBER.findall(item.text) for number in numbers) for item in matching):
                reason = "numeric_mismatch"
        if reason:
            struck.append({"text": sentence, "reason": reason})
        else:
            accepted.append({"text": sentence, "citation_ids": [item.id for item in matching]})
    if accepted:
        latest = max(item.fetched_at for item in valid if item.id in {id for row in accepted for id in row["citation_ids"]})
        return {"sentences": accepted, "struck": struck, "no_data": False,
                "newest_evidence_at": latest.isoformat()}
    latest = max((item.fetched_at for item in valid), default=None)
    return {"sentences": [], "struck": struck, "no_data": True,
            "message": f"No verified answer from {searched}. Check the linked source directly.",
            "newest_evidence_at": latest.isoformat() if latest else None}
