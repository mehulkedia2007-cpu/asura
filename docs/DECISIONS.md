# DECISIONS.md — DAARI (Team ASURA)

Append-only. One line per decision: what, why, when. Reversals get their own entry.

## D1 · 2026-09-17 · Repo `asura` reused for DAARI, previous project removed
The working tree arrived with every file of the previous project (NADI, a health-triage build) deleted and `DAARI_BUILD_PLAN.md` added. `/setup` treated that as intentional and rebuilt the operating layer for DAARI rather than restoring NADI. The NADI tree remains recoverable at commit `a264545`.
Names: **repo and deploy target = `asura`** (the directory and the GitHub remote), **product = DAARI**, **Python packages = `daari_core` and `daari`**. Never name a deploy target after a previous project.

## D2 · 2026-09-17 · Toolchain verified at setup, not assumed
| Tool | Found |
|---|---|
| git | 2.55.0 |
| gh | 2.101.0, logged in as `dmrk22` |
| uv | 0.12.15 |
| pnpm | 12.3.4 |
| node | v22.23.2 |
| docker | 29.7.2, daemon up |
| ollama | 0.34.1, **no models pulled** |
| ffmpeg / ffprobe | 9.0.1 — **installed during this setup** |
| python3 (system) | 3.14.7 — the project pins 3.12 via `uv`, so this is not used |
| vercel CLI | not installed — deploy is optional (§13 cut line 9) |
| Microsoft Edge | not installed — **human to-do**, it is the demo browser for native te-IN voices |

ffmpeg was installed at setup rather than at P5, per §15 finding 22 (librosa/ffmpeg install stalls).

## D3 · 2026-09-17 · Versions pinned from the live registries, never from memory
Checked with `npm view <pkg> version` and the PyPI JSON API on 2026-09-17.

**Web**
| Package | Version |
|---|---|
| next | 16.3.5 |
| react / react-dom | 19.3.0 |
| typescript | 7.0.2 |
| tailwindcss / @tailwindcss/postcss | 4.3.3 |
| motion | 13.4.0 |
| zustand | 5.0.15 |
| @tanstack/react-query | 5.103.1 |
| react-hook-form | 7.88.0 |
| zod | 4.6.5 |
| d3-force | 3.0.0 |
| @playwright/test | 1.63.0 |
| @biomejs/biome | 2.5.14 |

**API / core**
| Package | Version |
|---|---|
| fastapi | 0.141.1 |
| pydantic | 2.13.5 |
| sqlalchemy | 2.0.54 |
| alembic | 1.20.0 |
| structlog | 26.1.0 |
| httpx | 0.28.1 |
| arq | 0.28.0 |
| networkx | 3.6.1 |
| numpy | 2.5.3 |
| fastembed | 0.8.0 |
| librosa | 1.0.0 |
| edge-tts | 7.2.8 |
| groq | 1.7.0 |
| google-genai | 2.24.0 |
| pytest | 9.1.1 |
| hypothesis | 6.168.0 |
| ruff | 0.16.8 |

**Risk flagged, not resolved:** TypeScript **7.0.2** is the native-port major, not the 5.x line. P1 must prove `pnpm typecheck` and `pnpm build` green on Next 16.3.5 before the web lane goes wide. If it fights, fall back to the latest 5.x and record the reversal here — that is a P1 decision, not a P5 surprise.

## D4 · 2026-09-17 · frontend-design and design-critique already installed — no vendored copy
`/setup` step 6 says to fetch `frontend-design` into `.claude/skills/` if missing. It is already installed from Anthropic's official plugin marketplace at
`~/.claude/plugins/marketplaces/claude-plugins-official/plugins/frontend-design/skills/frontend-design/SKILL.md`,
invocable as `frontend-design:frontend-design`, alongside `anthropic-skills:design-critique-agent` and `design-audit`.
Vendoring a second copy into the repo would only create a version to drift. Not done deliberately. If the plugin is ever unavailable on the demo laptop, fetch it from `github.com/anthropics/skills` into `.claude/skills/frontend-design/` and record the source commit here.

## D5 · 2026-09-17 · MCP servers verified live, not just declared
`.mcp.json` declares `context7` (`@upstash/context7-mcp`, latest 4.1.1) and `playwright` (`@playwright/mcp`, latest 0.0.81). Both are also connected in-session as plugin servers. Verified `context7` with a live `resolve-library-id` call for Next.js — it returned `/vercel/next.js`. Playwright MCP verified by package resolution and the connected plugin server; not launched, to avoid opening a browser during setup.

