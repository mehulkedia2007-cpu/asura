"""Run the P7 rehearsal and audit without inventing field evidence.

The audit is deterministic and offline. Field mode is opt-in: it requires a
reviewed microphone clip, its independently prepared transcript, and live
provider access. The clip is sent through the real ASR/agent/TTS path with all
local rehearsal caches bypassed. Missing prerequisites produce an explicit
``not_run`` or ``blocked`` result instead of a synthetic score.

Examples, from the repository root::

    uv run --project apps/api python evals/run_p7.py --audit
    uv run --project apps/api python evals/run_p7.py --audio clip.webm \
        --reference clip.txt --locale te --samples 1 --require-field
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import math
import re
import sys
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps/api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

MAX_AUDIO_BYTES = 4_500_000
MAX_SAMPLES = 20


def _words(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return re.findall(r"[\w\u0c00-\u0c7f\u0900-\u097f]+", normalized, re.UNICODE)


def _characters(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return [
        char
        for char in normalized
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    ]


def edit_distance(left: list[str], right: list[str]) -> int:
    """Levenshtein distance with no third-party ASR-eval dependency."""
    previous = list(range(len(right) + 1))
    for left_index, left_item in enumerate(left, 1):
        current = [left_index]
        for right_index, right_item in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_item != right_item),
                )
            )
        previous = current
    return previous[-1]


def transcript_metrics(reference: str, hypothesis: str) -> dict[str, Any]:
    """Return reproducible WER/CER and bounded 1-error accuracy indicators."""
    reference_words = _words(reference)
    hypothesis_words = _words(hypothesis)
    reference_chars = _characters(reference)
    hypothesis_chars = _characters(hypothesis)
    word_errors = edit_distance(reference_words, hypothesis_words)
    char_errors = edit_distance(reference_chars, hypothesis_chars)
    return {
        "reference_words": len(reference_words),
        "hypothesis_words": len(hypothesis_words),
        "word_errors": word_errors,
        "wer": round(word_errors / max(1, len(reference_words)), 4),
        "word_accuracy": round(
            max(0.0, 1.0 - word_errors / max(1, len(reference_words))), 4
        ),
        "reference_characters": len(reference_chars),
        "hypothesis_characters": len(hypothesis_chars),
        "character_errors": char_errors,
        "cer": round(char_errors / max(1, len(reference_chars)), 4),
        "character_accuracy": round(
            max(0.0, 1.0 - char_errors / max(1, len(reference_chars))), 4
        ),
    }


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _p7_ready(audit: dict[str, Any], field: dict[str, Any]) -> bool:
    """Report P7's phase gate without implying that the full build is ready."""
    return bool(
        audit.get("passed")
        and field.get("status") == "measured"
        and field.get("reference_transcript_independently_reviewed") is True
    )


