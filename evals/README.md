P3 retrieval regression
=======================

P4 locale coverage: run `python evals/i18n_check.py` from the repo root. CI
requires the English, Telugu and Hindi catalogs to have identical, nonempty
keys and rejects duplicate keys. This checks UI message coverage; it does not
grade the quality of source-language scheme or job text.

From `apps/api`:

```sh
uv run alembic upgrade head
uv run python ../../evals/run_p3.py --snapshot
uv run python ../../evals/run_p3.py --schemes --lexical
uv run python ../../evals/run_p3.py --schemes
```

The snapshot command requires neither services nor provider credentials. CI runs
it alongside the scam, grounding and no-data gates. The other commands evaluate
the current database, with optional Gemini query embeddings in the last command.

`schemes_corpus.jsonl` contains 179 public-source records exported from the local
index on 2026-09-25 after migration 0006 recovered descriptions and tags from
retained myScheme English search responses. Each record retains its source URL
and original fetch timestamp. The fixture contains only retrieval fields, not
eligibility decisions. It is a frozen regression corpus, not a current benefits
catalog. Refresh the fixture only as an explicit source-corpus update, and review
relevance judgments separately.

The existing 40 queries and relevance labels in `schemes_golden.jsonl` are
unchanged. Precision remains `relevant unique results / 5` per query, including
queries with fewer than five labeled relevant schemes. The maximum possible
aggregate is therefore 0.84. The fixed 0.80 gate is unchanged. On this corpus,
the repaired lexical path scores 161/200 = **0.805**, English 0.80, Telugu 0.81;
recall@5 is 0.728 and hit@5 is 1.0.

The corpus and queries were used during development; these are regression
measurements, not independent holdout or field-accuracy estimates. Ranking uses
source text, generic bilingual vocabulary and purpose fields, never expected IDs
or golden labels. Broader independently judged queries are still needed to
measure generalization. The current ranker scans the small AP/central catalog;
a larger deployment needs a measured candidate-recall gate before reinstating a
bounded shortlist.

## P4 cached voice rehearsal

From `apps/api`, register and warm a reviewed audio clip, then replay it with
HTTP and external TTS disabled. Postgres must remain available locally:

```sh
.venv/bin/python scripts/check_voice_replay.py clip.mp3 transcript.txt --locale te --warm
.venv/bin/python scripts/check_voice_replay.py clip.mp3 transcript.txt --locale te --samples 20
```

Warm mode sends the actual prompt, tool definitions, queries and tool results to
configured model providers and synthesizes the verified reply with Edge TTS.
Replay substitutes no model or tool results: it uses actual caches and tools,
blocks HTTP/TTS egress, requires source cards or a computed result, successful
tools and cached MP3 delivery, and exits nonzero if p95 first audio is ≥1500 ms
or total response delivery is ≥4000 ms. Times measure server receipt to audio
delivery, excluding playback duration and browser/network overhead. The browser
HUD separately records release to playback start. Clips/transcripts stay in the
ignored local cache; register only reviewed clips.

2026-09-26: 20 repeats each of three synthetic clips passed. First-audio/total
p95 was 3.0/3.0 ms (English roadmap), 34.7/34.7 ms (Telugu jobs), and 0.3/0.3 ms
(Hindi roadmap). Telugu jobs retained real source cards but spoke the localized
no-data message where sources lacked Telugu text. These cached regression
measurements do not establish live microphone ASR accuracy or uncached latency.


## P5

Run `cd apps/api && uv run python ../../evals/run_p5.py`. It measures 10 reviewed-corpus retrieval cases, 20 synthetic labeled notices, 8 synthetic answers and 116 derived feedback adversarial cases. Gates: recall@5 ≥ 0.7, field accuracy ≥ 0.9, must-mention recall ≥ 0.8, zero privacy/no-data/feedback violations. These development fixtures are not a holdout set. `scripts/check_p5.py` separately tests real Postgres ordering/concurrency, expiry and deletion. `apps/web/scripts/check-p5.mjs` exercises all three locales against running local servers, including Web Audio generated stream capture with stubbed ASR and explicit transcript confirmation. See [P5](../docs/P5.md).

## P7 rehearsal and audit

Run the deterministic audit from the repository root with:

```sh
uv run --project apps/api python evals/run_p7.py --audit
```

This exercises the existing safety and regression boundaries without network
calls or database writes. It also writes `evals/p7_report.json` with the
current Constitution table and the cached P3/P4/P5 evidence.

Field Telugu accuracy and uncached voice latency require an independently
reviewed microphone clip plus a separately prepared transcript. Run the real
rehearsal only with both files:

```sh
uv run --project apps/api python evals/run_p7.py \
  --audio /path/to/reviewed-telugu-clip.webm \
  --reference /path/to/reviewed-telugu-clip.txt \
  --locale te --samples 1 --reviewed \
  --review-note "independent review source and clip provenance" --require-field
```

The runner bypasses the ASR, LLM, and TTS caches for that path and reports WER,
CER, first-audio p95, and total-turn p95. Missing files, provider access, or
real audio delivery produce `not_run`/`blocked`, never a synthetic pass. See
[P7](../docs/P7.md).

`--reviewed` attests that the Telugu microphone recording is real and its
reference transcript was independently checked; `--review-note` records the
review basis. Audio is capped at 4.5 MB and
runs at 20 samples; transcript text is not written to the report. The uncached
latencies are reported separately. Freeze readiness uses the defined P4 cached
browser/server latency gates, not the uncached field timing.

Synthetic clips may be measured for pipeline rehearsal with
`--source synthetic_rehearsal`; the resulting status is `rehearsal_only` and
cannot make the P7 phase status ready. P7 phase readiness does not assert full
build readiness; the report lists the remaining P2/P3 gates separately.
