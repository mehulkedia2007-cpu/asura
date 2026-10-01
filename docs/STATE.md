# STATE — DAARI

Spec: [build.md](../build.md), v6, §13. Updated 2026-10-01.

## Current phase

**P1 complete; P2/P3 functional slices implemented but their full data and retrieval gates remain open; P4 complete; P5 complete within the documented source/paste/on-screen/text-metric cut lines; P6 evidence and polish complete; P7 audit and reviewed field rehearsal complete.** P2 has a shared deterministic engine, a 24-skill seed taxonomy, CAT items, typed API tools and an interactive Before | After path page. P3 adds live-source adapters, cached snapshots, distance and scam rules, conservative scheme eligibility, a hybrid scheme index, a six-hour arq refresh job and a fail-closed prose verifier. The frozen P3 corpus passes precision@5 at 0.805; the current 340-record live index scores 0.745 lexical / 0.730 hybrid on the same development labels and remains below the 0.80 target. P4 connects voice and text to the same tools through a bounded agent loop.

The web UI offers locale-aware path, leads, schemes and voice surfaces. The API exposes `/health`, P2/P3 engine routes, a text agent and a voice WebSocket. The P2 migration adds pgvector tables for anonymous profile, skill and role vectors. The 13 Constitution articles now have named API regression tests and live evidence probes; current local checks report all 13 green.

## Verification on 2026-09-25

| Gate | Result |
|---|---|
| Core tests and Ruff | 5 passed, 1 skipped; Ruff clean |
| API tests and Ruff | 6 passed; Ruff clean |
| Web typecheck, lint, unit tests, build | All green; 3 unit tests, webpack production build |
| API Pyright | 0 errors |
| English and Telugu HTTP pages | Both rendered localized P1 status text from the production build |
| Docker Postgres and Redis | Both healthy; baseline Alembic migration applied, pgvector present |
| Live `/health` | HTTP 200, overall `ok: true`; db, redis, Gemini, Groq, ASR, TTS, Adzuna, myscheme, Nominatim and SerpAPI probes `ok`. Adzuna initially returned HTTP 503, then passed twice on retry. Ollama optional and skipped. |
| English and Telugu dev pages | Both HTTP 200 with localized P1 status text |

The old P1 probe measurements in Git history are dated 2026-09-18; they are not evidence of current provider status.

## P2 verification on 2026-09-25

| Gate | Result |
|---|---|
| Core | 75 tests passed; Ruff clean; persona AST test now runs rather than skips |
| API | 10 tests passed; Ruff clean; Pyright 0 errors |
| Web | Typecheck, Biome, 3 unit tests and production build green |
| Local database | Migration `0002_p2_vectors` applied; 24 skill and 2 role vectors seeded; profile update changed its stored vector version |
| Local HTTP | English, Telugu and Hindi `/path` returned 200; Next proxy returned a computed learner Before | After response |

The P2 seed uses 47-dimensional prerequisite feature vectors, not fastembed. The current catalog has 24 sourced skills and 26 assessment items; only SQL and two-wheeler riding have at least eight items. CAT currently grades free-text answers by exact normalized text. P3 adds distance to lead fit; schedule, language and pay constraints are still absent. These limits should remain visible in demos and evidence rather than being described as full §7 coverage.

## P3 implementation and limits on 2026-09-25

Adzuna India and Remotive searches now normalize to source-linked, fetch-stamped lead cards. A user-triggered Nominatim lookup is persisted; Adzuna coordinates yield haversine kilometres and a 25 → 50 → 100 km radius. District listing skills feed the shared demand weights and the path page. Scam rules run before display. The lead page can use held skills from the path page to score matches with measured distance. Source payloads and geocodes persist under migration `0003_p3_sources`; refresh and a six-hour cache are implemented.

