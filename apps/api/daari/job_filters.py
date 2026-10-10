"""Evidence admission for live feeds, separate from shared engine match scores."""
import re
from datetime import UTC, datetime, timedelta

MAX_JOB_AGE_DAYS = 60
_STOP = {"job", "jobs", "vacancy", "vacancies", "work", "near", "in", "and", "pradesh", "andhra",
         "government", "govt", "recruitment", "ఉద్యోగాలు", "ఉద్యోగం", "ప్రభుత్వ", "नौकरी", "सरकारी"}


def terms(query: str) -> set[str]:
    return {word for word in re.findall(r"[^\W_]+", query.casefold()) if len(word) > 1 and word not in _STOP}


def relevant(query: str, title: str, description: str = "") -> bool:
    wanted = terms(query)
    if not wanted:
        return True
    headline = set(re.findall(r"[^\W_]+", title.casefold()))
    body = set(re.findall(r"[^\W_]+", description.casefold()))
    if wanted <= headline:
        return True
    # A incidental skill mention cannot make an unrelated writing/admin role
    # a technical vacancy. Require a relevant occupation in the title.
    technical = {"developer", "engineer", "programmer", "analyst", "scientist", "architect"}
    if wanted <= (headline | body):
        return bool(wanted & headline or headline & technical)
    return False


def fresh(value: str | None, now: datetime | None = None) -> bool:
    if not value:
        return False
    try:
        published = datetime.fromisoformat(value)
        if published.tzinfo is None:
            published = published.replace(tzinfo=UTC)
        current = now or datetime.now(UTC)
        return current - timedelta(days=MAX_JOB_AGE_DAYS) <= published <= current + timedelta(days=1)
    except (ValueError, TypeError):
        return False
