"""Monotonic voice hop measurements retained for the local evidence HUD."""

import math
from collections import deque

_samples: deque[dict[str, float]] = deque(maxlen=200)


def record(stamps: dict[str, float]) -> dict[str, float]:
    keys = ("t_release", "t_asr_final", "t_llm_first_token", "t_llm_response", "t_engine_done", "t_audio_first_chunk", "t_done")
    result = {key: round(max(0.0, (stamps[key] - stamps["t_release"]) * 1000), 1)
              for key in keys if key in stamps and "t_release" in stamps}
    if result:
        _samples.append(result)
    return result


def summary() -> dict[str, dict[str, float]]:
    result = {}
    for key in ("t_asr_final", "t_llm_first_token", "t_llm_response", "t_engine_done", "t_audio_first_chunk", "t_done"):
        values = sorted(row[key] for row in _samples if key in row)
        if values:
            result[key] = {"n": len(values), "p50": values[math.ceil(0.5 * len(values)) - 1],
                           "p95": values[math.ceil(0.95 * len(values)) - 1]}
    return result