def _audit() -> dict[str, Any]:
    """Exercise the safety boundaries and collect existing regression reports."""
    from daari_core.assess import Item, next_item, should_stop, start, update
    from daari_core.scam import score

    from daari.evidence import (
        _constitution,
        _fixture_evidence,
        _grounding_metrics,
        _i18n,
        _import_graph,
        _match_ablations,
        _roadmap_invariants,
        _scam_metrics,
        _scheme_metrics,
    )
    from daari.grounding.verifier import verify
    from daari.prep.notice import extract

    invented = verify("Guaranteed placement at 90000.", [])
    forbidden = verify("Pay a fee to apply.", [])
    notice = extract(
        "Company: TCS\nRole: Prime\nInterview date: 2026-10-04\n"
        "Contact: Ravi Kumar 9876543210\nEmail: person@example.test",
    )
    notice_serialized = json.dumps(notice, ensure_ascii=False)
    localized_scam = {
        "telugu_fee": score("రిజిస్ట్రేషన్ ఫీజు చెల్లించండి", "Example Ltd").badge == "red",
        "hindi_fee": score("पंजीकरण शुल्क भुगतान करें", "Example Ltd").badge == "red",
        "telugu_no_fee": score("ఫీజు లేదు. దరఖాస్తు సమర్పించండి", "Example Ltd").badge
        == "none",
        "telugu_whatsapp_only": "WhatsApp"
        in " ".join(score("వాట్సాప్ ద్వారా మాత్రమే సంప్రదించండి", "Example Ltd").reasons),
    }
    bank = [
        Item(str(index), "sql_querying", float(index % 3), "q", "a", "fixture")
        for index in range(6)
    ]
    state = start()
    for index in range(6):
        item = next_item(state, bank)
        assert item is not None
        state = update(state, item, index % 2 == 0)
    checks = {
        "invented_number_struck": bool(invented["no_data"] and invented["struck"]),
        "forbidden_payment_struck": bool(forbidden["no_data"] and forbidden["struck"]),
        "notice_personal_data_removed": not any(
            value in notice_serialized
            for value in ("Ravi", "9876543210", "person@example.test")
        ),
        "cat_terminates_at_six": len(state.answered) == 6
        and should_stop(state, max_items=6),
        **localized_scam,
    }
    verifier_values = []
    for case in [
        json.loads(line)
        for line in (ROOT / "evals/grounding_golden.jsonl").read_text().splitlines()
        if line.strip()
    ]:
        started = time.perf_counter()
        verify(case["draft"], _fixture_evidence(case["evidence"]))
        verifier_values.append((time.perf_counter() - started) * 1000)
    verifier_p95 = _percentile(verifier_values, 0.95)
    p5 = _json(ROOT / "evals/p5_report.json")
    p4 = _json(ROOT / "evals/p4_report.json")
    p3 = {
        "scheme_retrieval": _scheme_metrics(),
        "scam": _scam_metrics(),
        "grounding": _grounding_metrics(),
    }
    audit = {
        "passed": all(checks.values()),
        "checks": checks,
        "verifier": {
            "samples": len(verifier_values),
            "p95_ms": round(verifier_p95 or 0, 3),
            "gate_ms": 400,
            "passed": bool(verifier_p95 is not None and verifier_p95 < 400),
        },
        "shared_engine": _import_graph(),
        "roadmap": _roadmap_invariants(),
        "match_ablations": _match_ablations(),
        "i18n": _i18n(),
        "constitution": _constitution(),
        "regressions": {"p3": p3, "p4": p4, "p5": p5},
    }
    audit["passed"] = bool(
        audit["passed"]
        and audit["verifier"]["passed"]
        and audit["shared_engine"]["status"] == "green"
        and audit["roadmap"]["passed"]
        and audit["match_ablations"]["passed"]
        and audit["i18n"]["passed"]
        and p3["scheme_retrieval"]["passed"]
        and p3["scam"]["passed"]
        and p3["grounding"]["passed"]
        and p4.get("status") == "complete"
        and p4.get("cached_browser", {}).get("passed") is True
        and p4.get("cached_server", {}).get("passed") is True
        and p5["passed"]
    )
    return audit


class _Sink:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def send_json(self, data: dict[str, Any]) -> None:
        self.events.append(data)