The myScheme v6 adapter pages through live search results, prioritizes AP records, and fetches English eligibility, benefits, documents and application steps. Telugu detail is fetched when a Telugu search requests it. A second adapter reads the public AP MSME directory's scheme cards, with source links and fetch stamps; its summary-only cards always have unknown eligibility. Both sources feed a `tsvector` plus 768-dimensional Gemini embedding index under migration `0004_p3_scheme_index`. The source record and source snippet stay attached to each candidate. A temperature-zero extraction pass is validated against verbatim snippets and numeric/string values; incomplete rules remain unknown, and a false result is filtered. The scheme screen shows source text, documents, steps, source freshness, coverage counts, and one source-backed missing-field question when possible. An arq worker is configured for six-hour refreshes; it must be run separately with `arq daari.workers.WorkerSettings`.

The deterministic prose verifier admits only verbatim evidence spans, cites each surviving sentence, strikes unsupported or forbidden claims and emits a no-data message when nothing survives. The optional LLM semantic pass in §7.14 remains unimplemented. Other AP department and central portal detail adapters and Playwright source fallback remain open. Portal checks record reachability, errors and discovered links without treating portal links as ingested scheme details. The AP MSME portal exposes bundled directory summaries; it does not supply eligibility evidence through this adapter.

The local suite passes: 79 core tests, 25 API tests, 3 web tests, Ruff, Pyright, web typecheck, Biome and Next build. Migrations `0003`–`0006` were applied locally. Approved live checks returned 9 leads from Adzuna and Remotive for a Guntur technician search, 3 with measured local distances and no source errors. A live myScheme/AP directory skill search found 46 candidates. A Telugu scheme search found 32 candidates and five visible Telugu names; two model rule-extraction calls returned HTTP 503, so those decisions remained unknown. The index now holds 179 source records after topic backfills. Portal probes reached 5 of 9 configured sources; four failed or timed out in this environment.

The P3 golden fixtures are now present: 30 synthetic scam cases, 20 synthetic grounding cases and 10 no-data adversarial cases. They measure recall 1.0, precision 1.0, grounding F1 1.0 and zero no-data violations on those fixtures. The unchanged 40-query scheme set (20 Telugu) now measures precision@5 **0.805** (161/200), recall@5 **0.728** and hit@5 **1.0**, up from 0.49 precision. English precision is 0.80 and Telugu precision is 0.81. The frozen source snapshot, live-database lexical path and embedding-enabled production retrieval check all pass the unchanged ≥ 0.80 gate. Queries with only two or three labeled relevant schemes limit the theoretical aggregate maximum to 0.84.

The repair preserves descriptions and tags during detail ingestion, restores missing context from retained official snapshots, ranks all 179 scheme purposes instead of a generic-word top-20 shortlist, and normalizes English/Telugu search concepts. Application boilerplate no longer determines relevance. Per-locale chunk hashes now invalidate changed embeddings correctly. CI runs the frozen corpus benchmark without provider calls; reproduce with `cd apps/api && uv run python ../../evals/run_p3.py --snapshot`. See [evals/README.md](../evals/README.md).

These queries were used during retrieval development, so these are regression results, not independent holdout or field-accuracy claims. The broader portal coverage, optional semantic verifier and source fallbacks described above remain open; the retrieval blocker is resolved.

## P4 functional slice and limits on 2026-09-25

`/agent/chat` and `/ws/voice` share a bounded, six-call agent loop over typed P2/P3 tools. Gemini native function calls are first, Groq second, optional Ollama third, with a 60-second circuit breaker and response cache. When a provider is unavailable, explicit job, scheme and path requests use a conservative deterministic route. Model prose and all factual speech pass through the existing exact-span verifier. The response carries source cards, citation IDs, removed claims, provider and tool trace. Roadmap, match and assessment results render as structured engine data without invented prose. A missing scheme field can be asked in the selected language; a spoken numeric or yes/no answer updates the supplied profile and reruns deterministic eligibility. Unknown eligibility stays unknown without complete source rules.

