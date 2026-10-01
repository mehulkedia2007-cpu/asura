"""P7 rehearsal helpers never turn missing field evidence into a pass."""

import json
import sys
from argparse import Namespace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evals"))

from run_p7 import (  # pyright: ignore[reportMissingImports]
    _field_rehearsal,
    _p7_ready,
    transcript_metrics,
)

from daari.voice import asr


def test_transcript_metrics_reports_word_and_character_errors():
    result = transcript_metrics("నాకు పని కావాలి", "నాకు పని కావాలి")
    assert result["wer"] == 0
    assert result["cer"] == 0
    changed = transcript_metrics("నాకు పని కావాలి", "నాకు ఉద్యోగం కావాలి")
    assert changed["word_errors"] > 0
    assert 0 < changed["word_accuracy"] < 1


@pytest.mark.asyncio
async def test_field_rehearsal_cannot_use_reviewed_asr_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(asr, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(asr.settings, "GROQ_API_KEY", None)
    audio = b"reviewed-microphone-clip"
    asr.register_rehearsal(audio, "నాకు పని కావాలి", "te")
    assert await asr.transcribe(audio, "audio/webm", "te") == (
        "నాకు పని కావాలి",
        "rehearsal_cache",
    )
    assert await asr.transcribe(
        audio,
        "audio/webm",
        "te",
        allow_rehearsal_cache=False,
    ) == ("", "unavailable")


def test_p7_gate_requires_reviewed_field_evidence_but_does_not_claim_full_build_readiness():
    audit = {"passed": True}
    field = {
        "status": "measured",
        "reference_transcript_independently_reviewed": True,
        "latency": {"passed_voice_thresholds": False},
    }
    # Build plan's 1.5 s / 4 s voice gate applies to cached P4 clips. P7 cold
    # measurements are reported separately and do not replace that gate.
    assert _p7_ready(audit, field)
    field["latency"]["passed_voice_thresholds"] = True
    assert _p7_ready(audit, field)
    field["reference_transcript_independently_reviewed"] = False
    assert not _p7_ready(audit, field)


@pytest.mark.asyncio
async def test_synthetic_rehearsal_reports_metrics_without_storing_transcript(
    monkeypatch, tmp_path
):
    from daari import p4

    async def fake_turn(sink, message):
        await sink.send_json(
            {"type": "transcript", "text": "నాకు పని కావాలి", "provider": "groq"}
        )
        await sink.send_json(
            {
                "type": "done",
                "stamps_ms": {
                    "t_asr_final": 230,
                    "t_audio_first_chunk": 850,
                    "t_done": 2400,
                },
            }
        )

    monkeypatch.setattr(p4, "_turn", fake_turn)
    audio = tmp_path / "clip.webm"
    reference = tmp_path / "reference.txt"
    audio.write_bytes(b"webm clip")
    reference.write_text("నాకు పని కావాలి", encoding="utf-8")
    args = Namespace(
        source="synthetic_rehearsal",
        audio=str(audio),
        reference=str(reference),
        locale="te",
        samples=1,
        reviewed=False,
        review_note="",
    )

    result = await _field_rehearsal(args)
    serialized = json.dumps(result, ensure_ascii=False)
    assert result["status"] == "rehearsal_only"
    assert result["asr"]["wer_mean"] == 0
    assert result["latency"]["passed_voice_thresholds"]
    assert result["rows"][0]["stages_ms"]["t_asr_final"] == 230
    assert "నాకు పని కావాలి" not in serialized


@pytest.mark.asyncio
async def test_reviewed_field_mode_requires_explicit_reviewer_attestation(tmp_path):
    audio = tmp_path / "clip.webm"
    reference = tmp_path / "reference.txt"
    audio.write_bytes(b"webm clip")
    reference.write_text("నాకు పని కావాలి", encoding="utf-8")
    args = Namespace(
        source="reviewed_microphone",
        audio=str(audio),
        reference=str(reference),
        locale="te",
        samples=1,
        reviewed=False,
        review_note="",
    )

    result = await _field_rehearsal(args)
    assert result["status"] == "blocked"
    assert "--reviewed" in result["reason"]


@pytest.mark.asyncio
async def test_reviewed_field_mode_requires_review_provenance(tmp_path):
    audio = tmp_path / "clip.webm"
    reference = tmp_path / "reference.txt"
    audio.write_bytes(b"webm clip")
    reference.write_text("నాకు పని కావాలి", encoding="utf-8")
    args = Namespace(
        source="reviewed_microphone",
        audio=str(audio),
        reference=str(reference),
        locale="te",
        samples=1,
        reviewed=True,
        review_note="",
    )

    result = await _field_rehearsal(args)
    assert result["status"] == "blocked"
    assert "--review-note" in result["reason"]