async def _field_rehearsal(args: argparse.Namespace) -> dict[str, Any]:
    source = args.source
    if not args.audio or not args.reference:
        return {
            "status": "not_run",
            "source": source,
            "reason": "reviewed microphone audio and an independent reference transcript are required",
            "scope": "real microphone clip, not synthetic Web Audio or cached rehearsal",
        }
    if args.locale != "te":
        return {
            "status": "blocked",
            "source": source,
            "reason": "P7 field accuracy is scoped to independently reviewed Telugu microphone clips",
        }
    audio_path = Path(args.audio)
    reference_path = Path(args.reference)
    if not audio_path.is_file() or not reference_path.is_file():
        return {
            "status": "blocked",
            "source": source,
            "reason": "audio or reference path does not exist",
        }
    audio = audio_path.read_bytes()
    reference = reference_path.read_text(encoding="utf-8").strip()
    if not audio or not reference:
        return {
            "status": "blocked",
            "source": source,
            "reason": "audio and reference transcript must be nonempty",
        }
    if len(audio) > MAX_AUDIO_BYTES:
        return {
            "status": "blocked",
            "source": source,
            "reason": f"audio exceeds the {MAX_AUDIO_BYTES}-byte rehearsal limit",
        }
    if source == "reviewed_microphone" and not args.reviewed:
        return {
            "status": "blocked",
            "source": source,
            "reason": "explicit --reviewed attestation is required for field evidence",
        }
    if source == "reviewed_microphone" and not args.review_note.strip():
        return {
            "status": "blocked",
            "source": source,
            "reason": "--review-note must identify the independent review evidence",
        }

    from daari.p4 import _turn

    mime = {
        ".webm": "audio/webm",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
    }.get(audio_path.suffix.casefold(), "application/octet-stream")
    rows: list[dict[str, Any]] = []
    for _ in range(args.samples):
        sink = _Sink()
        started = time.monotonic()
        await _turn(
            sink,
            {
                "audio": base64.b64encode(audio).decode(),
                "mime": mime,
                "bypass_cache": True,
                "request": {"text": "voice input", "locale": "te", "persona": "rural"},
            },
        )
        elapsed_ms = round((time.monotonic() - started) * 1000, 1)
        transcript_event = next(
            (event for event in sink.events if event.get("type") == "transcript"), None
        )
        done_event = next(
            (event for event in sink.events if event.get("type") == "done"), None
        )
        hypothesis = str((transcript_event or {}).get("text") or "")
        provider = (transcript_event or {}).get("provider", "unavailable")
        row: dict[str, Any] = {
            "asr_provider": provider,
            "transcript_metrics": transcript_metrics(reference, hypothesis)
            if hypothesis
            else None,
            "elapsed_ms": elapsed_ms,
            "event_types": [event.get("type") for event in sink.events],
        }
        if done_event:
            stamps = done_event.get("stamps_ms") or {}
            row["first_audio_ms"] = stamps.get("t_audio_first_chunk")
            row["total_ms"] = stamps.get("t_done")
            row["stages_ms"] = {
                str(key): value
                for key, value in stamps.items()
                if key != "t_release" and isinstance(value, (int, float))
            }
        rows.append(row)

    asr_rows = [
        row
        for row in rows
        if row["asr_provider"] == "groq" and row["transcript_metrics"]
    ]
    latency_rows = [
        row
        for row in rows
        if row.get("first_audio_ms") is not None and row.get("total_ms") is not None
    ]
    asr = {
        "status": "measured" if asr_rows else "blocked",
        "provider": sorted({row["asr_provider"] for row in rows}),
        "samples": len(asr_rows),
        "word_accuracy_mean": round(
            sum(row["transcript_metrics"]["word_accuracy"] for row in asr_rows)
            / len(asr_rows),
            4,
        )
        if asr_rows
        else None,
        "wer_mean": round(
            sum(row["transcript_metrics"]["wer"] for row in asr_rows) / len(asr_rows), 4
        )
        if asr_rows
        else None,
        "cer_mean": round(
            sum(row["transcript_metrics"]["cer"] for row in asr_rows) / len(asr_rows), 4
        )
        if asr_rows
        else None,
        "reason": None
        if asr_rows
        else "Groq ASR did not return a live transcript; cached/browser fallback is not field accuracy",
    }
    latency = {
        "status": "measured" if latency_rows else "blocked",
        "samples": len(latency_rows),
        "first_audio_p95_ms": _percentile(
            [row["first_audio_ms"] for row in latency_rows], 0.95
        ),
        "total_p95_ms": _percentile([row["total_ms"] for row in latency_rows], 0.95),
        "passed_voice_thresholds": bool(
            latency_rows
            and (
                _percentile([row["first_audio_ms"] for row in latency_rows], 0.95) or 0
            )
            < 1500
            and (_percentile([row["total_ms"] for row in latency_rows], 0.95) or 0)
            < 4000
        ),
        "reason": None
        if latency_rows
        else "uncached full voice turn did not deliver real audio and a done event",
    }
    measured = bool(asr_rows and latency_rows)
    return {
        "status": "rehearsal_only"
        if measured and source == "synthetic_rehearsal"
        else "measured"
        if measured
        else "blocked",
        "source": source,
        "scope": "ASR and full agent/TTS caches bypassed",
        "reference_transcript_independently_reviewed": source == "reviewed_microphone"
        and args.reviewed,
        "review_note": args.review_note if args.reviewed else None,
        "asr": asr,
        "latency": latency,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit", action="store_true", help="run the deterministic red-team audit"
    )
    parser.add_argument(
        "--audio", help="reviewed microphone clip for live Telugu rehearsal"
    )
    parser.add_argument(
        "--reference", help="independently reviewed transcript for --audio"
    )
    parser.add_argument(
        "--source",
        choices=("reviewed_microphone", "synthetic_rehearsal"),
        default="reviewed_microphone",
        help="classify the clip; synthetic rehearsal cannot unlock field completion",
    )
    parser.add_argument(
        "--reviewed",
        action="store_true",
        help="attest that a reviewer independently checked the Telugu mic clip and transcript",
    )
    parser.add_argument(
        "--review-note",
        default="",
        help="brief provenance for the independent recording/transcript review",
    )
    parser.add_argument("--locale", choices=("en", "te", "hi"), default="te")
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument(
        "--require-field",
        action="store_true",
        help="exit nonzero unless field mode measures live ASR and audio",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "evals/p7_report.json")
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be positive")
    if args.samples > MAX_SAMPLES:
        parser.error(f"--samples cannot exceed {MAX_SAMPLES}")
    audit = _audit()
    field = asyncio.run(_field_rehearsal(args))
    report = {
        "phase": "P7",
        "checked_at": datetime.now(UTC).isoformat(),
        "scope": "Rehearsal and audit; cached regressions are not field validation.",
        "audit": audit,
        "field_rehearsal": field,
        "readiness": {
            "p7_phase": "ready" if _p7_ready(audit, field) else "open",
            "full_build": "open",
            "open_gates": [
                "P2 taxonomy, role and CAT-bank breadth",
                "P2 multilingual learned embeddings",
                "P3 live-index precision and source breadth",
            ],
        },
    }
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not audit["passed"]:
        return 1
    if args.require_field and field["status"] != "measured":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