The header mic is on the existing product screens and `/te/voice` is the rural entry point. The browser sends Web Speech interim text and a MediaRecorder blob at release; Groq Whisper supplies the final transcript when available, with browser-final fallback. Reviewed rehearsal clips can be registered by exact audio hash for offline ASR replay; arbitrary user speech is not cached. Final model text streams internally so the first content-token stamp is measured, then complete sentences pass verification before reaching the browser. Verified sentences are sent as separate events, synthesized through Edge TTS, with browser speech synthesis fallback. Successfully generated sentence MP3s are cached by text, voice and locale. A new press cancels the active server task and browser playback. The HUD reports release-receipt to ASR, first model content token, completed model response, engine result and first audio chunk, plus browser release to playback start. Its p50/p95 values include sample counts. Source names lacking Telugu or Hindi wording retain their verbatim names under a localized field label; summaries are never invented.

Offline checks: 40 API tests passed, Ruff and Pyright clean; 79 core tests passed, Ruff clean; web typecheck, Biome, 3 unit tests and production build passed. `evals/i18n_check.py` reports 125 matching, nonempty keys across en/te/hi. Local HTTP returned 200 for `/te/voice`, `/en/voice`, `/hi/voice`, `/en/path` and `/te/schemes`; `/voice/latency` and OpenAPI returned 200. A runtime-only Next server-component hook error was found in the first HTTP pass, fixed, and the same routes then rendered 200. The WebSocket transcript, verified sentence and audio event sequence passes a local integration test with substituted providers.

## P4 completion checks on 2026-09-26

The user explicitly authorized sending the real system prompt, tool definitions, synthetic queries and resulting tool data to Google Gemini and Groq. Full-product execution passed: Groq computed a roadmap (8.82 s), Gemini returned five job cards (21.50 s), and a Telugu scheme turn returned five source cards using Gemini tools and a Groq final response (64.02 s). All recorded first content tokens. These uncached timings do not pass the cached voice target and are not presented as low-latency live behavior.

Live checks exposed and fixed a missing Uvicorn WebSocket transport (`wsproto==1.3.2`), missing taxonomy IDs in model context, an unbounded TTS wait, transient cache keys and cache bypass during circuit cooldown. TTS now falls back after 12 seconds; voice agent work is capped at 90 seconds. Engine timestamps precede the final response, source fallback preserves rejected claims, and detected language reaches scheme retrieval. Scheme follow-up questions are spoken even when the answer has no verified prose.

Three synthetic, reviewed clips were warmed through real tools and replayed 20 times each with HTTP and external TTS blocked, retaining actual caches and local Postgres. First-audio/total-response p95: English roadmap **3.0/3.0 ms**, Telugu jobs **34.7/34.7 ms**, Hindi roadmap **0.3/0.3 ms**. All pass <1.5 s/<4 s for server delivery. The Telugu job turn retained real source cards and spoke the localized no-data response because the titles lack Telugu text. These figures exclude browser overhead and audio playback duration; they do not establish recorded-human Telugu ASR accuracy. The earlier synthetic Whisper check changed one Telugu word.

Headless Chrome rendered en/te/hi voice pages with no page errors; screenshots were visually inspected. The real browser-to-Uvicorn WebSocket delivered transcript, computed roadmap, verified sentence, MP3 and done events. This replaces the earlier failed Chrome inspection. Reproduce cached checks with `apps/api/scripts/check_voice_replay.py`; see `evals/README.md`. Local generated clips and screenshots remain in ignored `.cache/voice/rehearsal/`.

## Final P4 closure on 2026-09-26

P4 is finished. Complete sentences now pass verification and reach TTS while the final model response is still streaming. Regression tests prove that invented claims stay silent and audio can precede the final result. Barge-in cancels server work, invalidates queued browser audio and ignores old socket events; pending microphone permission and file-reader races are guarded. The HUD includes browser playback p50/p95. Source names without translations are spoken verbatim with deterministic Telugu/Hindi field labels, adding no invented translation or benefit.

