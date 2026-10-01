"""P4 boundaries: tool facts, language, and verified speech events."""

from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from daari.agent import llm, loop
from daari.agent.llm import _gemini_contents, _groq_messages, _parse_gemini
from daari.main import app
from daari.voice import asr, tts
from daari.voice.lang import detect
from daari.voice.latency import record, summary
from daari.voice.stream import Sentences


def test_sentence_stream_keeps_incomplete_tail_and_decimal_together():
    splitter = Sentences()
    assert splitter.push("Pay is 3.") == []
    assert splitter.push("5 units. Next") == ["Pay is 3.5 units."]
    assert splitter.push(" line\nచివరి వాక్యం") == ["Next line"]
    assert splitter.push("", final=True) == ["చివరి వాక్యం"]


def test_localized_source_label_preserves_title_without_inventing_translation():
    evidence, cards = loop._evidence("search_jobs", {"leads": [{
        "title": "SQL analyst", "source_url": "https://example.gov/job",
        "fetched_at": datetime.now(UTC).isoformat(),
    }]}, "te")
    assert loop._source_draft(evidence, "te") == "ఉద్యోగం: SQL analyst"
    assert cards[0]["title"] == "SQL analyst"
    assert loop.verify(loop._source_draft(evidence, "te"), evidence)["no_data"] is False


@pytest.mark.asyncio
async def test_agent_streams_only_evidence_before_final_response(monkeypatch):
    spoken = []
    calls = 0

    async def say(text):
        spoken.append(text)

    async def model(messages, tools, on_text=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"role": "assistant", "tool_calls": [{"id": "1", "function": {
                "name": "search_jobs", "arguments": '{"query":"analyst"}'}}]}, "gemini", False
        assert on_text is not None
        await on_text("Invented salary 90000.\nSQL analyst.\n")
        assert spoken == ["SQL analyst."]  # callback ran before model completion
        return {"role": "assistant", "content": "Invented salary 90000.\nSQL analyst."}, "gemini", False

    async def sourced_jobs(name, args, request):
        return {"leads": [{"title": "SQL analyst.", "source_url": "https://example.gov/job",
                           "fetched_at": datetime.now(UTC).isoformat()}]}

    monkeypatch.setattr(loop, "complete", model)
    monkeypatch.setattr(loop, "_execute", sourced_jobs)
    result = await loop.run(loop.AgentRequest(text="Find analyst jobs"), on_sentence=say)
    assert result["verification"]["struck"][0]["text"] == "Invented salary 90000."
    assert [row["text"] for row in result["verification"]["sentences"]] == spoken


