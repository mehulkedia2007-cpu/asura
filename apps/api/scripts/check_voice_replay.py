"""Warm a reviewed clip, or measure its real cached voice turn without HTTP/TTS egress.

Run from apps/api: .venv/bin/python scripts/check_voice_replay.py --help
Local Postgres remains available. No tool or model outputs are substituted.
"""

import argparse
import asyncio
import base64
import json
import math
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from daari.p4 import _turn
from daari.voice.asr import register_rehearsal


class Sink:
    def __init__(self, progress=False):
        self.events: list[dict] = []
        self.progress = progress

    async def send_json(self, data: dict) -> None:
        self.events.append(data)
        if self.progress:
            print(json.dumps({"event": data["type"]}), flush=True)


async def deny_http(*args, **kwargs):
    raise httpx.ConnectError("offline rehearsal")


def deny_tts(*args, **kwargs):
    raise ConnectionError("offline rehearsal")


async def main(args):
    audio = args.audio.read_bytes()
    transcript = args.transcript.read_text().strip()
    if args.warm:
        register_rehearsal(audio, transcript, args.locale)
    rows = []
    with ExitStack() as stack:
        if not args.warm:
            stack.enter_context(patch("httpx.AsyncClient.send", deny_http))
            stack.enter_context(patch("edge_tts.Communicate", deny_tts))
        for _ in range(1 if args.warm else args.samples):
            sink = Sink(progress=args.warm)
            await _turn(sink, {"audio": base64.b64encode(audio).decode(), "mime": args.mime,
                               "request": {"text": "voice input", "locale": args.locale}})
            events = sink.events
            done = next((event for event in events if event["type"] == "done"), None)
            result = next((event["result"] for event in events if event["type"] == "result"), {})
            trace = result.get("trace", [])
            valid = (done and any(event["type"] == "audio" for event in events)
                     and not any(event["type"] in {"error", "browser_tts"} for event in events)
                     and trace and all(row["status"] == "ok" for row in trace)
                     and (result.get("cards") or result.get("engine_result"))
                     and events[0].get("provider") == "rehearsal_cache")
            if not valid:
                print(json.dumps({"passed": False, "events": [event["type"] for event in events],
                                  "trace": trace}, ensure_ascii=False))
                return 1
            assert done is not None
            rows.append(done["stamps_ms"])
    metrics = {}
    for key in ("t_audio_first_chunk", "t_done"):
        values = sorted(row[key] for row in rows)
        metrics[key] = {"n": len(values), "p50_ms": values[math.ceil(len(values) * .5) - 1],
                        "p95_ms": values[math.ceil(len(values) * .95) - 1]}
    passed = (metrics["t_audio_first_chunk"]["p95_ms"] < 1500
              and metrics["t_done"]["p95_ms"] < 4000)
    print(json.dumps({"mode": "warm" if args.warm else "http_and_tts_blocked",
                      "locale": args.locale, "metrics": metrics, "passed": passed,
                      "scope": "server release to audio delivery; excludes browser playback"}))
    return 0 if args.warm or passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--locale", choices=("en", "te", "hi"), default="te")
    parser.add_argument("--mime", default="audio/mpeg")
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--warm", action="store_true")
    options = parser.parse_args()
    if options.samples < 1:
        parser.error("--samples must be positive")
    raise SystemExit(asyncio.run(main(options)))
