"""A bounded tool loop. Only source spans survive into user-facing prose."""

import json
import re
import time
import unicodedata
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from daari import leads, p5, schemes
from daari.agent.llm import complete
from daari.agent.registry import AssessArgs, LearnArgs, MatchArgs, PathArgs
from daari.grounding.verifier import Evidence, verify
from daari.p2 import _path, _path_data, assess_next, match_role, simulate
from daari.prep.pack import PackArgs
from daari.taxonomy_loader import get_taxonomy
from daari.voice.lang import Locale, detect
from daari.voice.stream import Sentences


class AgentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    locale: Locale = "en"
    persona: Literal["student", "rural"] = "student"
    held: dict[str, int] = Field(default_factory=dict)
    goal: str = "data_analyst"
    place: str = Field(default="Guntur", max_length=150)
    profile: dict = Field(default_factory=dict)
    confirmed_notice: PackArgs | None = None
    pending_field: Literal["age", "state", "district", "gender", "category",
                           "annual_income", "occupation", "education", "land_holding",
                           "disability", "bpl", "student_status"] | None = None
    pending_query: str | None = Field(default=None, max_length=100)


class JobArgs(BaseModel):
    query: str = Field(min_length=1, max_length=100)
    place: str | None = Field(default=None, max_length=150)


class SchemeArgs(BaseModel):
    query: str = Field(min_length=1, max_length=100)


class GoalArgs(BaseModel):
    goal: str | None = None


class SkillUpdateArgs(GoalArgs):
    skill: str
    level: int = Field(ge=1, le=5)


class SkillArgs(BaseModel):
    skill: str


_ARG_MODELS: dict[str, type[BaseModel]] = {
    "search_jobs": JobArgs, "find_schemes": SchemeArgs,
    "get_roadmap": GoalArgs, "simulate_skill_update": SkillUpdateArgs,
    "match_roles": GoalArgs, "assess_next_item": SkillArgs,
}


_TOOLS = [
    {"name": "search_jobs", "description": "Search current job leads near a place", "parameters": {
        "type": "object", "properties": {"query": {"type": "string"}, "place": {"type": "string"}},
        "required": ["query"]}},
    {"name": "find_schemes", "description": "Search live government schemes; eligibility is deterministic", "parameters": {
        "type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "get_roadmap", "description": "Calculate the skill path for a taxonomy goal", "parameters": {
        "type": "object", "properties": {"goal": {"type": "string"}}, "required": ["goal"]}},
    {"name": "simulate_skill_update", "description": "Show path and vector change after a skill update", "parameters": {
        "type": "object", "properties": {"skill": {"type": "string"}, "level": {"type": "integer"}},
        "required": ["skill", "level"]}},
    {"name": "match_roles", "description": "Compute an explained role match", "parameters": {
        "type": "object", "properties": {"goal": {"type": "string"}}, "required": ["goal"]}},
    {"name": "assess_next_item", "description": "Choose the next assessment question", "parameters": {
        "type": "object", "properties": {"skill": {"type": "string"}}, "required": ["skill"]}},
]
_P5_MODELS = {"get_company_questions": p5.QuestionsArgs, "build_prep_pack": GoalArgs,
              "start_interview": p5.StartArgs, "interview_feedback": p5.FeedbackArgs}
_ARG_MODELS.update(_P5_MODELS)
_TOOLS.extend({"name": name, "description": description, "parameters": _P5_MODELS[name].model_json_schema()}
              for name, description in (
                  ("get_company_questions", "Retrieve dated candidate-reported questions for an exact company and role"),
                  ("build_prep_pack", "Build from user-confirmed notice fields already supplied in this request"),
                  ("start_interview", "Start five-question interview practice"),
                  ("interview_feedback", "Compute quote-guarded feedback for the user's answer")))
