"""Source-text ranking with bilingual concept normalization; no scheme-ID rules.

Titles and benefit descriptions express purpose. Eligibility and application
boilerplate must not overpower them simply because a record has more detail.
"""

import math
import re
from collections import Counter

# Both documents and queries use the same vocabulary. Telugu stems deliberately
# cover inflected forms; English matches whole words (never e.g. IT in benefit).
_CONCEPTS = {
    "skill": (r"\b(?:skills?|skilling|upskilling|futureskills)\b", "నైపుణ్య"),
    "training": (
        r"\b(?:training|train|courses?|learn|learning)\b",
        "శిక్షణ",
        "నేర్చు",
        "కోర్సు",
    ),
    "practice": (r"\b(?:internships?|practical experience)\b",),
    "vocational": (r"\b(?:vocational|trades?|craftsmen|iti|itis)\b", "వృత్తి"),
    "apprentice": (r"\bapprentice\w*\b", "అప్రెంటిస్"),
    "loan": (r"\bloans?\b", "రుణ", "లోన్"),
    "education": (r"\beducation(?:al)?\b", "విద్య"),
    "rural": (r"\b(?:rural|villages?|grameen|gramin|gramodyog)\b", "గ్రామ"),
    "employment": (r"\b(?:employment|jobs?|livelihoods?|work)\b", "ఉపాధి", "ఉద్యోగ", "పని"),
    "entrepreneur": (
        r"\b(?:entrepreneur\w*|business|start[- ]?ups?)\b",
        "వ్యవస్థాపక",
        "వ్యాపార",
    ),
    "disability": (
        r"\b(?:disabilit\w*|disabled|divyangjan|differently abled)\b",
        "వికలాంగ",
        "దివ్యాంగ",
    ),
    "digital": (
        # FutureSkills Prime is described by its official scheme source as a
        # digital-upskilling incentive:
        # https://www.myscheme.gov.in/schemes/fspip . Preserve that proper-name
        # alias in the same vocabulary used for search instead of requiring an
        # embedding.
        r"\b(?:digital|technology|electronics?|ict|esdm|futureskills)\b",
        "డిజిటల్",
        "టెక్నాలజీ",
        "ఎలక్ట్రానిక్స్",
        "ఐటీ",
    ),
    "craft": (
        r"\b(?:crafts?|handicrafts?|artisans?|craftsmen|coir|khadi)\b",
        "హస్తకళ",
        "చేతివృత్తి",
    ),
    "pmkvy": (r"\bpmkvy\b", r"kaushal vikas", "కౌశల్ వికాస్", "పీఎంకేవీవై"),
}
_STOP = {
    "a",
    "an",
    "and",
    "for",
    "of",
    "the",
    "to",
    "in",
    "on",
    "or",
    "with",
    "by",
    "from",
    "government",
    "scheme",
    "schemes",
    "program",
    "programme",
    "persons",
    "people",
    "want",
    "need",
    "paid",
    "opportunity",
    "start",
    "traditional",
    "term",
    "short",
    "pradhan",
    "mantri",
    "kaushal",
    "vikas",
    "yojana",
}


def tokens(value: str) -> list[str]:
    value = re.sub(r"\bIT\b", "digital", value).casefold()
    concepts = []
    for concept, patterns in _CONCEPTS.items():
        if any(re.search(pattern, value) for pattern in patterns):
            concepts.append(concept)
    for patterns in _CONCEPTS.values():
        for pattern in patterns:
            # Preserve Telugu until all concepts have been recognized.
            if pattern.startswith("\\b") or pattern == "kaushal vikas":
                value = re.sub(pattern, " ", value)
    words = re.findall(r"[a-z][a-z0-9]+", value)
    if not concepts:
        words.extend(re.findall(r"[\u0c00-\u0c7f]+", value))
    return concepts + [word for word in words if word not in _STOP]