def test_verifier_exception_fails_closed_to_no_prose(monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("guard unavailable")

    monkeypatch.setattr(loop, "verify", unavailable)
    checked = loop._safe_verify("Unverified claim.", [], "the linked sources")
    assert checked["no_data"] is True
    assert checked["sentences"] == []
    assert checked["struck"] == [{"reason": "verifier_unavailable"}]


def test_voice_barge_in_cancels_model_work(monkeypatch):
    import asyncio
    import threading

    stopped = threading.Event()

    async def pending_run(request, on_sentence=None):
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr("daari.p4.run", pending_run)
    with TestClient(app).websocket_connect("/ws/voice") as socket:
        socket.send_json({"type": "release", "request": {"text": "voice"}, "browser_final": "jobs"})
        assert socket.receive_json()["type"] == "transcript"
        socket.send_json({"type": "cancel"})
        assert socket.receive_json()["type"] == "cancelled"
        assert stopped.wait(1)


def test_voice_delivers_streamed_audio_before_final_result(monkeypatch):
    async def streaming_run(request, on_sentence=None):
        assert on_sentence is not None
        await on_sentence("SQL analyst.")
        return {"locale": "en", "verification": {"no_data": False,
                "sentences": [{"text": "SQL analyst."}]},
                "t_llm_response": None, "t_engine_done": 0.0}

    async def audio(text, locale):
        return b"mp3"

    monkeypatch.setattr("daari.p4.run", streaming_run)
    monkeypatch.setattr("daari.p4.synthesize", audio)
    with TestClient(app).websocket_connect("/ws/voice") as socket:
        socket.send_json({"type": "release", "request": {"text": "voice"}, "browser_final": "jobs"})
        events = [socket.receive_json() for _ in range(5)]
    assert [event["type"] for event in events] == ["transcript", "sentence", "audio", "result", "done"]


def test_language_detection_keeps_tenglish_in_selected_language():
    assert detect("నాకు పని కావాలి", "en") == "te"
    assert detect("मुझे नौकरी चाहिए", "en") == "hi"
    assert detect("naku job kavali", "te") == "te"


def test_gemini_function_round_trip_preserves_opaque_signature():
    parsed = _parse_gemini({"candidates": [{"content": {"parts": [
        {"functionCall": {"id": "call-1", "name": "search_jobs", "args": {"query": "driver"}},
         "thoughtSignature": "opaque"}]}}]})
    assert parsed["tool_calls"][0]["id"] == "call-1"
    contents = _gemini_contents([
        {"role": "system", "content": "tools"},
        {"role": "user", "content": "jobs"}, parsed,
        {"role": "tool", "name": "search_jobs", "tool_call_id": "call-1", "content": "{}"},
    ])
    assert contents[1]["parts"][0]["thoughtSignature"] == "opaque"
    assert contents[2]["parts"][0]["functionResponse"]["id"] == "call-1"
    assert "_gemini_parts" not in _groq_messages([parsed])[0]


@pytest.mark.asyncio
async def test_agent_responds_to_every_model_tool_call(monkeypatch):
    calls = [{"id": f"call-{index}", "function": {"name": "get_roadmap", "arguments": "{}"}}
             for index in range(3)]
    seen_messages = []

    async def fake_complete(messages, tools):
        seen_messages.append(messages.copy())
        if len(seen_messages) == 1:
            return {"role": "assistant", "content": None, "tool_calls": calls}, "groq", False
        return {"role": "assistant", "content": "No data", "tool_calls": []}, "groq", False

    async def fake_execute(name, args, request):
        return {"goal": "data_analyst", "steps": []}

    monkeypatch.setattr(loop, "complete", fake_complete)
    monkeypatch.setattr(loop, "_execute", fake_execute)
    result = await loop.run(loop.AgentRequest(text="Give me a path"))
    assert len([message for message in seen_messages[1] if message["role"] == "tool"]) == 3
    assert len(result["trace"]) == 3


@pytest.mark.asyncio
async def test_groq_final_pass_omits_tools_after_tool_result(monkeypatch):
    sent = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    async def fake_stream(client, provider, url, **kwargs):
        sent.append(kwargs["json"])
        return {"role": "assistant", "content": "hello", "tool_calls": []}

    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    monkeypatch.setattr(llm, "_stream_final", fake_stream)
    messages = [{"role": "system", "content": "dummy"}, {"role": "user", "content": "hello"},
                {"role": "tool", "tool_call_id": "c1", "name": "echo_word", "content": "hello"}]
    await llm._request("groq", "openai/gpt-oss-120b", messages, [{"name": "echo_word"}])
    assert "tools" not in sent[0] and "tool_choice" not in sent[0]
    assert sent[0]["stream"] is True


@pytest.mark.asyncio
async def test_streamed_final_records_first_text_token():
    payload = 'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\ndata: {"choices":[{"delta":{"content":" there"}}]}\n\ndata: [DONE]\n\n'
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200, content=payload.encode(), headers={"content-type": "text/event-stream"}, request=request))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await llm._stream_final(client, "groq", "https://example.com/test", json={})
    assert result["content"] == "Hello there"
    assert result["_first_token_at"] is not None


def test_slot_value_parses_indic_digits_without_guessing_words():
    assert loop._slot_value("annual_income", "₹૨,૦૦,૦૦૦") == 200000
    assert loop._slot_value("annual_income", "2 lakh") == 200000
    assert loop._slot_value("annual_income", "two lakh") is None
    assert loop._slot_value("bpl", "అవును") is True


def test_offline_job_fallback_uses_search_terms_instead_of_whole_sentence():
    assert loop._fallback("నాకు గుంటూరు దగ్గర పని కావాలి") == ("search_jobs", {"query": "jobs"})
    assert loop._fallback("Find driver jobs") == ("search_jobs", {"query": "driver"})