Final verification: **46 API tests**, Ruff, Pyright, web lint/typecheck, **3 web tests**, production build, 125-key i18n coverage, mobile layouts in all three languages, browser queue cancellation, and real provider/tool execution passed. The final 20 cached Chrome turns per locale measured first-playback p95 **56 ms en / 53 ms te / 44 ms hi** and response-delivery p95 **3 / 39 / 3 ms** with upstream HTTP/TTS blocked. The server-only gate also passed 60 turns. These are the plan's cached-clip gates; human field ASR evaluation and uncached performance remain rehearsal measurements, not unfinished P4 implementation. See [P4 closure](P4.md) and [machine-readable evidence](../evals/p4_report.json).

## P5 completion on 2026-09-26

P5 adds `/questions`, `/prep` and `/interview` in English, Telugu and Hindi, backed by the shared match/roadmap/schedule engine, source-linked candidate reports, confirmed notice fields and quote-guarded feedback. The reviewed seed has 11 questions from four 2024 reports, with 60 general company discovery entries; no college-specific recruitment claim is made. Local Postgres stores question vectors and expiring interview sessions under migration `0007_p5_interviews`. Four typed agent tools are connected.

P5 passes 86 core tests, 65 API tests, Ruff/Pyright and web checks. The 10-query retrieval, 20-notice and 8-answer development sets meet their gates with zero tested privacy/no-data/feedback violations. Both registered TCS sources refreshed live. Three-language browser flows and database concurrency/expiry/deletion checks pass. The plan’s paste-only notice, on-screen export and text-metric cuts are applied; lexical vectors, limited corpus breadth and lack of independent field validation remain explicit. See [P5 details and reproduction](P5.md) and [golden evidence](../evals/p5_report.json).

## Phase status

| Phase | Status |
|---|---|
| P1 skeleton + Constitution scaffold | Complete; code checks and live health gate green |
| P2 engine, CAT, tool registry | Functional slice green; full taxonomy, item bank and learned-embedding gate open |
| P3 live data, schemes, grounding | Frozen snapshot passes (0.805); current live index fails at 0.745; broader adapters and relevance review remain open |
| P4 streaming voice, agent, i18n flows | Complete; streaming safety, barge-in, real providers, i18n and cached server/browser latency gates pass; see P4.md |
| P5 interview intelligence and prep | Complete within §13 cut lines; corpus, confirmed schedules, coach, sessions, agent tools and regression gates pass; see P5.md |
| P6 evidence and polish | Complete; read-only evidence API and localized board green |
| P7 rehearsal and audit | Audit and reviewed human-recording rehearsal complete; cold ASR/latency measurements retained in `evals/p7_report.json` |

## Next action

### Website regression pass — 2026-09-26

Fixed mobile roadmap select overflow, dark-mode secondary-text contrast, native
Telugu/Hindi font selection, the homepage voice link changing locale, inherited
Excel skills on fresh profiles, saved-goal restoration, malformed saved-number
recovery, stale roadmap responses, and missing demand persistence. Question
search now waits for company data. API forwarding and voice connection setup
have bounded waits. Skills without CAT questions now show an explicit message.
The homepage no longer asserts an unverified online status.

Verification: 88 core tests, 69 API tests and 3 web unit tests pass; web lint,
TypeScript and production build pass. Production browser audit covers nine routes
in three languages at 390px light and 1440px dark, including skill update, market
shock and assessment opening: no page exceptions or horizontal overflow. Full
three-language interview journeys pass, including notice confirmation, five
answers, history reload, deletion and microphone cancellation (generated audio,
substituted ASR). Actual English browser searches returned 27 job leads and five
schemes with no reported source errors. These are sampled searches, not exhaustive
coverage or accuracy guarantees. Reproduction is in DEMO.md; screenshots and
machine reports are in ignored `.cache/web-audit` and `.cache/p5`.

