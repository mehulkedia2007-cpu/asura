"""P4 text agent and cancelable voice session."""

import asyncio
import base64
import binascii
import time
from typing import Protocol

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from daari.agent.loop import AgentRequest, run
from daari.voice.asr import transcribe
from daari.voice.lang import detect
from daari.voice.latency import record, summary
from daari.voice.tts import synthesize

router = APIRouter(tags=["P4 agent and voice"])


class EventSink(Protocol):
    async def send_json(self, data: dict) -> None: ...


@router.post("/agent/chat")
async def chat(request: AgentRequest) -> dict:
    result = await run(request)
    result.pop("t_llm_response")
    result.pop("t_llm_first_token")
    result.pop("t_engine_done")
    return result


@router.get("/voice/latency")
def latency() -> dict:
    return {"samples": summary()}


async def _turn(ws: EventSink, message: dict, released_at: float | None = None) -> None:
    stamps = {"t_release": released_at or time.monotonic()}
    bypass_cache = bool(message.get("bypass_cache", False))
    try:
        encoded = str(message.get("audio") or "")
        if len(encoded) > 6_000_000:
            await ws.send_json({"type": "error", "detail": "audio_too_large"})
            return
        audio = base64.b64decode(encoded, validate=True) if encoded else b""
        request = AgentRequest.model_validate(message.get("request") or {})
        if bypass_cache:
            transcript, asr_provider = await transcribe(
                audio, str(message.get("mime") or "audio/webm"), request.locale,
                str(message.get("browser_final") or ""), allow_rehearsal_cache=False,
            )
        else:
            transcript, asr_provider = await transcribe(
                audio, str(message.get("mime") or "audio/webm"), request.locale,
                str(message.get("browser_final") or ""),
            )
        stamps["t_asr_final"] = time.monotonic()
        await ws.send_json({"type": "transcript", "text": transcript, "provider": asr_provider})
        if not transcript:
            await ws.send_json({"type": "error", "detail": "no_transcript"})
            return
        if len(transcript) > 500:
            await ws.send_json({"type": "error", "detail": "transcript_too_long"})
            return
        request = request.model_copy(update={"text": transcript})
        locale = detect(transcript, request.locale)
        emitted: set[str] = set()

        async def speak(sentence: str) -> None:
            if sentence in emitted:
                return
            index = len(emitted)
            emitted.add(sentence)
            # Callback is invoked only for an evidence-verified complete sentence.
            await ws.send_json({"type": "sentence", "index": index, "text": sentence})
            chunk = await synthesize(sentence, locale, use_cache=False) if bypass_cache else await synthesize(sentence, locale)
            if chunk:
                if "t_audio_first_chunk" not in stamps:
                    stamps["t_audio_first_chunk"] = time.monotonic()
                await ws.send_json({"type": "audio", "index": index, "mime": "audio/mpeg",
                                    "data": base64.b64encode(chunk).decode()})
            else:
                await ws.send_json({"type": "browser_tts", "index": index, "text": sentence,
                                    "locale": locale})

        if bypass_cache:
            result = await asyncio.wait_for(
                run(request, on_sentence=speak, bypass_cache=True), timeout=90,
            )
        else:
            result = await asyncio.wait_for(run(request, on_sentence=speak), timeout=90)
        first_token = result.pop("t_llm_first_token", None)
        if first_token is not None:
            stamps["t_llm_first_token"] = first_token
        llm_response = result.pop("t_llm_response")
        if llm_response is not None:
            stamps["t_llm_response"] = llm_response
        stamps["t_engine_done"] = result.pop("t_engine_done")
        await ws.send_json({"type": "result", "result": result})
        checked = result["verification"]
        spoken = [row["text"] for row in checked["sentences"]] if not checked["no_data"] else [checked["message"]]
        if result.get("next_question") and result["next_question"]["text"] not in spoken:
            spoken.append(result["next_question"]["text"])
        for sentence in spoken:
            await speak(sentence)
        stamps["t_done"] = time.monotonic()
        await ws.send_json({"type": "done", "stamps_ms": record(stamps), "summary_ms": summary()})
    except (ValidationError, ValueError, binascii.Error):
        await ws.send_json({"type": "error", "detail": "invalid_request"})
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001 — boundary must not leak provider exceptions or secrets.
        await ws.send_json({"type": "error", "detail": "agent_unavailable"})


@router.websocket("/ws/voice")
async def voice(ws: WebSocket) -> None:
    await ws.accept()
    task: asyncio.Task | None = None
    released_at: float | None = None
    try:
        while True:
            message = await ws.receive_json()
            kind = message.get("type")
            if kind == "release_start":
                released_at = time.monotonic()
            if kind in {"cancel", "release"} and task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                task = None
            if kind == "release":
                task = asyncio.create_task(_turn(ws, message, released_at))
                released_at = None
            elif kind == "interim":
                await ws.send_json({"type": "interim", "text": str(message.get("text") or "")[:500]})
            elif kind == "cancel":
                await ws.send_json({"type": "cancelled"})
    except WebSocketDisconnect:
        pass
    finally:
        if task and not task.done():
            task.cancel()