def test_offline_roadmap_fallback_recognizes_all_product_languages():
    for request in (
        "Show my roadmap to become a data analyst",
        "డేటా అనలిస్ట్ కోసం నా అభ్యాస ప్రణాళిక చూపించు",
        "डेटा एनालिस्ट बनने के लिए मेरा रोडमैप दिखाओ",
        "मेरी अध्ययन योजना दिखाओ",
    ):
        assert loop._fallback(request) == ("get_roadmap", {})


@pytest.mark.asyncio
async def test_clear_hindi_roadmap_request_executes_when_provider_returns_only_prose(monkeypatch):
    async def prose_only(*args, **kwargs):
        return {"content": "Here is your roadmap", "tool_calls": []}, "test", False

    monkeypatch.setattr(loop, "complete", prose_only)
    result = await loop.run(loop.AgentRequest(
        text="डेटा एनालिस्ट बनने के लिए मेरा रोडमैप दिखाओ", locale="hi", goal="data_analyst",
    ))
    assert result["engine_result"]["kind"] == "get_roadmap"
    assert result["trace"][0]["status"] == "ok"
    assert result["engine_result"]["data"]["total_hours"] > 0


@pytest.mark.asyncio
async def test_agent_falls_back_to_source_title_and_cites_it(monkeypatch):
    async def no_provider(messages, tools):
        return None, "unavailable", False

    async def sourced_jobs(name, args, request):
        assert name == "search_jobs"
        return {"leads": [{"title": "SQL analyst", "source_url": "https://www.adzuna.com/jobs/42",
                           "fetched_at": datetime.now(UTC).isoformat(), "scam": {"badge": "none"}}]}

    monkeypatch.setattr(loop, "complete", no_provider)
    monkeypatch.setattr(loop, "_execute", sourced_jobs)
    result = await loop.run(loop.AgentRequest(text="Find a job near Guntur"))
    assert result["verification"]["sentences"] == [
        {"text": "SQL analyst", "citation_ids": ["search_jobs:0"]}]
    assert result["trace"][0]["tool"] == "search_jobs"
    assert result["cards"][0]["source_url"].startswith("https://")


@pytest.mark.asyncio
async def test_path_tool_returns_structured_result_without_unverified_prose(monkeypatch):
    async def no_provider(messages, tools):
        return None, "unavailable", False

    async def computed_path(name, args, request):
        return {"steps": [{"skill": "sql_querying", "label_en": "SQL",
                           "label_te": "ఎస్క్యూఎల్", "label_hi": "एसक्यूएल", "hours": 20}]}

    monkeypatch.setattr(loop, "complete", no_provider)
    monkeypatch.setattr(loop, "_execute", computed_path)
    result = await loop.run(loop.AgentRequest(text="Show my path", locale="te"))
    assert result["engine_result"]["kind"] == "get_roadmap"
    assert result["verification"]["sentences"] == []
    assert result["verification"]["message"] == "లెక్కించిన ఫలితాన్ని కింద చూడండి."


@pytest.mark.asyncio
async def test_model_invention_is_struck_before_voice(monkeypatch):
    async def invented(messages, tools):
        return {"role": "assistant", "content": "Guaranteed placement at ₹90000.", "tool_calls": []}, "groq", False

    monkeypatch.setattr(loop, "complete", invented)
    result = await loop.run(loop.AgentRequest(text="Tell me the salary"))
    assert result["verification"]["no_data"]
    assert result["verification"]["struck"][0]["reason"] == "unsupported" or result["verification"]["struck"][0]["reason"] == "forbidden_claim"


@pytest.mark.asyncio
async def test_spoken_slot_answer_rechecks_scheme_with_updated_profile(monkeypatch):
    seen = []

    async def no_provider(messages, tools):
        return None, "unavailable", False

    async def scheme_result(name, args, request):
        seen.append(request.profile.copy())
        return {"schemes": [{"name_te": "నమూనా పథకం", "name_en": "Sample scheme",
                             "url": "https://www.myscheme.gov.in/schemes/sample",
                             "fetched_at": datetime.now(UTC).isoformat(),
                             "eligibility": {"status": "unknown" if len(seen) == 1 else "true"}}],
                "next_question": {"field": "annual_income"} if len(seen) == 1 else None}

    monkeypatch.setattr(loop, "complete", no_provider)
    monkeypatch.setattr(loop, "_execute", scheme_result)
    first = await loop.run(loop.AgentRequest(text="నాకు పథకం కావాలి", locale="te"))
    assert first["next_question"]["field"] == "annual_income"
    second = await loop.run(loop.AgentRequest(
        text="₹2,00,000", locale="te", pending_field="annual_income",
        pending_query=first["next_question"]["query"], profile={"state": "Andhra Pradesh"}))
    assert seen[1]["annual_income"] == 200000
    assert second["profile_update"] == {"annual_income": 200000}
    assert second["cards"][0]["eligibility"]["status"] == "true"