_BY_NAME = {tool["name"]: tool for tool in _TOOLS}
_NO_DATA = {
    "en": "No verified answer is available. Check the linked source directly.",
    "te": "ధృవీకరించిన సమాధానం అందుబాటులో లేదు. మూలాన్ని నేరుగా తనిఖీ చేయండి.",
    "hi": "सत्यापित उत्तर उपलब्ध नहीं है। स्रोत पर सीधे जाँचें।",
}
_STRUCTURED = {
    "en": "Review the computed result below.",
    "te": "లెక్కించిన ఫలితాన్ని కింద చూడండి.",
    "hi": "गणना किया गया परिणाम नीचे देखें।",
}
_FIELD_LABELS = {
    "age": ("age", "వయసు", "उम्र"),
    "annual_income": ("annual income", "వార్షిక ఆదాయం", "वार्षिक आय"),
    "state": ("state", "రాష్ట్రం", "राज्य"),
    "district": ("district", "జిల్లా", "ज़िला"),
    "gender": ("gender", "లింగం", "लिंग"),
    "category": ("social category", "సామాజిక వర్గం", "सामाजिक वर्ग"),
    "occupation": ("occupation", "వృత్తి", "पेशा"),
    "education": ("education", "విద్య", "शिक्षा"),
    "land_holding": ("land holding", "భూమి వివరాలు", "भूमि स्वामित्व"),
    "disability": ("disability status", "వైకల్య స్థితి", "विकलांगता स्थिति"),
    "bpl": ("BPL status", "బీపీఎల్ స్థితి", "बीपीएल स्थिति"),
    "student_status": ("student status", "విద్యార్థి స్థితి", "छात्र स्थिति"),
}


def _question(field: str, locale: Locale) -> str:
    index = {"en": 0, "te": 1, "hi": 2}[locale]
    label = _FIELD_LABELS[field][index]
    return {"en": f"What is your {label}?", "te": f"మీ {label} ఏమిటి?",
            "hi": f"आपकी {label} क्या है?"}[locale]


def _slot_value(field: str, text: str) -> str | int | float | bool | None:
    cleaned = text.strip()
    if field in {"age", "annual_income", "land_holding"}:
        digits = "".join(str(unicodedata.digit(char)) if char.isdecimal() else char for char in cleaned)
        match = re.search(r"\d+(?:[,.]\d+)*", digits)
        if not match:
            return None
        number = float(match.group().replace(",", ""))
        if field == "annual_income":
            if re.search(r"lakh|lac|లక్ష|लाख", cleaned, re.IGNORECASE):
                number *= 100_000
            elif re.search(r"crore|కోటి|करोड़", cleaned, re.IGNORECASE):
                number *= 10_000_000
            elif re.search(r"thousand|వేల|हजार|हज़ार", cleaned, re.IGNORECASE):
                number *= 1_000
        if (field == "age" and not 0 < number <= 120) or (
            field != "age" and not 0 <= number <= 1_000_000_000_000
        ):
            return None
        return int(number) if field != "land_holding" else number
    if field in {"disability", "bpl", "student_status"}:
        value = cleaned.casefold()
        if value in {"yes", "true", "అవును", "हाँ", "हां"}:
            return True
        if value in {"no", "false", "లేదు", "नहीं"}:
            return False
        return None
    return cleaned[:100] or None


def _fallback(text: str) -> tuple[str, dict] | None:
    lower = text.casefold()
    if any(word in lower for word in ("scheme", "యోజన", "పథకం", "योजना")):
        return "find_schemes", {"query": text}
    if any(word in lower for word in ("job", "work", "ఉద్యోగ", "పని", "नौकरी", "काम")):
        terms = (("driver", ("driver", "డ్రైవర్", "డ్రైవింగ్", "ड्राइवर")),
                 ("delivery", ("delivery", "డెలివరీ", "डिलीवरी")),
                 ("technician", ("technician", "టెక్నీషియన్", "तकनीशियन")),
                 ("data analyst", ("data analyst", "డేటా అనలిస్ట్", "डेटा एनालिस्ट")))
        query = next((label for label, aliases in terms if any(alias in lower for alias in aliases)), "jobs")
        return "search_jobs", {"query": query}
    if any(word in lower for word in ("path", "roadmap", "మార్గం", "रास्ता")):
        return "get_roadmap", {}
    return None