def rank_records(
    query: str,
    records: list[dict],
    limit: int = 8,
    prior: dict[str, float] | None = None,
    *,
    dedupe_duplicates: bool = False,
) -> list[dict]:
    """BM25 over purpose fields, with coverage of explicit query concepts."""
    terms = set(tokens(query))
    if not query.strip() or limit <= 0:
        return []
    fields = [
        (
            Counter(
                tokens(str(r.get("name_en") or "") + " " + str(r.get("name_te") or ""))
            ),
            Counter(
                tokens(
                    str(r.get("summary_en") or "")
                    + " "
                    + str(r.get("benefit_text") or "")
                    + " "
                    + str(r.get("summary_te") or "")
                )
            ),
        )
        for r in records
    ]
    counts = Counter(
        term
        for title, body in fields
        for term in terms
        if term in title or term in body
    )
    averages = [
        sum(sum(f[i].values()) for f in fields) / max(len(fields), 1) or 1
        for i in (0, 1)
    ]
    focus = terms & (
        _CONCEPTS.keys() - {"skill", "training", "employment", "education", "practice"}
    )
    # A trade-training request is vocational; explicitly traditional/artisan
    # language distinguishes craft support from general occupational training.
    if (
        "craft" in focus
        and "vocational" in focus
        and not re.search(
            r"traditional|artisan|handicraft|సాంప్రదాయ|హస్తకళ", query.casefold()
        )
    ):
        focus.discard("craft")
        terms.discard("craft")
    if "craft" in focus and re.search(
        r"traditional|artisan|handicraft|సాంప్రదాయ|హస్తకళ", query.casefold()
    ):
        focus.discard("vocational")
        terms.discard("vocational")
    if focus & {"disability", "loan"}:
        focus.discard("vocational")
    scored = []
    for record, (title, body) in zip(records, fields, strict=True):
        score = 0.0
        for term in terms:
            idf = math.log(
                1 + (len(records) - counts[term] + 0.5) / (counts[term] + 0.5)
            )
            for i, (field, weight) in enumerate(((title, 4.0), (body, 1.0))):
                tf = field[term]
                score += (
                    weight
                    * idf
                    * tf
                    * 2.2
                    / (tf + 1.2 * (0.25 + 0.75 * sum(field.values()) / averages[i]))
                )
        if score <= 0:
            if (prior or {}).get(record["id"], 0.0) > 0:
                scored.append(
                    {**record, "retrieval_score": (prior or {})[record["id"]]}
                )
            continue
        # Missing a requested topic cannot be compensated by generic training.
        if focus:
            score *= (
                0.05 + sum(t in title or t in body for t in focus) / len(focus)
            ) ** 3
        metadata = set(tokens(" ".join(record.get("tags") or [])))
        department = set(tokens(str(record.get("ministry_or_dept") or "")))
        wants_training = bool(terms & {"skill", "training", "vocational", "practice"})
        has_training = bool(
            (title.keys() | body.keys() | metadata)
            & {"skill", "training", "vocational", "practice"}
        )
        if wants_training and not has_training:
            score *= 0.5
        if focus and not any(t in title for t in focus):
            score *= 0.5
        # Topic evidence in the title outranks incidental mentions in prose.
        if focus:
            score = score * 0.1 + sum(
                16
                if t in title or (t == "digital" and t in department)
                else 8
                if t in body or t in metadata
                else 0
                for t in focus
            )
            if wants_training:
                score += (
                    4
                    if title.keys() & {"skill", "training", "vocational", "practice"}
                    else 2
                    if has_training
                    else 0
                )
                if not has_training:
                    score *= 0.6
            if "employment" in terms:
                score += 6 if "employment" in title or "employment" in body else 0
        if re.search(
            r"\b(?:awards?|medal|insurance|pension)\b",
            str(record.get("name_en", "")).casefold(),
        ) and not terms & {"award", "medal", "insurance", "pension"}:
            score *= 0.2
        score += (prior or {}).get(record["id"], 0.0)
        scored.append({**record, "retrieval_score": round(score, 6)})
    ordered = sorted(scored, key=lambda r: (-r["retrieval_score"], r["id"]))
    if not dedupe_duplicates:
        return ordered[:limit]

    unique: list[dict] = []
    seen_titles: set[str] = set()
    for record in sorted(
        ordered,
        key=lambda r: (
            -r["retrieval_score"],
            # When two registries list the same named scheme, keep the record
            # with the richer source detail; this usually preserves the full
            # myScheme record over an AP directory summary.
            -sum(bool(r.get(key)) for key in (
                "summary_en", "benefit_text", "eligibility_text", "documents_text", "apply_text"
            )),
            r["id"],
        ),
    ):
        title = re.sub(r"\W+", " ", str(record.get("name_en") or "").casefold()).strip()
        # Records without a title cannot be safely merged; their source IDs
        # remain distinct.
        key = title or str(record["id"])
        if key in seen_titles:
            continue
        seen_titles.add(key)
        unique.append(record)
        if len(unique) >= limit:
            break
    return unique
