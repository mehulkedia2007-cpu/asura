"""Live myScheme search with conservative eligibility and stamped evidence."""

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

import httpx
from daari_core.eligibility import evaluate

from daari.ap_portal import search as search_ap_portal
from daari.myscheme_client import detail, search_pages
from daari.scheme_index import coverage, retrieve, upsert
from daari.scheme_rules import extract as extract_llm_rules


def _items(payload: dict) -> list[dict]:
    data = payload.get("data", payload)
    if isinstance(data, dict):
        hits = data.get("hits")
        if isinstance(hits, dict) and isinstance(hits.get("items"), list):
            return [item.get("fields", item) for item in hits["items"] if isinstance(item, dict)]
        for key in ("schemes", "hits", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return [item.get("_source", item) for item in value if isinstance(item, dict)]
            if isinstance(value, dict) and isinstance(value.get("hits"), list):
                return [item.get("_source", item) for item in value["hits"] if isinstance(item, dict)]
    return []


def _text(value: Any) -> str:
    if isinstance(value, str):
        return re.sub(r"<[^>]+>", " ", value).strip()
    if isinstance(value, list):
        return "\n".join(_text(item) for item in value)
    if isinstance(value, dict):
        if "label" in value:
            return _text(value["label"])
        return "\n".join(_text(item) for item in value.values())
    return ""


def extract_rules(eligibility_text: str) -> tuple[dict, bool]:
    """Extract only narrow, unambiguous predicates; incomplete text stays unknown."""
    clauses = [s.strip(" .\n") for s in re.split(r"[.;\n]+", eligibility_text) if s.strip()]
    rules: list[dict] = []
    complete = bool(clauses)
    for clause in clauses:
        found = []
        age = re.fullmatch(r"(?:applicant(?:'s)? )?age (?:must be |should be )?between (\d+) and (\d+) years?", clause, re.IGNORECASE)
        if age:
            found = [{"field": "age", "op": "gte", "value": int(age[1]), "snippet": clause},
                     {"field": "age", "op": "lte", "value": int(age[2]), "snippet": clause}]
        state = re.fullmatch(r"(?:the )?applicant must be (?:a )?(?:permanent )?resident of (Andhra Pradesh)", clause, re.IGNORECASE)
        if state:
            found = [{"field": "state", "op": "eq", "value": state[1], "snippet": clause}]
        income = re.fullmatch(r"(?:annual )?(?:family )?income (?:must be |should be )?(?:less than|below|up to) (?:Rs\.?|₹)?\s*([\d,]+)", clause, re.IGNORECASE)
        if income:
            found = [{"field": "annual_income", "op": "lte", "value": int(income[1].replace(",", "")), "snippet": clause}]
        if not found:
            complete = False
        rules.extend(found)
    return {"all": rules, "any": []}, complete


def normalize(raw: dict, fetched_at: str) -> dict | None:
    slug = str(raw.get("slug") or raw.get("scheme_slug") or "").strip().strip("/")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", slug):
        return None
    url = f"https://www.myscheme.gov.in/schemes/{slug}"
    name = _text(raw.get("schemeNameEng") or raw.get("scheme_name") or raw.get("schemeName") or raw.get("name"))
    if not name:
        return None
    description = _text(raw.get("briefDescriptionEng") or raw.get("brief_description") or raw.get("briefDescription") or raw.get("schemeShortTitle") or raw.get("description"))
    eligibility_text = _text(raw.get("eligibility"))
    rules, complete = extract_rules(eligibility_text)
    region = _text(raw.get("level"))
    states = raw.get("beneficiary_states") or raw.get("beneficiaryState") or raw.get("state") or []
    ap = "andhra pradesh" in str(states).casefold() or "andhra pradesh" in region.casefold()
    if not ap and "central" not in region.casefold():
        return None
    content = f"{name}\n{description}\n{eligibility_text}"
    return {
        "id": slug, "name_en": name, "level": region,
        "name_te": _text(raw.get("schemeName")) if raw.get("schemeNameEng") else None,
        "summary_te": _text(raw.get("briefDescription")) if raw.get("briefDescriptionEng") else None,
        "state": "Andhra Pradesh" if ap else None,
        "ministry_or_dept": _text(raw.get("ministry") or raw.get("nodalMinistryName") or raw.get("department")),
        "summary_en": description, "tags": raw.get("tags") or [],
        "benefit_text": _text(raw.get("benefits")) or description,
        "eligibility_text": eligibility_text, "documents_text": _text(raw.get("documents")),
        "apply_text": _text(raw.get("application_process") or raw.get("application")),
        "url": url, "fetched_at": fetched_at, "as_of": raw.get("last_updated"),
        "content_hash": hashlib.sha256(content.encode()).hexdigest(),
        "rules": rules, "rules_complete": complete,
        "source": "myScheme",
    }


def merge_detail(scheme: dict, payload: dict) -> dict:
    english = payload["en"]
    telugu = payload["te"]
    basics = english.get("basicDetails") or {}
    content = english.get("schemeContent") or {}
    criteria = english.get("eligibilityCriteria") or {}
    telugu_basics = telugu.get("basicDetails") or {}
    telugu_content = telugu.get("schemeContent") or {}
    documents = payload["documents"]
    scheme["name_en"] = _text(basics.get("schemeName")) or scheme["name_en"]
    scheme["name_te"] = _text(telugu_basics.get("schemeName")) or scheme.get("name_te")
    scheme["summary_te"] = _text(telugu_content.get("briefDescription")) or scheme.get("summary_te")
    scheme["ministry_or_dept"] = _text(basics.get("nodalMinistryName")) or scheme["ministry_or_dept"]
    scheme["summary_en"] = _text(content.get("briefDescription")) or scheme.get("summary_en") or scheme["benefit_text"]
    scheme["benefit_text"] = _text(content.get("benefits_md")) or scheme["benefit_text"]
    scheme["eligibility_text"] = _text(criteria.get("eligibilityDescription_md"))
    scheme["documents_text"] = _text(documents.get("documentsRequired_md"))
    scheme["apply_steps"] = [
        {"channel": _text(item.get("mode")), "text": _text(item.get("process"))[:2000]}
        for item in english.get("applicationProcess", []) if isinstance(item, dict)
    ]
    scheme["apply_text"] = "\n".join(step["text"] for step in scheme["apply_steps"])
    scheme["application_channels"] = [
        _text(item.get("applicationName")) for item in payload["channels"] if isinstance(item, dict)
    ]
    scheme["fetched_at"] = payload["fetched_at"]
    scheme["as_of"] = basics.get("lastUpdated") or content.get("lastUpdated") or scheme.get("as_of")
    content_text = "\n".join((scheme["name_en"], scheme.get("summary_en") or "", scheme["benefit_text"],
                              scheme["eligibility_text"], scheme["documents_text"], scheme["apply_text"]))
    scheme["content_hash"] = hashlib.sha256(content_text.encode()).hexdigest()
    scheme["rules"], scheme["rules_complete"] = extract_rules(scheme["eligibility_text"])
    scheme["stale"] = payload["stale"]
    return scheme


async def ingest_summaries(query: str, locale: str = "en", refresh: bool = False) -> dict:
    """Keep the searchable government index broad without claiming summary eligibility."""
    async with httpx.AsyncClient(timeout=15) as client:
        raw_items, errors, truncated = await search_pages(client, query, refresh, locale)
        candidates = [item for raw, stamp in raw_items if (item := normalize(raw, stamp))]
        for scheme in candidates:
            await upsert(scheme, summary_only=True)
    return {"query": query, "indexed_candidates": len(candidates),
            "errors": errors, "truncated": truncated}


async def search(query: str, profile: dict, refresh: bool = False, locale: str = "en") -> dict:
    query = query.strip()[:100]
    if not query:
        raise ValueError("query is required")
    results: list[dict] = []
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=15) as client:
        raw_items, search_errors, truncated = await search_pages(client, query, refresh, locale)
        errors.extend(search_errors)
        candidates = [item for raw, stamp in raw_items if (item := normalize(raw, stamp))]
        portal_schemes, portal_errors = await search_ap_portal(client, query, refresh)
        errors.extend(portal_errors)
        for scheme in [*candidates, *portal_schemes]:
            await upsert(scheme, summary_only=True)
        first_pass = await retrieve(query, limit=20)
        rank = {item["id"]: i for i, item in enumerate(first_pass["records"])}
        candidates.sort(key=lambda item: (item["state"] != "Andhra Pradesh",
                                          rank.get(item["id"], 1000)))
        for scheme in candidates[:5]:
            payload, detail_errors = await detail(client, scheme["id"], locale, refresh)
            errors.extend(detail_errors)
            if payload:
                merge_detail(scheme, payload)
            if scheme["eligibility_text"] and not scheme["rules_complete"]:
                extracted, complete, extraction_error = await extract_llm_rules(
                    scheme["id"], scheme["content_hash"], scheme["eligibility_text"]
                )
                if extraction_error:
                    errors.append(extraction_error)
                if extracted["all"] or extracted["any"]:
                    scheme["rules"], scheme["rules_complete"] = extracted, complete
            await upsert(scheme)
            results.append(scheme)
    retrieval = await retrieve(query)
    retrieval_scores = {item["id"]: item["retrieval_score"] for item in retrieval["records"]}
    ordered = [*results, *retrieval["records"]]
    deduplicated: dict[str, dict] = {}
    for scheme in ordered:
        deduplicated.setdefault(scheme["id"], scheme)
    visible = []
    result_ids = {result["id"] for result in results}
    ranked = sorted(deduplicated.values(), key=lambda item: -(
        retrieval_scores.get(item["id"], 0.0)
        + (0.005 if item.get("state") == "Andhra Pradesh" else 0.0)
        + (0.002 if item["id"] in result_ids else 0.0)
    ))
    for scheme in ranked:
        scheme["stale"] = bool(scheme.get("stale")) or (
            datetime.now(UTC) - datetime.fromisoformat(scheme["fetched_at"])
        ).total_seconds() > 6 * 3600
        # A summary without complete eligibility evidence cannot establish qualification.
        try:
            decision = evaluate(profile, scheme["rules"]) if scheme["rules_complete"] else None
        except ValueError:
            decision = None
        scheme["eligibility"] = {
            "status": decision.status if decision else "unknown",
            "reasons": decision.reasons if decision else (),
            "missing_fields": decision.missing_fields if decision else (),
        }
        if scheme["eligibility"]["status"] != "false":
            visible.append(scheme)
        if len(visible) >= 5:
            break
    next_question = None
    for scheme in visible:
        missing = scheme["eligibility"]["missing_fields"]
        if scheme["rules_complete"] and len(missing) == 1:
            next_question = {"scheme_id": scheme["id"], "field": missing[0],
                             "source_snippets": [rule["snippet"] for group in scheme["rules"].values()
                                                 for rule in group if rule["field"] == missing[0]]}
            break
    return {"schemes": visible, "source_errors": errors, "truncated": truncated,
            "candidates_found": len(candidates) + len(portal_schemes),
            "stale": any(item.get("stale") for item in visible),
            "retrieval_kind": retrieval["kind"], "embedding_kind": retrieval["embedding_kind"],
            "searched_at": datetime.now(UTC).isoformat(), "source": "myScheme",
            "coverage": await coverage(), "next_question": next_question}
