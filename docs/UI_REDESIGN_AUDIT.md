# UI redesign and build-plan audit — 2026-10-01

## Scope and result

Redesigned all nine existing product routes in English, Telugu and Hindi. The frontend is ready to publish. Local functional verification uses the real FastAPI service, PostgreSQL and Redis. **The public Vercel frontend still needs a reachable API and WebSocket backend; local success does not establish production engine availability.**

The review references `build.md` §§7–10 and §13, `docs/UI_BRIEF.md`, and the existing phase evidence. It does not declare the full build plan complete.

## Design changes

- Grouped sidebar navigation; mobile disclosure; active route; skip link; shared page introductions and footer.
- Paper/ink surfaces, coral actions, Instrument Serif headlines, local Telugu/Hindi fonts, mono data and timestamps. Coral is darker than the original token so white button text meets contrast requirements. Light/dark preference persists.
- New home journey cards, simplified search/filter surfaces, useful initial states, preparation steps, interview setup and evidence panels.
- Roadmap statistics, sourced prerequisite graph using `d3-force`, keyboard-selectable skill details, CAT progress/uncertainty and explicit learner/market diffs. Desktop compares two paths; mobile switches between them.
- Sourced result cards, expandable matching components, localized missing-skill chips, conservative eligibility questions and stale/source-error notices. Engine scores are signed weighted scores, so the UI now shows the actual decimal rather than an unsupported percentage.
- Header voice popover on every route, three prompts on the voice page, focus on opening, Escape/outside dismissal, cancellation on closing.
- API availability notice with retry and localized service errors.

The graph settles synchronously and has no ongoing animation during audio. Fancy counters, marquees and animated diff choreography remain absent; the simpler treatment follows the user's request to reduce clutter.

## Verification

| Check | Result / scope |
|---|---|
| Core/API/web unit suites | 88 core + 89 API + 3 web = **180 passed** |
| Static checks | Ruff, Pyright, web Biome, TypeScript and production build pass |
| Localization | **363 keys**, identical nonempty en/te/hi key sets; rendered Telugu/Hindi glyphs inspected |
| Browser route regression | 27 locale/route combinations, mobile and desktop; HTTP 200, no page errors or horizontal overflow; simulation, market reordering and localized assessment opening pass |
| Responsive widths | 108 checks across 390 / 768 / 1024 / 1440 px, all pass |
| axe-core | 57 states: light/dark on every locale/route plus three voice popovers; no WCAG A/AA violations |
| Lighthouse accessibility | **100/100 on all nine English routes**, mobile emulation; accessibility-only audit, not a performance score |
| Interaction checks | Map source selection, mobile comparison, menu Escape/focus, voice focus/dismissal, persistent theme and simulated 503 → real API retry pass |
| Live engine browser journey | 7 real sourced leads; 5 schemes from a 342-record index; components/source stamps; Unknown eligibility → one fact → qualifies; six CAT answers → saved profile and recalculated roadmap |
| P5 browser journeys | All three locales: questions, no-coverage result, privacy-redacted notice review/confirmation, prep shortfall, five interview answers, history reload/deletion, transcription confirmation/cancellation pass |
| P3/P5/P7 deterministic evals | Frozen scheme precision@5 **0.805**; scam precision/recall 1.0; grounding F1 1.0; no-data violations 0; P5 and Constitution regressions pass |
| Cached voice playback | After warming, 20 turns per locale; first playback p95 en **65 ms**, te **53 ms**, hi **54 ms**; response done p95 4 / 36 / 4 ms; cached gates pass |

The P5 microphone check uses a generated MediaStream and stubbed ASR. Cached voice checks replay existing rehearsal clips. Neither is a new human microphone accuracy test. Initial cold rehearsal turns took approximately 14.7 seconds (English) and 6.4 seconds (Hindi); the cached timings must not be presented as cold latency. The reviewed 2026-09-30 P7 field evidence was preserved when refreshing the deterministic audit.

