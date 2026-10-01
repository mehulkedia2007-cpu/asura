"""Three-valued eligibility decisions from source-backed predicate rules."""

from dataclasses import dataclass
from typing import Any

FIELDS = frozenset({"age", "state", "district", "gender", "category", "annual_income", "occupation", "education", "land_holding", "disability", "bpl", "student_status"})
OPS = frozenset({"eq", "ne", "in", "lte", "gte"})


@dataclass(frozen=True)
class Decision:
    status: str
    reasons: tuple[str, ...]
    missing_fields: tuple[str, ...]


def _check(profile: dict[str, Any], rule: dict[str, Any]) -> bool | None:
    field, op, value = rule["field"], rule["op"], rule["value"]
    if field not in FIELDS or op not in OPS or not rule.get("snippet"):
        raise ValueError("predicate requires an allowed field, operator and source snippet")
    actual = profile.get(field)
    if actual is None or actual == "":
        return None
    if op in {"lte", "gte"}:
        try:
            actual, value = float(actual), float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("ordered predicates require numeric values") from exc
    elif op == "in":
        if not isinstance(value, (list, tuple, set, frozenset)):
            raise ValueError("in predicate requires a collection")
        return str(actual).casefold() in {str(item).casefold() for item in value}
    elif isinstance(actual, str) and isinstance(value, str):
        actual, value = actual.casefold(), value.casefold()
    return {"eq": lambda: actual == value, "ne": lambda: actual != value,
            "lte": lambda: actual <= value, "gte": lambda: actual >= value}[op]()


def evaluate(profile: dict[str, Any], rules: dict[str, list[dict[str, Any]]]) -> Decision:
    """False overrides unknown; an `any` group passes if one known rule passes."""
    all_rules, any_rules = rules.get("all", []), rules.get("any", [])
    if not all_rules and not any_rules:
        return Decision("unknown", (), ())
    results = [(_check(profile, rule), rule) for rule in all_rules]
    alternatives = [(_check(profile, rule), rule) for rule in any_rules]
    failed = any(ok is False for ok, _ in results)
    if alternatives and all(ok is False for ok, _ in alternatives):
        failed = True
    missing = {rule["field"] for ok, rule in results if ok is None}
    if alternatives and not any(ok is True for ok, _ in alternatives):
        missing.update(rule["field"] for ok, rule in alternatives if ok is None)
    status = "false" if failed else "unknown" if missing else "true"
    supported = [rule["snippet"] for ok, rule in results if ok is True]
    if alternatives:
        supported.extend(rule["snippet"] for ok, rule in alternatives if ok is True)
    return Decision(status, tuple(supported), tuple(sorted(missing)) if status == "unknown" else ())