async def _execute(name: str, supplied: dict, request: AgentRequest) -> dict:
    if name not in _BY_NAME:
        raise ValueError("unknown tool")
    supplied = _ARG_MODELS[name].model_validate(supplied).model_dump(exclude_none=True)
    if name == "get_company_questions":
        return await p5.get_company_questions(p5.QuestionsArgs(**supplied))
    if name == "build_prep_pack":
        if request.confirmed_notice is None or not request.confirmed_notice.confirmed:
            return {"confirmation_required": True}
        return await p5.build_prep_pack(request.confirmed_notice)
    if name == "start_interview":
        return await p5.start_interview(p5.StartArgs(**{**supplied, "locale": request.locale, "held": request.held}))
    if name == "interview_feedback":
        # Never let the model invent the learner's answer to grade.
        return await p5.interview_feedback(p5.FeedbackArgs(transcript=request.text, locale=request.locale))
    if name == "search_jobs":
        query = str(supplied["query"]).strip()
        place = str(supplied.get("place") or request.place).strip()
        return await leads.search(query, place, request.held)
    if name == "find_schemes":
        query = str(supplied["query"]).strip()
        return await schemes.search(query, request.profile, locale=request.locale)
    goal = str(supplied.get("goal") or request.goal)
    if goal not in get_taxonomy().roles:
        raise ValueError("unknown goal")
    base = {"persona": request.persona, "held": request.held, "goal": goal}
    if name == "get_roadmap":
        return _path_data(_path(PathArgs(**base)), 10)
    if name == "simulate_skill_update":
        return simulate(LearnArgs(**base, skill=supplied["skill"], level=supplied["level"]))
    if name == "match_roles":
        return match_role(MatchArgs(**base))
    return assess_next(AssessArgs(skill=supplied["skill"]))


def _stamp(raw: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(raw))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return None


def _evidence(name: str, result: dict, locale: Locale) -> tuple[list[Evidence], list[dict]]:
    items = result.get("leads", []) if name == "search_jobs" else result.get("schemes", []) if name == "find_schemes" else result.get("questions", []) if name == "get_company_questions" else []
    evidence = []
    cards = []
    for index, item in enumerate(items[:5]):
        url = item.get("source_url") or item.get("url")
        stamp = _stamp(item.get("fetched_at"))
        if not isinstance(url, str) or not url.startswith("https://") or not stamp:
            continue
        title = (item.get("name_te") if locale == "te" else None) or (
            item.get("name_en") if name == "find_schemes" else (item.get(f"text_{locale}") or item.get("text")) if name == "get_company_questions" else item.get("title"))
        summary = (item.get("summary_te") if locale == "te" else None) or (
            item.get("summary_en") if name == "find_schemes" else None)
        as_of = None
        if name == "get_company_questions":
            try:
                as_of = date.fromisoformat(item["as_of"])
            except (KeyError, ValueError, TypeError):
                continue
            label = {"en": "Reported by a candidate; source updated", "te": "అభ్యర్థి నివేదిక; మూలం నవీకరణ",
                     "hi": "उम्मीदवार की रिपोर्ट; स्रोत अद्यतन"}[locale]
            summary = f"{label}: {as_of.isoformat()}"
        # Localize the field label, retaining the source's name verbatim. This
        # deterministic presentation adds no translated entity, benefit or number.
        spoken_title = title
        if title and locale != "en" and detect(str(title), "en") != locale:
            labels = {"te": ("ఉద్యోగం", "పథకం"), "hi": ("नौकरी", "योजना")}
            label = ({"te": "ప్రశ్న", "hi": "प्रश्न"}[locale] if name == "get_company_questions"
                     else labels[locale][int(name == "find_schemes")])
            spoken_title = f"{label}: {title}"
        source_text = "\n".join(str(value) for value in (spoken_title, title, summary) if value)
        if not source_text:
            continue
        evidence.append(Evidence(f"{name}:{index}", source_text, url, stamp, as_of))
        cards.append({"title": title, "summary": summary, "source_url": url,
                      "fetched_at": stamp.isoformat(),
                      "eligibility": item.get("eligibility") if name == "find_schemes" else None,
                      "scam": item.get("scam") if name == "search_jobs" else None,
                      "distance_km": item.get("distance_km") if name == "search_jobs" else None})
    return evidence, cards