Automated accessibility checks are useful but do not prove every assistive-technology combination. Telugu/Hindi additions still need native-language editorial review.

## Build-plan cross-check

| Plan requirement | Current status |
|---|---|
| §8 paper/ink/coral, multilingual type, mobile layouts, keyboard controls, Lighthouse ≥90 | Verified for the redesigned existing routes |
| §7.4 Before/After, demand shock, hours/weeks, trigger, vector shift | Implemented; browser simulation and market ordering pass. Shift is displayed when the API supplies it |
| §8 sourced skill graph | Implemented for real catalog prerequisites; held/missing styles and demand-sized nodes. It does not display unimplemented semantic/PMI edges |
| §7.7 CAT uncertainty, stop within six | Verified for SQL in a complete browser journey; broader bank is still incomplete |
| §7.6 lead source/fetched-at, distance, scam reasons, decomposable scores | Rendered and actual sourced cards verified. Local adapters can return older postings; fetch time is not publication time |
| §7.5 scheme provenance, documents/apply steps, Unknown and slot question | Rendered; live eligibility recheck passes. Some indexed records are stale or have incomplete rules; the UI exposes that uncertainty |
| §7.8 header voice, three prompts, cancellation, trace/timing | Implemented; browser focus/cancellation and cached WebSocket/audio verified locally. No production voice service configured |
| §7.9–7.12 questions/prep/interview | Verified within documented source, pasted-notice, on-screen and text-metric cut lines |
| §7.14 verifier / Constitution / evidence | Deterministic audit green; current-index metric separated from frozen regression |
| §10 production deployment | Frontend linked to the user's GitHub fork. API, WebSocket, cloud Postgres/Redis and production refresh worker are not provisioned |

### Requirements still open

1. **Production engine:** provide/deploy a public FastAPI service plus PostgreSQL/Redis/worker and configure Vercel `DAARI_API_URL` and `NEXT_PUBLIC_WS_URL`. The current public engine returns 503. A laptop's localhost cannot serve Vercel.
2. **P2 breadth:** 24 skills, 2 roles and 26 CAT items remain far below ~300 skills/40 roles and the larger assessment bank. P2 uses deterministic prerequisite-feature vectors, not the planned learned multilingual model.
3. **Graph/roadmap algorithm breadth:** UI shows prerequisite edges. The current roadmap uses demand-prioritized topological ordering, rather than the complete multi-edge Dijkstra design. Semantic/PMI graph breadth remains open.
4. **Match constraints:** distance is present; schedule, language and minimum-pay constraints remain absent. Do not claim every §7.3 filter is implemented.
5. **P3 live retrieval gate:** current local-index lexical precision@5 is **0.745**, below 0.80 on the same development labels. Older measurement of hybrid retrieval was 0.730; it was not freshly recomputed in this UI pass. Frozen 0.805 is not a substitute for this live gate. Wider source adapters, reviewed live relevance judgments and fallbacks remain work.
6. **Full UI-spec details:** onboarding and assessment are consolidated into existing path/voice controls; separate `/onboard` and `/assess` routes, spoken skill confirm/deny onboarding, per-result agent trace drawers, prosody/trends and animated counters/diffs are not complete. These were not fabricated for the redesign.

## Reproduce

Run Docker services, API migrations/seed and FastAPI on 8000; build/start web on 3015. From `apps/web`:

```sh
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm check:ui
pnpm check:journeys
WEB_URL=http://127.0.0.1:3015 node scripts/audit-web.mjs
node scripts/check-p5.mjs
WEB_URL=http://127.0.0.1:3015 VOICE_WS=ws://127.0.0.1:8000/ws/voice node scripts/voice-replay.mjs ../../.cache/voice/rehearsal 20
```

Browser reports/screenshots are in ignored `.cache/redesign`, `.cache/web-audit` and `.cache/p5`. The committed summary is `evals/ui_redesign_report.json`. Lighthouse was run with a temporary official registry install and installed Playwright Chromium; no browser credentials or recordings were committed.
