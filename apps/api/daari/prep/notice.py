"""Paste-only extraction. Retain only known notice fields and their source spans."""

import re
from datetime import UTC, date, datetime

FIELDS = {
    "company": ("company", "recruiter", "కంపెనీ", "कंपनी"),
    "role": ("role", "position", "పాత్ర", "पद"),
    "interview_date": ("interview date", "drive date", "date", "తేదీ", "तारीख"),
    "ctc": ("ctc", "salary", "package", "జీతం", "वेतन"),
    "eligibility": ("eligibility", "అర్హత", "पात्रता"),
    "rounds": ("rounds", "selection process", "రౌండ్లు", "चरण"),
    "mode": ("mode", "విధానం", "माध्यम"),
}


def sanitize(value: str) -> str:
    # Names need contextual recognition: discard entire contact/person clauses,
    # including unlabeled continuation lines, instead of retaining the raw notice.
    value = re.split(r"\b(?:contact|coordinator|placement officer|person|name|mr\.?|mrs\.?|ms\.?|dr\.?)\s*[:\s]", value, flags=re.IGNORECASE)[0]
    value = re.split(r"\S+@\S+", value)[0]
    for match in re.finditer(r"(?:\+?91[ -]?)?\d[\d ()-]{8,}\d", value):
        if sum(char.isdigit() for char in match.group()) >= 10:
            value = value[:match.start()]
            break
    return value.strip(" ,;.-")


def parse_date(value: str) -> str | None:
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=UTC).date().isoformat()
        except ValueError:
            pass
    # Slash dates are ambiguous: require an explicit ISO correction.
    return None


def extract(raw: str) -> dict:
    fields: dict = {}
    for key, aliases in FIELDS.items():
        pattern = r"(?:^|\n)\s*(?:" + "|".join(re.escape(a) for a in aliases) + r")\s*[:：-]\s*([^\n]+)"
        found = re.findall(pattern, raw, re.IGNORECASE)
        values = list(dict.fromkeys(sanitize(value) for value in found if sanitize(value)))
        if len(values) != 1:
            fields[key] = {"value": None, "source_span": None, "status": "conflicting" if values else "missing"}
            continue
        span = values[0]
        value = parse_date(span) if key == "interview_date" else (
            [r.strip() for r in re.split(r",|→|->|;", span) if r.strip()] if key == "rounds" else span)
        fields[key] = {"value": value, "source_span": span, "status": "extracted" if value is not None else "needs_review"}
    return {"fields": fields, "confirmation_required": True, "input_mode": "paste",
            "retained_text": "\n".join(f"{key}: {row['source_span']}" for key, row in fields.items() if row["source_span"])}


def validate_date(value: str) -> date:
    return date.fromisoformat(value)