This pass did not close the P2/P3 breadth gates, nor does it certify
deployment, accessibility scores, or human speech accuracy. P7 field rehearsal
is complete as documented below. Keep the P5 golden and session-integration
gates in CI, the P3 retrieval regression in CI, and the P4 replay command as a
local provider/cache rehearsal. Cached browser release-to-playback passes
separately from the P7 cold field measurements. Expand P2 taxonomy/CAT coverage
and P3 verified source breadth before claiming their full gates. Keep `/health`
and Constitution status honest as capabilities are added.

## Additional local verification — 2026-09-28

The current Postgres index contains 340 distinct scheme records, while the
reviewed regression snapshot contains 179. The frozen 40-query P3 regression
still passes at precision@5 **0.805**. Against the larger live index, the same
labels score **0.745** on the lexical path and **0.730** on the embedding-enabled
hybrid path, both below the 0.80 gate. The added live
records have not been independently judged in the golden set, so this result
does not establish that they are irrelevant; it does mean the live retrieval
gate is not closed. The runtime now collapses duplicate English scheme titles
across source registries before returning top results. A source-backed
FutureSkills alias improves digital-skill matching. More relevance judgments
for the larger live candidate set are needed before claiming the live gate.

Local verification also passed: 88 core tests, 69 API tests before the new
ranking regression, the P5 database session integration, web lint/typecheck/
unit tests/production build, 271-key three-locale coverage, P5 golden gates,
and the deterministic P7 audit. The real-microphone P7 rehearsal remains
unrun because its independently reviewed recording and transcript are not
available here. The UI browser audit and multilingual screen demo also remain
unverified in this pass because the saved browser permission blocks localhost.


## User-perspective regression — 2026-09-30

Rechecked the production build in Chromium against all nine routes at 390px and 1440px across English, Telugu and Hindi: all routes returned HTTP 200 with no page errors or horizontal overflow. Path simulation, market shock and assessment opening worked. The three-locale interview/prep browser journey passed five answers, history reload/deletion, audio capture with stubbed ASR, transcript confirmation and pending-microphone cancellation.

Fixed Telugu/Hindi SQL CAT prompts to use their localized wording, made the assessment API honor the selected locale for prompts and feedback, and added an explicit English-question notice for the English-skill bank. The market-shock control now requires a selected skill still on the learner's path; its browser check confirms the path order moves after a shock. The evidence board now distinguishes the frozen P3 benchmark from a read-only measurement of the current local index. The scheme retrieval ablation uses a fixture where graph edges measurably help (graph delta +0.0112); its previous fixture passed while showing no graph effect. The verifier exception path fails closed, and Article I–XIII regression tests and live probes pass.

Fresh local checks at that point: 88 core tests; 85 API tests, Ruff and Pyright; web lint, typecheck, 3 unit tests and production build; 277-key locale coverage; P3/P5 golden sets; deterministic P7 audit; 27-route browser audit; and three-locale interview/prep flow. P7 field rehearsal and report were completed in the subsequent closure below. P2/P3 data breadth and live-index scheme precision remain open.

## P7 closure — 2026-09-30

The P7 field runner now captures numeric per-hop timing stamps, omits recognized
and reference transcript text, limits clips to 4.5 MB and runs to 20 samples,
and requires explicit review provenance before a field result can be reported.
Freeze readiness checks the deterministic audit, reviewed field evidence, and
cached P4 browser/server gates from the plan; uncached P7 latency remains a
measurement rather than a substituted P4 gate. Five uncached runs on a
human-recorded, independently quality-checked Google FLEURS Telugu test clip
measured WER 0.55, CER 0.2342, word accuracy 0.45, first-audio p95 14,428.6 ms
and total-turn p95 14,428.8 ms. The cold accuracy and latency are poor but the
plan defines no cold P7 pass threshold; cached P4 browser/server gates pass.
The P7 report contains source attribution and
metrics but no transcript or audio. Eighty-nine API tests, Ruff, Pyright, and
the deterministic P7 audit pass.

