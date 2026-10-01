"""Native function-call adapter with a small provider circuit breaker and cache."""

import hashlib
import json
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx

from daari.config import REPO_ROOT, cache_root, settings

_MODELS = (("gemini", "gemini-3.1-flash-lite"),
           ("groq", "openai/gpt-oss-120b"), ("ollama", "llama3.1:8b"))
_USER_AGENT = "DAARI/0.1 (https://github.com/dmrk22/asura)"
_failures: dict[str, int] = defaultdict(int)
_blocked_until: dict[str, float] = defaultdict(float)
TextSink = Callable[[str], Awaitable[None]]


def _cache_file(provider: str, model: str, messages: list[dict], tools: list[dict]) -> Path:
    stable = [{key: value for key, value in message.items() if key != "_first_token_at"}
              for message in messages]
    raw = json.dumps([provider, model, stable, tools], sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    directory = Path(settings.LLM_CACHE_DIR)
    if not directory.is_absolute():
        if settings.VERCEL and directory.parts[:1] == (".cache",):
            directory = cache_root(REPO_ROOT).joinpath(*directory.parts[1:])
        else:
            directory = REPO_ROOT / directory
    return directory / f"{digest}.json"


def _groq_messages(messages: list[dict]) -> list[dict]:
    allowed = {"role", "content", "tool_calls", "tool_call_id", "name"}
    return [{key: value for key, value in message.items() if key in allowed}
            for message in messages]


def _gemini_contents(messages: list[dict]) -> list[dict]:
    contents = []
    for message in messages:
        if message["role"] == "system":
            continue
        if message["role"] == "tool":
            parts = [{"functionResponse": {"id": message.get("tool_call_id", ""),
                                           "name": message["name"],
                                           "response": {"result": message["content"]}}}]
            role = "user"
        elif message.get("_gemini_parts"):
            # Gemini 3 thought signatures are opaque and must be returned unchanged
            # on the next function-result turn.
            parts = message["_gemini_parts"]
            role = "model"
        elif message.get("tool_calls"):
            parts = [{"functionCall": {"name": call["function"]["name"],
                                       "args": json.loads(call["function"]["arguments"])}}
                     for call in message["tool_calls"]]
            role = "model"
        else:
            parts = [{"text": message.get("content") or ""}]
            role = "model" if message["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": parts})
    return contents


def _parse_gemini(body: dict) -> dict:
    parts = body.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    calls = []
    text = []
    for index, part in enumerate(parts):
        if "functionCall" in part:
            item = part["functionCall"]
            calls.append({"id": item.get("id") or f"gemini-{index}", "type": "function",
                          "function": {"name": item["name"],
                                       "arguments": json.dumps(item.get("args") or {})}})
        elif isinstance(part.get("text"), str):
            text.append(part["text"])
    return {"role": "assistant", "content": "\n".join(text), "tool_calls": calls,
            "_gemini_parts": parts}


async def _stream_final(client: httpx.AsyncClient, provider: str, url: str,
                        on_text: TextSink | None = None, **kwargs: Any) -> dict:
    """Buffer final text for verification while measuring the first content token."""
    chunks: list[str] = []
    first_token: float | None = None
    async with client.stream("POST", url, **kwargs) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            event = json.loads(payload)
            if provider == "gemini":
                parts = event.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                pieces = [part["text"] for part in parts if isinstance(part.get("text"), str)]
            else:
                delta = event.get("choices", [{}])[0].get("delta", {})
                pieces = [delta["content"]] if isinstance(delta.get("content"), str) else []
            for piece in pieces:
                if piece:
                    if first_token is None:
                        first_token = time.monotonic()
                    chunks.append(piece)
                    if on_text:
                        await on_text(piece)
    return {"role": "assistant", "content": "".join(chunks), "tool_calls": [],
            "_first_token_at": first_token}


async def _request(provider: str, model: str, messages: list[dict], tools: list[dict],
                   on_text: TextSink | None = None) -> dict:
    final_only = any(message["role"] == "tool" for message in messages)
    async with httpx.AsyncClient(timeout=18, headers={"User-Agent": _USER_AGENT}) as client:
        if provider == "gemini":
            declarations = [{"name": t["name"], "description": t["description"],
                             "parameters": t["parameters"]} for t in tools]
            body = {"systemInstruction": {"parts": [{"text": messages[0]["content"]}]},
                    "contents": _gemini_contents(messages), "tools": [{"functionDeclarations": declarations}],
                    **({"toolConfig": {"functionCallingConfig": {"mode": "NONE"}}} if final_only else {}),
                    "generationConfig": {"temperature": 0}}
            if final_only:
                return await _stream_final(client, provider,
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent",
                    params={"key": settings.GEMINI_API_KEY, "alt": "sse"}, json=body, on_text=on_text)
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": settings.GEMINI_API_KEY},
                json=body,
            )
            response.raise_for_status()
            return _parse_gemini(response.json())
        payload: dict[str, Any] = {
            "model": model, "messages": _groq_messages(messages),
            "tools": [{"type": "function", "function": t} for t in tools],
            "tool_choice": "auto", "temperature": 0, "stream": False,
        }
        if final_only:
            # Groq's GPT-OSS currently returns HTTP 400 when tools are supplied
            # with tool_choice=none and it nevertheless emits a call. Omitting
            # declarations makes the final pass text-only.
            payload.pop("tools")
            payload.pop("tool_choice")
            payload["stream"] = True
        if provider == "groq":
            if final_only:
                return await _stream_final(client, provider,
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"}, json=payload, on_text=on_text)
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"}, json=payload,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]
        if final_only:
            # Ollama's OpenAI-compatible streaming endpoint uses the same SSE
            # delta shape as Groq.
            return await _stream_final(client, "groq", f"{settings.OLLAMA_BASE_URL}/v1/chat/completions",
                                       json=payload, on_text=on_text)
        response = await client.post(f"{settings.OLLAMA_BASE_URL}/v1/chat/completions", json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]


async def complete(messages: list[dict], tools: list[dict],
                   on_text: TextSink | None = None, *,
                   use_cache: bool = True) -> tuple[dict | None, str, bool]:
    """Return message, provider and cache hit; never expose provider error text."""
    for provider, model in _MODELS:
        if (provider == "gemini" and not settings.GEMINI_API_KEY) or (
            provider == "groq" and not settings.GROQ_API_KEY
        ):
            continue
        path = _cache_file(provider, model, messages, tools)
        if use_cache and path.exists():
            try:
                cached = json.loads(path.read_text())
                if cached.get("content"):
                    cached["_first_token_at"] = time.monotonic()
                    if on_text and not cached.get("tool_calls"):
                        await on_text("")
                        await on_text(cached["content"])
                return cached, provider, True
            except (OSError, ValueError):
                pass
        if time.monotonic() < _blocked_until[provider]:
            continue
        try:
            if on_text:
                await on_text("")
            message = (await _request(provider, model, messages, tools, on_text=on_text)
                       if on_text else await _request(provider, model, messages, tools))
            _failures[provider] = 0
            if use_cache:
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps({key: value for key, value in message.items()
                                                if key != "_first_token_at"}, ensure_ascii=False))
                except OSError:
                    pass
            return message, provider, False
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            _failures[provider] += 1
            if (isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429) or _failures[provider] >= 3:
                _blocked_until[provider] = time.monotonic() + 60
    return None, "unavailable", False