def test_voice_socket_sends_only_verified_sentence(monkeypatch):
    async def fake_asr(audio, mime, locale, browser_final):
        return browser_final, "browser"

    async def fake_run(request, on_sentence=None):
        now = datetime.now(UTC).isoformat()
        return {"locale": "te", "provider": "cached", "cards": [], "trace": [],
                "verification": {"sentences": [{"text": "నైపుణ్యం", "citation_ids": ["e1"]}],
                                 "struck": [{"text": "Invented claim", "reason": "unsupported"}],
                                 "no_data": False, "citations": {"e1": {"source_url": "https://example.gov",
                                                                    "fetched_at": now}}},
                "t_llm_response": None, "t_engine_done": 0.0}

    async def fake_tts(sentence, locale):
        assert sentence == "నైపుణ్యం"
        return b"mp3"

    monkeypatch.setattr("daari.p4.transcribe", fake_asr)
    monkeypatch.setattr("daari.p4.run", fake_run)
    monkeypatch.setattr("daari.p4.synthesize", fake_tts)
    with TestClient(app).websocket_connect("/ws/voice") as socket:
        socket.send_json({"type": "release", "request": {"text": "voice input", "locale": "te"},
                          "browser_final": "పని", "audio": ""})
        events = [socket.receive_json() for _ in range(5)]
    assert [event["type"] for event in events] == ["transcript", "result", "sentence", "audio", "done"]
    assert events[2]["text"] == "నైపుణ్యం"
    assert events[3]["data"] == "bXAz"
    assert events[4]["stamps_ms"]["t_audio_first_chunk"] >= 0


def test_latency_percentiles_are_measured_from_release():
    measured = record({"t_release": 10, "t_asr_final": 10.2, "t_audio_first_chunk": 10.9})
    assert measured["t_asr_final"] == 200
    assert summary()["t_audio_first_chunk"]["p95"] >= 900


@pytest.mark.asyncio
async def test_llm_cache_survives_circuit_breaker_and_transient_token_stamp(monkeypatch, tmp_path):
    import json
    import time

    monkeypatch.setattr(llm, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(llm, "_blocked_until", {"gemini": time.monotonic() + 60})
    messages = [{"role": "assistant", "content": "source", "_first_token_at": 10}]
    path = llm._cache_file("gemini", llm._MODELS[0][1], messages, [])
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"role": "assistant", "content": "cached answer"}))
    messages[0]["_first_token_at"] = 20
    message, provider, cached = await llm.complete(messages, [])
    assert message and message["content"] == "cached answer"
    assert provider == "gemini" and cached


@pytest.mark.asyncio
async def test_cached_sentence_audio_works_without_edge_connection(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, "REPO_ROOT", tmp_path)
    path = tts._cache_path("ధృవీకరించిన సమాధానం", "te", tts.settings.TTS_VOICE_TE)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"cached-mp3")

    class OfflineEdge:
        def __init__(self, *args, **kwargs):
            raise AssertionError("network TTS should not be called")

    monkeypatch.setattr(tts.edge_tts, "Communicate", OfflineEdge)
    assert await tts.synthesize("ధృవీకరించిన సమాధానం", "te") == b"cached-mp3"


@pytest.mark.asyncio
async def test_rehearsal_asr_cache_requires_exact_clip_and_locale(monkeypatch, tmp_path):
    monkeypatch.setattr(asr, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(asr.settings, "GROQ_API_KEY", None)
    asr.register_rehearsal(b"reviewed-audio", "నాకు పని కావాలి", "te")
    assert await asr.transcribe(b"reviewed-audio", "audio/webm", "te") == (
        "నాకు పని కావాలి", "rehearsal_cache")
    assert (await asr.transcribe(b"reviewed-audio", "audio/webm", "hi", "browser final"))[1] != "rehearsal_cache"
    assert await asr.transcribe(b"different", "audio/webm", "te", "browser final") == (
        "browser final", "browser")