The report now names this `p7_phase: ready` and keeps `full_build: open`, with
the remaining P2/P3 gates listed explicitly. This avoids presenting the P7
phase result as whole-plan completion. P7 readiness tests pass; the audit,
three-locale catalog check, and whitespace checks pass.

This supersedes the earlier statements above that the real-microphone rehearsal
was unavailable or unrun. The cold turn missed the cached-clip latency targets;
those targets apply to the separately passing P4 cached regressions.

## Remaining full-build gates

- **P2:** the seed contains 24 skills, 2 roles, and 26 CAT items. Only SQL and
  two-wheeler riding have at least eight items. The plan calls for roughly 300
  sourced skills, 40 roles, and the larger role and generic CAT bank. Vectors
  are prerequisite-feature vectors rather than the planned multilingual
  fastembed model. These are implementation/data gaps, not completed gates.
- **P3:** the frozen 179-record regression passes the 0.80 precision@5 target;
  the current 340-record live index scores 0.745 lexical and 0.730 hybrid on
  the existing development labels. Added live candidates have not been
  independently relevance-reviewed. Wider department/central detail adapters,
  Playwright fallback, and the optional semantic verifier remain unimplemented.
- **P7:** audit and reviewed Telugu field evidence are complete. Cold field
  WER is 0.55 and first-audio p95 is 14,428.6 ms; the plan does not define cold
  field thresholds. These results are diagnostic, and P7 readiness does not
  mean the entire build plan is complete.

## UI redesign and verification — 2026-10-01

All nine existing routes now use a grouped workspace shell, responsive navigation,
paper/ink surfaces, persistent themes, local multilingual type, clearer forms,
sourced cards and focused preparation flows. The roadmap includes a real
`d3-force` prerequisite map and a mobile Before/After switch. Voice focus,
dismissal and recording cancellation were checked. Match scores now display
signed weighted decimals rather than misleading percentages.

Local checks: 180 core/API/web tests; Ruff/Pyright/Biome/TypeScript/build; 363
locale keys; 27 route/locale browser journeys; 108 responsive checks; 57 axe
states with no A/AA violations; Lighthouse accessibility 100 on all nine English
routes; real leads/schemes search, eligibility recheck and six-question CAT;
three-locale P5 flows; 20 cached voice turns per locale with playback p95
65/53/54 ms. Cold rehearsal latency was much slower. The historical reviewed
P7 field evidence is preserved; no new human microphone accuracy test was run.

See `UI_REDESIGN_AUDIT.md` for requirement-by-requirement status and limitations.
The live index now has 342 schemes; its freshly checked lexical precision@5 is
0.745, below the plan gate. P2 breadth, learned skill embeddings, graph breadth,
match constraints and wider source retrieval remain open. The redesigned
frontend can publish to the user's fork/Vercel project, but production engine
functionality is blocked until a reachable API/WebSocket backend and cloud
infrastructure are supplied or provisioned.

## Cloud backend connection — 2026-10-01

Free Neon PostgreSQL and Upstash Redis resources have been provisioned with
explicit user approval. The API now has a Vercel FastAPI entrypoint, pinned
production requirements, migration/seed build step, TLS-verified cloud URL
normalization, ephemeral runtime cache paths, origin checks and `/ready`.
Frontend HTTP and voice addresses resolve from private `DAARI_API_URL`; the
online badge checks schema/database/cache readiness. Local regressions pass
88 core, 97 API and 5 web tests, Ruff/Pyright/Biome/TypeScript/build, plus the
idempotent database initialization. Production connection verification follows
deployment; this entry does not yet certify the live backend. Remaining full
build data/retrieval gates above stay open. See `DEPLOYMENT.md`.