def _source_draft(evidence: list[Evidence], locale: Locale) -> str:
    selected = []
    for item in evidence[:3]:
        lines = [line.strip() for line in item.text.splitlines() if line.strip()]
        if not lines:
            continue
        # Title is source text in the requested language when the source supplies it.
        if locale == "te" and not any("\u0c00" <= char <= "\u0c7f" for char in lines[0]):
            continue
        if locale == "hi" and not any("\u0900" <= char <= "\u097f" for char in lines[0]):
            continue
        selected.append(lines[0])
    return "\n".join(selected)


def _safe_verify(
    draft: str, evidence: list[Evidence], searched: str, verifier=None,
) -> dict:
    """Fail closed if verification is unavailable or raises unexpectedly."""
    try:
        check = verifier or verify
        return check(draft, evidence, searched=searched)
    except Exception:  # noqa: BLE001 — an unavailable guard must never expose prose.
        return {
            "sentences": [],
            "struck": [{"reason": "verifier_unavailable"}] if draft.strip() else [],
            "no_data": True,
            "message": "",
            "newest_evidence_at": None,
        }


async def run(
    request: AgentRequest,
    on_sentence: Callable[[str], Awaitable[None]] | None = None,
    *,
    bypass_cache: bool = False,
) -> dict:
    locale = detect(request.text, request.locale)
    request = request.model_copy(update={"locale": locale})
    forced: tuple[str, dict] | None = None
    profile_update: dict = {}
    if request.pending_field and request.pending_query:
        value = _slot_value(request.pending_field, request.text)
        if value is None:
            return {"locale": locale, "provider": "deterministic", "trace": [], "cards": [],
                    "verification": {"sentences": [], "struck": [], "no_data": True,
                                     "message": _question(request.pending_field, locale),
                                     "citations": {}, "newest_evidence_at": None},
                    "next_question": {"field": request.pending_field,
                                      "query": request.pending_query,
                                      "text": _question(request.pending_field, locale)},
                    "profile_update": {}, "t_llm_response": None,
                    "t_llm_first_token": None,
                    "t_engine_done": time.monotonic()}
        request.profile = {**request.profile, request.pending_field: value}
        profile_update = {request.pending_field: value}
        forced = ("find_schemes", {"query": request.pending_query})
    system = (f"Today is {datetime.now(UTC).date()}. Persona: {request.persona}. Reply language: {locale}. "
              f"Current goal ID: {request.goal}. Current place: {request.place}. "
              f"Allowed goal IDs: {', '.join(get_taxonomy().roles)}. "
              f"Allowed skill IDs: {', '.join(get_taxonomy().skills)}. "
              f"Held skills: {json.dumps(request.held, sort_keys=True)}. "
              "Use these exact IDs in tool arguments; omit optional goal to use the current goal. "
              "Use tools for current facts. Never invent numbers, names, eligibility or placement promises. "
              "Only repeat verbatim source text in your final answer; the verifier removes other claims. "
              "Choose a tool before answering a factual request. Do not repeat a tool call.")
    messages: list[dict] = [{"role": "system", "content": system},
                            {"role": "user", "content": request.text}]
    trace: list[dict] = []
    evidence: list[Evidence] = []
    cards: list[dict] = []
    engine_result: dict | None = None
    next_question: dict | None = None
    final = ""
    provider = "unavailable"
    llm_response = None
    first_token = None
    engine_done = time.monotonic()
    visited: set[str] = set()
    streamed: list[dict] = []

    async def publish(parts: list[str]) -> None:
        for part in parts:
            if locale != "en" and detect(part, "en") != locale:
                continue
            checked_part = _safe_verify(part, evidence, "the available sources")
            for row in checked_part["sentences"]:
                if row not in streamed:
                    streamed.append(row)
                    if on_sentence:
                        await on_sentence(row["text"])

    for _ in range(6):
        splitter = Sentences()

        async def receive(text: str) -> None:
            nonlocal splitter
            if not text:
                splitter = Sentences()
                return
            await publish(splitter.push(text))

        if forced:
            model_message, chosen, cached = None, "deterministic", False
        else:
            if on_sentence and evidence:
                if bypass_cache:
                    model_message, chosen, cached = await complete(
                        messages, _TOOLS, on_text=receive, use_cache=False,
                    )
                else:
                    model_message, chosen, cached = await complete(messages, _TOOLS, on_text=receive)
            else:
                if bypass_cache:
                    model_message, chosen, cached = await complete(messages, _TOOLS, use_cache=False)
                else:
                    model_message, chosen, cached = await complete(messages, _TOOLS)
        if model_message is None:
            fallback = forced or (_fallback(request.text) if not visited else None)
            if not fallback:
                break
            name, arguments = fallback
            provider = chosen
            forced = None
            calls = [{"id": "fallback", "function": {"name": name,
                                                        "arguments": json.dumps(arguments)}}]
        else:
            provider = chosen
            llm_response = time.monotonic()
            if first_token is None:
                first_token = model_message.get("_first_token_at")
            calls = model_message.get("tool_calls") or []
            if not calls:
                final = str(model_message.get("content") or "")
                await publish(splitter.push("", final=True))
                break
            messages.append(model_message)
        for index, call in enumerate(calls):
            name = call.get("function", {}).get("name", "")
            if name not in _BY_NAME or name in visited or index >= 2:
                trace.append({"tool": name, "args": {}, "ms": 0.0,
                              "provider": provider, "status": "rejected", "cache_hit": cached})
                if model_message is not None:
                    messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                     "name": name, "content": '{"error":"tool_not_available"}'})
                continue
            visited.add(name)
            start = time.monotonic()
            arguments: dict = {}
            try:
                arguments = json.loads(call["function"].get("arguments") or "{}")
                if not isinstance(arguments, dict):
                    raise TypeError("invalid arguments")
                result = await _execute(name, arguments, request)
                if name not in {"search_jobs", "find_schemes"}:
                    engine_result = {"kind": name, "data": result}
                new_evidence, new_cards = _evidence(name, result, locale)
                evidence.extend(new_evidence)
                cards.extend(new_cards)
                if name == "find_schemes" and new_evidence and result.get("next_question"):
                    field = result["next_question"].get("field")
                    if field in _FIELD_LABELS:
                        next_question = {"field": field, "query": arguments["query"],
                                         "text": _question(field, locale)}
                # Request-time metadata changes every run; source fetch stamps remain
                # part of the model context and invalidate cached factual responses.
                model_result = {key: value for key, value in result.items()
                                if key not in {"searched_at", "refreshed_at"}}
                content = json.dumps(model_result, ensure_ascii=False, default=str)[:12000]
                status = "ok"
            except Exception as exc:  # noqa: BLE001 — tool failures degrade without leaking provider URLs.
                content = json.dumps({"error": type(exc).__name__})
                status = "error"
            engine_done = time.monotonic()
            trace.append({"tool": name, "args": arguments if status == "ok" else {},
                          "ms": round((time.monotonic() - start) * 1000, 1),
                          "provider": provider, "status": status, "cache_hit": cached})
            if model_message is not None:
                messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                 "name": name, "content": content})
        if model_message is None:
            break
    if not final or locale != "en":
        final = _source_draft(evidence, locale)
    # A model's facts never go directly to rendering or speech.
    checked = _safe_verify(final, evidence, searched="the linked sources")
    if checked["no_data"] and evidence:
        struck = checked["struck"]
        checked = _safe_verify(_source_draft(evidence, locale), evidence, searched="the linked sources")
        checked["struck"] = struck + checked["struck"]
    if checked["no_data"]:
        checked["message"] = _STRUCTURED[locale] if engine_result else _NO_DATA[locale]
    if streamed:
        checked["sentences"] = streamed + [row for row in checked["sentences"] if row not in streamed]
        checked["no_data"] = False
    checked["citations"] = {item.id: {"source_url": item.source_url,
                                     "fetched_at": item.fetched_at.isoformat()}
                            for item in evidence}
    return {"locale": locale, "provider": provider, "verification": checked,
            "cards": cards, "engine_result": engine_result, "trace": trace, "next_question": next_question,
            "profile_update": profile_update, "t_llm_response": llm_response,
            "t_llm_first_token": first_token,
            "t_engine_done": engine_done}