## D6 · 2026-09-17 · Hooks proven by execution, not by reading
`.claude/hooks/pre-tool-guard.sh` was run against 18 sample payloads: 9 that must be blocked (force push in two spellings, `rm -rf` on a source dir and on the repo root, three ways of reading the env file, two ways of printing a secret) and 9 that must pass (`rm -rf` on build dirs, pytest, alembic, pnpm build, docker, ffmpeg, an ordinary push). 18/18 as specified. `ffmpeg` and `ffprobe` added to the permissions allow-list per §5.2.

## D7 · 2026-09-17 · `safety.md` repurposed rather than deleted
The previous project's `.claude/rules/safety.md` was health-triage-specific. Rewritten in place as DAARI's five guards (the LLM never decides · provenance or it doesn't ship · Scam Shield states its reasons · no praise without a quote · eligibility has three states). Keeping the filename keeps the guards where every agent already looks.

## D8 · 2026-09-17 · Not done at setup, deliberately
- **No `.env`.** It is human-owned; `/setup` never creates or edits it. The template `.env.example` was rewritten for DAARI (Adzuna, SerpAPI + budget, `DAARI_SEED`, TTS voices) — 5 keys need values before P1's health check goes green.
- **No cloud provisioning.** Deploy is §13 cut line 9 and the laptop is the primary demo. Supabase / Upstash / Vercel / HF are wired as optional keys only; `/ship` provisions them if the clock allows.
- **No notification target.** This project declares no Telegram/Slack integration, so `/setup` step 8 is a no-op. Add one to `.env.example` first if you want build pings.
- **No subagent routing check.** §5.1 asks `/setup` to dispatch a throwaway builder and grep its transcript for the model. Not run — dispatching a subagent for a setup task is a cost with no payoff until P1 has something to build. Do it as the first action of `/go`.

---

## D9 · 2026-09-18 · Groq no longer serves Llama 3.3 70B or Llama 4 — plan §3 was stale
`GET https://api.groq.com/openai/v1/models` on this account returns 13 models and **no Llama 3.3 or Llama 4**:
`allam-2-7b`, `canopylabs/orpheus-arabic-saudi`, `canopylabs/orpheus-v1-english`, `groq/compound`, `groq/compound-mini`, `meta-llama/llama-prompt-guard-2-22m`, `meta-llama/llama-prompt-guard-2-86m`, `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `openai/gpt-oss-safeguard-20b`, `qwen/qwen3.8-27b`, `whisper-large-v3`, `whisper-large-v3-turbo`.

**Decision: the Groq link in the chain is `openai/gpt-oss-120b`** (the largest tool-capable chat model on the list), with `qwen/qwen3.8-27b` as the same-provider fallback. ASR is unaffected: `whisper-large-v3` is present, and `whisper-large-v3-turbo` is available if latency bites at P4. Gemini `gemini-2.5-flash` is live and stays first in the chain (`gemini-3-flash-preview` and `gemini-3.1-flash-lite` are also listed — do not adopt a preview model on the demo path).

This is exactly what non-negotiable 5 exists for. Anything that hardcodes a Llama id from the plan text is a bug.

**Not verified:** the *numeric* free-tier rate limits for Gemini and Groq. Both consoles need an interactive login, which `/setup` cannot do. Reachability and model availability are verified; requests-per-minute is not. Treat the chain's circuit breaker (3 failures or one 429 → skip 60 s) as the real defence and do not design against a remembered quota.

## D10 · 2026-09-18 · myscheme.gov.in search API is `v6`; v4 and v5 are dead
Probed live: `search/v4` and `search/v5` both return `HTTP 500 {"message":"Internal server error"}`. **`GET https://api.myscheme.gov.in/search/v6/schemes?lang=en&q=[]&keyword=<kw>&sort=&from=0&size=<n>`** returns `200` with `{status:"Success", data:{summary:{total:…}}}` — 186 results for `income` — when sent with three headers together: `x-api-key: tYTy5eEhlu9rFjyxuCr7ra7ACp4dv1RH8gWuHTDc` (the portal's own public web key), a browser `User-Agent`, and `Referer: https://www.myscheme.gov.in/`. Without the key: `401`. That key is public site configuration, not a secret, so it belongs in `data/sources.yaml`, not in `.env`.

Also verified live: Nominatim returns Guntur at `16.2915189,80.4541588` with a contact `User-Agent` (1 req/s, cached, per its usage policy); Remotive answers with no key; `www.myscheme.gov.in/sitemap.xml` is a valid crawl fallback if the API moves again. **The Playwright fallback in §7.5 stays in the plan** — an API that changed twice will change again.

## D11 · 2026-09-18 · Two keys in `.env` are one character short and return 401
`.env` now exists with all 23 keys present and 19 non-empty. Gemini and Groq authenticate. **Adzuna returns `401 AUTH_FAIL` and SerpAPI returns `401 Invalid API key`.** The likely cause is a truncated paste, not a wrong account: `ADZUNA_APP_KEY` is **31 characters (Adzuna issues 32)** and `SERPAPI_KEY` is **63 characters (SerpAPI issues 64)** — each exactly one short. Values were never printed; only lengths were measured. `.env.example` now documents the expected lengths so the next paste is self-checking.

Consequence: Adzuna is **required** for demand weights (§7.4), so this blocks P3's demand weighting, not P1. SerpAPI is §13 cut line 8 and can be dropped entirely. `/health` reports both honestly rather than hiding them.

## D12 · 2026-09-18 · `tools: All tools` in the agent frontmatter meant *zero* tools
Every dispatch of `builder`, `designer` and `red-team` failed with *"would be spawned with zero tools — refusing: unrecognized [All, tools]"*. The frontmatter line `tools: All tools`, written at the previous setup, is parsed as a comma-separated **list of tool names**, and the two tokens `All` and `tools` are not tools. The correct way to grant every tool is to **omit the field**. Fixed in `builder.md`, `designer.md`, `red-team.md`; `planner.md` gained `Bash` (it has to run `git log`); `reviewer.md` keeps its read-only list and now names all seven safety-critical modules.

Agent definitions are cached for the life of a session, so the fix takes effect on the next `claude` start. This setup ran its two scaffold agents as `general-purpose` with an explicit `sonnet` override to get the same routing.

## D13 · 2026-09-18 · Subagent routing check: PASS (supersedes D8's fourth bullet)
Both scaffold subagents' transcripts under `~/.claude/projects/-Users-damaruk-dev-asura/<session>/subagents/` contain exactly one model: `"model":"claude-sonnet-5"`. Sonnet routing is correct, `CLAUDE_CODE_SUBAGENT_MODEL` needs no change, and the human can move to `/model opusplan` without the fallback in §5.1.

## D14 · 2026-09-18 · The pre-tool guard blocks *documentation* that quotes a destructive command
`pre-tool-guard.sh` greps the whole Bash command string, so a heredoc writing the sentence "never run recursive force-delete outside build dirs" is blocked as if it were that command. The guard is correct to be dumb here — narrowing it to ignore heredoc bodies is exactly the hole a malicious payload would use. **Decision: keep the guard unchanged; write documents that quote dangerous commands with the Write tool, not with a shell heredoc.** `CLAUDE.md`'s "Never" line is now phrased without the literal flags.

## D15 · 2026-09-18 · `redis` pinned to 5.3.1, not 8.1.0 — `arq` forbids 6.x and up
D3 pinned `redis==8.1.0` from the registry's latest. It is **mutually unsatisfiable with `arq==0.28.0`**, whose published metadata requires `redis[hiredis]<6,>=4.2.0` (confirmed live against the PyPI JSON API for arq 0.28.0, not inferred from an error message). No arq release supports redis 8.x.

**Decision: `redis==5.3.1`** — the newest release inside arq's window — with the reason inline in `apps/api/pyproject.toml`. Latest-from-the-registry is the rule for choosing a version; a dependency's own constraint still outranks it. Revisit only if arq ships a release that widens the pin; do not "upgrade redis" as a tidy-up without checking arq first.

## D16 · 2026-09-18 · `/health` must not report a reachable daemon as a usable provider
The first `/health` body reported `{"provider":"ollama","model":"llama3.1:8b","status":"ok","detail":"reachable"}`. Ollama is installed and running but **has no models pulled** — `GET /api/tags` returns `200 {"models":[]}`. A 200 from the daemon is not a provider: the chain's third link would have failed on its first real call, at P4, on stage.

The probe now parses the tag list and reports `skipped: model_not_pulled` unless the configured model is actually present (matching `llama3.1:8b` and a bare `llama3.1:latest` pull alike). Three regression tests in `apps/api/tests/test_health.py` cover empty list, model present, and bare-tag pull. Live body now reads `"status": "skipped", "detail": "model_not_pulled"`.

The general rule, since `/health` is what the P1 gate and the pitch both rely on: **a probe reports the capability, not the connection.** Reachable, authenticated and usable are three different facts.

## D17 · 2026-09-25 · Restart from P1 on the plan's phase order
At the user's request, the current tracked tree was restored from the verified P1 commit `6539b31`. This removes the standalone demo and the later ad hoc product routes, engine modules, fetchers, data, and screenshots from the branch tip. The old commits remain in Git history for reference; this is a forward cleanup commit, with no history rewrite. Untracked project export copies and overview artifacts were moved out of the repository to `/private/tmp/asura-pre-p1-artifacts-2026-09-25/`.

P1 keeps locally hosted font files so the Next build is independent of Google Fonts. Its build script uses webpack because Turbopack stalled on this host. The API CI now declares Pyright, which the old workflow invoked without installing. The premature eval job that silently passed when `evals/run.py` was absent and the ffmpeg installation (needed only for later voice/prosody work) were removed from P1 CI. Phase status and verification evidence live in `docs/STATE.md`. Resume with P2 only after the P1 gate is green.

## D18 · 2026-09-25 · P2 runs on a sourced seed before the learned embedding gate

The restored 24-skill taxonomy and 26-item CAT bank are the P2 seed from Git history. The API environment has no YAML parser or fastembed model installed, so the committed seed is JSON and the first vector representation is a deterministic 47-dimensional prerequisite feature vector. It gives the graph one genuine adjacency pair and lets profile vectors shift and persist in pgvector. The API reports `embedding_kind: prerequisite-feature-seed`; it does not call these learned or multilingual embeddings.

Migration `0002_p2_vectors` pins 47 dimensions for this seed. Expanding the taxonomy or replacing the representation requires a coordinated vector-table migration and reseed. The source data, assessment coverage and embedding model remain explicit P2 gate work in `docs/STATE.md` rather than being presented as complete §7 scale.

## D19 · 2026-09-25 · P3 live source and model behavior

After the user's approval, the public myScheme v6 search and detail endpoints were verified against live responses. Search returns `data.hits.items`; detail, documents and application channels are separate requests. The previously documented portal browser key is a public site key and is used only for those public endpoints. Eligibility is never inferred from a search summary. The AP MSME public directory supplies summary cards and source links, but no verified eligibility or document fields through the current adapter, so those cards remain `unknown`.

On this account, a real `gemini-2.5-flash` generate call returned 404 even though the model list exposed it; `gemini-3.1-flash-lite` generated a valid response and is the P3 rule extractor. Two later Telugu rule calls returned 503, leaving those decisions `unknown`. The scheme index uses `gemini-embedding-001` at 768 dimensions and lexical fallback if an embedding call fails. This updates D9's earlier availability observation; model-list reachability is not an execution guarantee.

The public Nominatim server is used for user-triggered place lookups with a persistent cache and one-request-per-second process limit. Adzuna supplied coordinates for three local Guntur leads in the live check. Recurring bulk listing geocoding is deliberately avoided under the [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/).

## D20 · 2026-09-25 · P3 retrieval gate remains red

The 40-query local benchmark (20 Telugu) on 179 live-derived scheme records measures precision@5 0.49, below §7.5's 0.8 gate. Scam and grounding fixture gates pass, but those synthetic fixtures do not establish field accuracy. The source registry now records portal reachability; five of nine portals were reachable in this environment, while unavailable portals supply no eligibility evidence. Do not infer a passing retrieval gate from a working UI or from a high hit@5 (0.875). Keep the benchmark exit status nonzero until precision improves on a reviewed relevance set.


## D21 · 2026-09-25 · Resolve P3 retrieval blocker without changing the gate

D20's 0.49 result is superseded by 0.805 precision@5 on the same 40 queries and
179 source records. No expected IDs or relevance labels were changed, and the
fixed denominator of five and 0.80 cutoff remain intact. The benchmark ceiling
is 0.84 because some queries have fewer than five labeled relevant schemes.

The old OR-query shortlist discarded candidates before ranking, verbose detail
text overwhelmed scheme purpose, and detail ingestion lost brief descriptions.
Use bilingual concept normalization and field-weighted purpose ranking over the
small AP/central catalog, with optional semantic rank as a small tie-breaker and
fallback. Preserve summary/tag metadata, backfill missing context from existing
source snapshots in migration 0006, and hash each actual locale chunk for vector
invalidation. Eligibility still requires complete source-backed rules.

CI now evaluates a frozen public-source corpus through the same ranker, so the
retrieval gate does not depend on services or model availability. Snapshot,
live-database lexical and embedding-enabled checks each measured 0.805;
English 0.80, Telugu 0.81, recall@5 0.728, hit@5 1.0. This is a development-set
regression result, not a holdout claim. Keep broader source coverage and an
independently judged evaluation set as separate work. See `evals/README.md`.

## D22 · 2026-09-25 · P4 keeps voice facts behind the existing verifier

The P4 agent calls the existing typed P2/P3 engine and live-source functions. Gemini/Groq/Ollama adapt native function calls into one bounded loop, with six model turns at most, provider circuit breaking and a cached response path. Source titles and locale summaries are extracted from stamped, HTTPS-linked cards. Free prose is checked against those exact spans before rendering or TTS; unsupported model text is struck. Missing Telugu/Hindi source wording produces a localized no-data utterance with the linked card still visible. This preserves the P3 safety boundary while the optional semantic verifier and verified translation are absent.

The voice route records receipt-to-hop timings and the browser records release-to-playback start. Final model text streams internally and measures its first content token; complete sentences are verified before any text or audio event leaves the server. The HUD also shows `t_llm_response` for completion. Generated sentence audio is cached by content hash; only explicitly reviewed ASR clips enter the transcript cache. The voice latency gate remains open. The one-field scheme follow-up uses a source-backed missing field and re-evaluates the deterministic rules after an answer.

## D23 · 2026-09-25 · Live P4 provider request held for explicit authorization

The sandbox could not connect to configured Gemini/Groq endpoints. An escalated product-prompt test was rejected by auto-review because it would send an internal system prompt, tool definitions and a query to those external APIs without specific authorization. A separate, safer test used only a synthetic `echo_word` tool and public `hello` prompt: Gemini and Groq both completed a native function-call round trip and streamed final text with a measured first content token. That check found that Groq's GPT-OSS returned HTTP 400 when `tool_choice=none` was sent with tool declarations; omitting declarations on the final text pass worked. Synthetic Edge TTS and Groq ASR also completed for English and Telugu, although the Telugu transcript changed one word. The actual product prompt, tool schemas and a real user recording were not sent. Full-product behavior remains unverified until the user authorizes that specific egress.

## D24 · 2026-09-26 · Authorized P4 integration and cached gate completed

Destination-specific user authorization resolved D23. The actual agent executed roadmap, job and Telugu scheme tools against configured Gemini/Groq, with first content-token measurements. Browser testing found the missing Uvicorn transport; pin wsproto 1.3.2. Supply taxonomy IDs in the prompt, exclude transient token/request timestamps from cache identity while retaining source fetch stamps, permit cache hits during provider cooldown, cap voice agent work at 90 s and Edge TTS at 12 s. Preserve rejected claims when falling back to verified source titles.

The reusable voice replay script blocks HTTP and Edge calls without substituting tool/model results, requires actual cached audio plus successful tool results, and evaluates server receipt-to-first-audio and total delivery. Three synthetic clips × 20 repeats passed the unchanged <1.5 s/<4 s gates (p95 at most 34.7 ms). This is a cached server regression, not a human ASR or browser playback benchmark. Uncached scheme retrieval took 64 s; P7 must retain that limitation and measure actual microphone/browser behavior. Real Chrome WebSocket verification and all three localized page renders passed.

## D25 · 2026-09-26 · Close P4 with sentence streaming and browser playback evidence

Final-only buffering was insufficient for P4. Incremental sentence splitting now feeds the existing verifier before each speech callback; incomplete tails remain buffered, provider failover resets the unfinished tail, and accepted streamed sentences stay in the final evidence record. No raw model token reaches TTS. Browser interruption invalidates queued playback, closes the prior socket and guards delayed microphone/file reads. Source names without translations get only a localized field label, preserving the name and its source exactly.

Forty-six API tests and all web checks pass. Browser-inclusive cached first-playback p95 is 56/53/44 ms for en/te/hi (20 each), with HTTP/TTS upstream blocked; response delivery p95 is 3/39/3 ms. Server cached gates also pass. These replace server-only timing as the P4 closure evidence. The UI now accumulates playback p50/p95. P4 is complete; field ASR and cold-provider measurements belong in P7 rehearsal and remain honestly distinguished from cached regression results.


## P5 completion — 2026-09-26

P5 uses the plan’s GfG/GitHub source lane, paste-only notices, on-screen packs and text-only coach metric cut lines. The 60-company list is a discovery seed; only TCS Prime and Infosys Specialist Programmer have reviewed report coverage. Those roles are never relabeled as the learner’s taxonomy goal. Dates retain their source-update meaning.

Schedules use Asia/Kolkata and exclude interview day, maintain prerequisites and report unfinished hours. Feedback admits only computed findings with valid transcript quotes; an optional model rewrite cannot add a trait, promise or unrelated claim. Session IDs are anonymous capabilities with 24-hour access expiry and an explicit delete action. Hash-feature vectors are labeled lexical rather than semantic. See [P5](P5.md) for checks, source limits and reproduction.

## D26 · 2026-09-26 · P7 measures field behavior only with independently reviewed inputs

P7 adds `evals/run_p7.py` and a cache-bypass path for an explicitly requested
field rehearsal. The deterministic audit passes the invented-number,
payment-instruction, notice-privacy, CAT-termination, shared-engine, roadmap,
ablation, i18n, P3 and P5 checks. The field path calculates WER/CER from a
separately prepared transcript and measures real first-audio and total-turn
p95 after bypassing ASR, LLM and TTS caches.

At the time of the initial P7 implementation, no reviewed microphone
clip/reference pair was available, so that snapshot recorded the field portion
as `not_run`. This was superseded on 2026-09-30 by the reviewed Google FLEURS
Telugu run documented in `docs/P7.md`. The current report separates P7 phase
readiness from whole-build readiness and lists remaining P2/P3 gates. Synthetic
uncached rehearsals remain `rehearsal_only`; neither they nor cached P4 timings
are promoted to field accuracy.

The red-team pass also exposed English-only scam payment/contact matching. The
core rules now catch Telugu and Hindi fee requests, Telugu WhatsApp-only
contact, and preserve explicit no-fee negation; the added cases pass.

## D27 · 2026-10-01 · Redesign around existing journeys and measured evidence
Use one grouped workspace, mobile comparison controls and a static settled d3-force prerequisite map. Deepen coral for contrast, preserve multilingual fonts and show source stamps. Show signed engine scores as decimals because they are not probabilities. Keep frozen benchmark, current live-index measurement, cached voice and cold/field evidence distinct. The redesigned UI does not close P2/P3 data gates or provision a production backend.

## D28 · 2026-10-01 · Deploy the shared API with free cloud persistence

Current Vercel documentation supports FastAPI ASGI WebSockets on Fluid compute.
Use a separate API project rooted at the monorepo root, free Neon in Singapore
and free Upstash Redis. User approved both provider terms and transfer of the
existing provider keys into private Vercel settings. Use verified TLS, direct
Neon connections and NullPool on serverless, explicit migrations and reviewed
seeds. Resolve frontend HTTP/voice configuration at request time and gate the
online badge on actual persistence readiness. No local credentials or rehearsal
files are bundled. The six-hour persistent arq worker is not provided by Vercel;
source freshness continues through request-time refresh. See DEPLOYMENT.md.

## D29 · 2026-10-01 · Bound interactive source refresh and preserve real tool execution

Keep interactive scheme refresh within 45 seconds, with an eight-second query
embedding budget and lexical fallback. Fetch relevant eligibility detail before
broad summary indexing and defer document embeddings to the existing batch
worker. Preserve fetched/cached evidence and expose timeout/partial refresh
warnings. Incomplete source rules stay unknown and do not prompt for personal
facts that cannot establish eligibility. Browser checks branch on source-backed
predicates rather than assuming every live catalog contains the same scheme.
Explicit roadmap requests in all three languages execute the shared tool even
when the model returns prose only or providers are unavailable; verification
still rejects unsupported prose. These decisions preserve useful engine output
during free-provider failures without claiming complete source coverage.
