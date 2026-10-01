"""Deterministic transcript indicators, not an assessment of personality or ability."""

import math
import re

STAR = {
    "situation": ("project", "team", "when", "ప్రాజెక్ట్", "బృందం", "परियोजना", "टीम"),
    "task": ("task", "goal", "needed", "responsible", "లక్ష్యం", "బాధ్యత", "लक्ष्य", "जिम्मेदारी"),
    "action": ("built", "created", "analysed", "analyzed", "implemented", "చేశాను", "నిర్మించాను", "बनाया", "किया"),
    "result": ("result", "reduced", "improved", "achieved", "ఫలితం", "తగ్గింది", "परिणाम", "सुधार"),
}
FILLERS = ("um", "uh", "erm", "you know", "అంటే", "అమ్", "मतलब", "उम्म")


def contains(text: str, phrase: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(phrase.casefold()) + r"(?!\w)", text.casefold()))


def measure(transcript: str, duration_seconds: float | None = None, keywords: tuple[str, ...] = ()) -> dict:
    if duration_seconds is not None and (not math.isfinite(duration_seconds) or duration_seconds <= 0):
        raise ValueError("duration must be positive and finite")
    words = re.findall(r"\S+", transcript)
    present = {key: any(contains(transcript, cue) for cue in cues) for key, cues in STAR.items()}
    fillers = sum(len(re.findall(r"(?<!\w)" + re.escape(cue) + r"(?!\w)", transcript.casefold())) for cue in FILLERS)
    wanted = tuple(dict.fromkeys(k.casefold().strip() for k in keywords if k.strip()))
    matched = [word for word in wanted if contains(transcript, word)]
    wpm = len(words) * 60 / duration_seconds if duration_seconds else None
    return {
        "word_count": len(words), "star": present, "star_coverage": sum(present.values()) / 4,
        "quantifiers": re.findall(r"\d+(?:[.,]\d+)?\s*%?", transcript),
        "filler_count": fillers, "filler_rate": round(fillers / max(1, len(words)), 4),
        "keyword_coverage": len(matched) / len(wanted) if wanted else None,
        "matched_keywords": matched, "missing_keywords": [k for k in wanted if k not in matched],
        "duration_seconds": duration_seconds, "wpm": round(wpm, 1) if wpm is not None else None,
        "pace_band": None if wpm is None else "slow" if wpm < 100 else "fast" if wpm > 180 else "middle",
        "method": "lexical_indicators_v1",
    }


def weakest_star(metrics: dict) -> str | None:
    return next((key for key in STAR if not metrics["star"][key]), None)
