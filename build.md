# DAARI by Team ASURA — SYNORA Track 1 (AI/ML) · Problem 01 · Master Build Plan v6 (FINAL) · ₹0 stack

18 Sep 2026. This file is self-contained; earlier versions are superseded. Save it as `~/dev/asura/DAARI_BUILD_PLAN.md`, open Terminal there, run `claude --model opus`, type `/setup` once, then `/model opusplan` and `/go` until the clock runs out. Claude Code creates the repo, code, tests, migrations, evals, deploy and demo script. You spend nothing.

Team: **ASURA**. Product: **DAARI** (దారి — "the way / the path"). Repo: `asura`.

v6 = v5 re-read line by line against the problem statement (§1) and red-audited against it (§16). Changes: the government-scheme pipeline is spelled out end to end (§7.5), the roadmap demo shows an explicit **Before | After** driven by a **"Simulate skill update"** control (the statement's own words), the profile is also a **vector** that re-embeds on every skill update (the mentors say "graph/vector"), Telugu is **end-to-end** on every screen (not only the rural mode), local job leads carry **distance in km** from the user's village, and AP-state scheme sources are mandatory. Nothing in the operating layer (§5) or the UI direction (§8) changed.

---

## 1. The problem statement, line by line, and where each line lands

| Their words | Our reading | Engine | Proof on stage |
|---|---|---|---|
| "unified, intelligent agent" | one product, one orchestrator, not two apps | E8 | one chat/voice surface for both personas; agent trace |
| "two distinct personas via a shared core matching engine" | two UIs that look and feel different, one engine underneath, provable | E1 + §8 | separate `packages/core`; AST test; live call counters per persona on `/evidence` |
| Students: "skill assessment" | measure, don't ask | E5 | 6-question adaptive test with an error bar |
| Students: "adaptive roadmap" | changes when the learner changes (and, our addition, when the market changes) | E2 | Before \| After view |
| Students: "targeted interview feedback" | specific to the role, the company, and the words the student said | E7 + E9 | quoted feedback, company-specific question corpus |
| Rural: "vernacular-language government scheme awareness" | schemes fetched live, filtered by eligibility, explained in Telugu, spoken | E4 + E6 + §7.5 | Telugu voice query → schemes with "why you qualify" |
| Rural: "local job leads" | near the user's village, with distance, from live sources, scam-checked | E3 | cards with km, source, fetched-at, scam badge |
| "Adaptive Roadmap: demonstrate before/after roadmap changes triggered by simulated skill updates" | a control literally labelled "Simulate skill update" and a side-by-side Before \| After | E2 | the judge presses it |
| "Live Data Sources … via live APIs or scraping, with no hardcoded lists" | every job and scheme comes from a fetcher with a source URL and a fetch time; only the list of *sources* is configuration | E3 + §7.5 | stamps + Refresh + repo-scan test |
| "Actionable Interview Feedback: highly specific, avoiding generic praise" | every feedback item quotes the candidate; praise without a quote is rejected | E7 | guard test at 0 violations |
| "Vernacular & Voice I/O: end-to-end support for at least one regional language with first-class voice input and output" | Telugu on every screen, every label, every scheme summary; voice in and out everywhere, not only the rural mode | E6 + i18n | flip the language toggle on `/path`; speak on `/interview` |
| "Shared Architectural Engine … verified in code" | a test, not a diagram | E1 | `/evidence` import-graph box |
| Mentor: "dynamic graph/vector updates in roadmaps" | both: the graph re-weights from live demand and grows transferability edges; the profile vector re-embeds on every skill update and shifts the match | E1 + E2 | `/evidence`: edges added today, cosine shift after the last update |
| Mentor: "precision of RAG retrieval for regional schemes" | AP-state schemes are in the corpus; precision@5 is measured, half the golden queries in Telugu | §7.5 | number on `/evidence` |
| Mentor: "voice latency" | measured per hop, shown live | E6 | HUD |
| Mentor: "actionable depth of mock interview feedback" | quotes + metrics + prosody + follow-up + company corpus | E7 + E9 | the interview screen |
| Suggested stack | ignored where a better free choice exists; each has a one-line answer | §11 | Q&A |

---

## 2. The angle: one path engine, market-aware, grounded, two worlds

**A Skill Graph that the live job market re-weights, wrapped in a Constitution.** ~300 canonical skills with prerequisite edges, learning hours, Telugu labels and sources. A person is a set of nodes and a vector; a goal is a set of nodes and a vector; a roadmap is the cheapest path between the sets where "cheapest" is hours divided by live market demand. A job is a set of required nodes, a distance, and a scam risk score. A scheme is a set of eligibility predicates with documents and apply steps. A company+role is a dated corpus of what was actually asked. Voice, Telugu, the student UI, the rural UI and the placement-cell UI are adapters. An LLM orchestrates by calling engine tools; it never decides a match, and under the Constitution it never states a fact it cannot point to.

| # | Engine | What the judge sees |
|---|---|---|
| E1 | **Skill Graph + Explainable Matcher** (`packages/core`) — level-aware coverage, graph gap cost over three edge types, profile/role/job vectors in pgvector, transferability learned from live co-occurrence | one package, AST test, per-persona call counters, graph on/off ablation, edges added today, cosine shift after update |
| E2 | **Market-Aware Adaptive Roadmap** — Dijkstra with weight = hours / (1 + demand); Before \| After on learner change and on market change | "Simulate skill update" → Before \| After + diff; "Market shock" → Before \| After + diff (cause: market) |
| E3 | **Live Local Leads + Scam Shield** — Adzuna India, Remotive, Google Jobs via SerpAPI; geocoded distance; freshness; new-since-visit; scam score with reasons | cards with km, source, fetched-at, Refresh, scam badge |
| E4 | **Schemes: Live Ingestion + Eligibility + Slot-Filling** — §7.5 pipeline; predicates evaluated deterministically; documents; apply steps at the Grama/Ward Sachivalayam; one spoken question for a missing field | "why you qualify" rule list, source link, Telugu summary, one question by voice |
| E5 | **Adaptive Skill Assessment** — Rasch 1PL CAT; rural: spoken self-description → taxonomy | six questions, estimate with error bar |
| E6 | **Streaming Voice, end-to-end Telugu** — interim transcripts, sentence-streamed TTS, barge-in, language auto-detect, five-hop HUD; full Telugu locale on every screen | reply audio < 1.5 s; language toggle everywhere |
| E7 | **Interview Coach with Evidence + Prosody** — quotes required, prosody bands, follow-up on the weakest STAR element | quoted feedback, metrics strip |
| E8 | **Agent Orchestrator** — tool-calling loop over engine tools with a visible trace | which tools ran, with what, how long, what the verifier struck |
| E9 | **Interview Intelligence + Placement Prep** — dated, sourced questions per company+role; placement notice → prep pack to the interview date | "37 questions, 2023–2026, 4 sources"; a 9-day plan |
| E10 | **The Constitution** — grounding rules enforced by schema, guard, verifier and evals; "no data" is a first-class answer | struck sentences with reasons; no-data rate; 13-row article panel |

Differentiators: the market moves the roadmap · Scam Shield · CAT assessment · slot-filling eligibility · streaming voice · prosody · what this company asked, dated · placement prep from a real notice · a constitution the code enforces · agent trace + evidence page.

---

## 3. Tech stack — ₹0, verified at `/setup` (never from memory)

| Layer | Choice | Why |
|---|---|---|
| Monorepo | `packages/core` (pure Python engine) + `apps/api` (FastAPI, `uv`) + `apps/web` (Next.js, `pnpm`) + `data/` + `evals/` | "Shared" is a fact of the import graph |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, **Alembic**, `structlog`, `httpx`, `arq` | Alembic autogenerate: migrations are Claude Code's job |
| Graph + math | **NetworkX**, **numpy**; skill/profile/role/job embeddings via fastembed stored in pgvector | Real algorithms, all CPU |
| DB | Postgres 17 + **pgvector**; local Docker `pgvector/pgvector:pg17`; prod Supabase free | Rows, vectors, graph tables, demand, item bank, corpus in one DB |
| Cache / queue | **Redis 7** (local Docker; prod Upstash free) + `arq` | Fetch cache with TTL, scheduled refresh, new-since-visit |
| **LLM (₹0)** | Chain: **Gemini** (AI Studio free; native tools) → **Groq** (Llama 3.3 70B / Llama 4; native tools) → **Ollama** `llama3.1:8b` (if pulled) → cached. `llm/tools.py` normalises tool schemas; JSON-mode fallback | Free, no card; the agent loop survives failover |
| **ASR (₹0)** | **Groq `whisper-large-v3`** (final, `language` auto or `te`) + browser Web Speech API for interim transcripts → `faster-whisper` small if pulled | Streaming feel from the browser, accuracy from Groq |
| **TTS (₹0)** | **`edge-tts`** (`te-IN-ShrutiNeural`, `hi-IN-SwaraNeural`, `en-IN-NeerjaNeural`) per sentence → browser `speechSynthesis` fallback (demo in Edge) | Natural Indic voices, no key |
| Prosody | **librosa** + `ffmpeg` | Real acoustic features |
| Embeddings / rerank | `fastembed` `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384-d, Telugu-capable) + `BAAI/bge-reranker-base` | Multilingual, CPU, zero network |
| Geocoding / distance | **Nominatim** (OSM, free, 1 req/s, cached) for village/mandal → lat/lon; haversine for km; Overpass (OSM) for nearest Sachivalayam/MeeSeva as a stretch | "Local" means kilometres, not a keyword |
| Live jobs | **Adzuna** India (free key), **Remotive** (no key), **SerpAPI Google Jobs** (free 100/month, no card, budgeted) | Three real sources, every card stamped |
| Live schemes | **myscheme.gov.in** (search JSON + detail pages; Playwright fallback), **AP state portals** (Grama/Ward Sachivalayam services list, APSeva, department scheme pages), **central livelihood portals** (PMKVY, PM Vishwakarma, PMEGP/KVIC, MUDRA, NAPS apprenticeships, NCS), **data.gov.in** datasets where they exist (free key) | §7.5 |
| Interview corpus | GeeksforGeeks interview experiences, AmbitionBox, LeetCode Discuss, GitHub public repos, SerpAPI-discovered blogs; Glassdoor excluded (ToS) | Public, dated, attributable |
| Frontend | Next.js (App Router), TypeScript strict, Tailwind v4, `motion`, **d3-force**, Zustand, TanStack Query, react-hook-form + zod, shadcn primitives restyled, `next-intl` (en/te/hi), `MediaRecorder` + Web Speech API | As in the UI brief; i18n is first-class |
| Tests / evals | `pytest`, `hypothesis`, Playwright, `evals/run.py` → `report.json` | `/evidence` reads the report |
| CI/CD | GitHub Actions: lint, types, core tests, api tests (pgvector service), web tests, evals, Playwright; deploy on `main` if secrets exist | A red eval blocks deploy |
| Hosting (₹0, optional) | Vercel + Hugging Face Space (Docker) + Supabase + Upstash | Laptop is the demo; prod is the QR |
| Claude Code tooling | superpowers, karpathy-guidelines, Anthropic `frontend-design`, design-critique, Context7 MCP, Playwright MCP | §5 |

---

## 4. Your part — 30 minutes, in parallel with `/setup`

1. **Install**: Homebrew; `brew install git gh uv pnpm node@22 ffmpeg`; Docker Desktop; Claude Code native installer `curl -fsSL https://claude.ai/install.sh | bash`; `claude` once, log in (Max). Optional (≥ 16 GB, home Wi-Fi): `brew install ollama && ollama pull llama3.1:8b`. Install **Microsoft Edge** for the demo (native Telugu TTS fallback).
2. **Free keys** (no card): GitHub `gh auth login`; Google AI Studio → `GEMINI_API_KEY`; Groq → `GROQ_API_KEY`; Adzuna → `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`; SerpAPI → `SERPAPI_KEY`; data.gov.in → `DATAGOV_KEY` (optional). Optional deploy: Supabase, Upstash, Vercel, HF token.
3. **Folder**: `mkdir -p ~/dev/asura && cd ~/dev/asura`; save this file as `DAARI_BUILD_PLAN.md`.
4. **Wired mic**; push-to-talk, 5 cm from the mouth; test in the hall.
5. **Telugu speaker** owns the data lane (§12). No Telugu speaker → strings reviewed by TTS read-back.
6. **One real placement notice** from the placement cell (redact names).
7. **Start**: `claude --model opus` → `/setup` → fill `.env` when it stops → on the green health check `/model opusplan` → `/go`. `/demo` before the last hour.

---

## 5. How Claude Code runs this — the operating layer

### 5.1 `CLAUDE.md` (Claude Code writes this at `/setup`; under 100 lines)

```markdown
# DAARI (Team ASURA) — rules for Claude Code
Hackathon: SYNORA Track 1, Problem 01. Spec = DAARI_BUILD_PLAN.md. Read it, docs/STATE.md and `git log -10` at the start of every task.

## Non-negotiables
1. One engine. Both persona routes import daari_core. A test fails if apps/api/daari/personas/* contains matching, roadmap, eligibility, assessment, scam or scheduling logic, or if either route bypasses daari_core. packages/core never imports FastAPI, SQLAlchemy, httpx or any LLM client.
2. No hardcoded leads or schemes. Every job or scheme shown comes from a fetcher with source_url and fetched_at; the UI renders both. Only the registry of sources is configuration. Snapshots allowed only with the stamp visible.
3. The LLM never decides. Matching, roadmap, eligibility, ability estimate, scam score, distance, schedule, coverage stats are deterministic engine calls. The LLM orchestrates (tool calls), extracts structure at temperature 0 (cached by sha256), and writes words. Every tool call is logged to the agent trace.
4. Feedback guard: every interview feedback item carries a verbatim quote from the transcript. Praise without a quote is rejected. Adversarial violations = 0.
5. Versions, model IDs, free-tier limits verified (Context7 / `npm view` / `uv pip index` / consoles) before use. Never from memory.
6. ₹0: no paid API, no card, no paid tier. SerpAPI's 100/month is a budget: rehearsal + demo only, cached.
7. The scripted demo path works with the network unplugged: cached LLM/tool responses, cached ASR for rehearsed clips, pre-rendered TTS, snapshot leads and schemes with stamps, local DB and Redis.
8. Synthetic personas only. Real live leads and schemes, fake people.
9. Clock rule: at each phase deadline, ship what passes tests, log what's missing in STATE.md, move on. Cut lines (§13) fall back per engine. Never extend a slot without a DECISIONS.md entry.
10. The Constitution (docs/CONSTITUTION.md) is enforced in code: every user-facing factual sentence passes grounding/verifier.py; every number passes constitution.check_numbers(); every date passes check_dates(). A sentence that fails is removed, not rephrased. The "no data" template is a success path.
11. Model memory is not a source. Anything time-bound (jobs, schemes, questions, companies, dates, salaries, deadlines, eligibility) is answered only from an evidence bundle with fetched_at stamps. The system prompt states today's date and forbids recall.
12. Every screen and every string has en / te / hi entries in apps/web/messages/*.json; a test fails on a missing te key. Scheme and job summaries shown in Telugu are generated at temperature 0 from the English evidence and never add an entity or a number (diff test).
13. Sources whose ToS forbid scraping are never fetched (Glassdoor). Polite limits (1 req/s), caching, no personal names stored from interview experiences or notices.

## Skills
brainstorming (5 min max per phase) → writing-plans → subagent-driven-development → test-driven-development → systematic-debugging → verification-before-completion. karpathy-guidelines on every diff. frontend-design + design-critique on every UI task; docs/UI_BRIEF.md is law.

## Process budget
Full reviewer pass only for packages/core/, agent/loop.py, schemes/extract_rules.py, grounding/verifier.py, interview/guard.py, voice/latency.py, prep/notice.py. Everything else: builder self-review + tests. One-page plans per phase. Up to three builders in parallel on disjoint folders.

## Commands
core: `cd packages/core && uv run pytest -q`
api: `cd apps/api && uv run pytest -q` · `uv run alembic revision --autogenerate -m "<msg>" && uv run alembic upgrade head` · `uv run uvicorn daari.main:app --reload` · `uv run arq daari.workers.WorkerSettings`
web: `cd apps/web && pnpm dev | pnpm build | pnpm test | pnpm e2e`
infra: `docker compose up -d` · evals: `uv run python evals/run.py`

## Models (aliases on the Anthropic API: opus = Opus 5, sonnet = Sonnet 5, haiku = Haiku 4.5; never pin version strings here)
- /setup runs in a session started with `claude --model opus`. After the green health check the human switches to `/model opusplan`.
- Subagent frontmatter: planner opus · builder sonnet · reviewer opus · designer sonnet · red-team opus. Effort default (high) everywhere.
- Routing check: /setup dispatches one throwaway builder and greps its transcript under ~/.claude/projects/<proj>/<session>/subagents/ for "model". If not sonnet: unset CLAUDE_CODE_SUBAGENT_MODEL (never set it to inherit), restart, re-check; if it still fails, note in DECISIONS.md and continue on opusplan.
- If plan limits bite: `/model sonnet`, all agents sonnet.

## Compaction policy
Preserve: current phase + task, failing tests, open decisions, human to-do. Re-read STATE.md after compaction.

## Never
push --force · rm -rf outside build dirs · edit or print .env · skip a failing test · hardcode a lead or a scheme · put engine logic outside packages/core · let the LLM return a match/score/eligibility directly · purple/violet/navy hues · gradients on product screens · any paid service.
```

### 5.2 `.claude/settings.json`

```json
{
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "Bash(uv:*)", "Bash(pnpm:*)", "Bash(npm view:*)", "Bash(npx:*)", "Bash(git:*)", "Bash(gh:*)",
      "Bash(docker:*)", "Bash(docker compose:*)", "Bash(ollama:*)", "Bash(vercel:*)", "Bash(huggingface-cli:*)",
      "Bash(python3:*)", "Bash(curl:*)", "Bash(make:*)", "Bash(ruff:*)", "Bash(pytest:*)", "Bash(ffmpeg:*)",
      "Read(**)", "Edit(**)", "Write(**)"
    ],
    "deny": ["Read(./.env)", "Edit(./.env)", "Bash(git push --force:*)", "Bash(rm -rf /:*)"]
  },
  "hooks": {
    "SessionStart": [{ "matcher": "startup|resume|clear|compact",
      "hooks": [{ "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/session-start.sh" }] }],
    "Stop": [{ "hooks": [{ "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/stop-gate.sh" }] }],
    "PreToolUse": [{ "matcher": "Bash",
      "hooks": [{ "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/pre-tool-guard.sh" }] }]
  }
}
```

Hooks: `session-start.sh` prints `docs/STATE.md`, `git log --oneline -10`, and the head of the current phase plan. `stop-gate.sh` exits 2 ("update docs/STATE.md first") if `apps/` or `packages/` changed in the turn and STATE.md did not. `pre-tool-guard.sh` blocks `push --force`, `rm -rf` outside `node_modules|.next|dist|.venv`, and any command that prints `.env` or a `*_API_KEY`. `/setup` validates hook and permission syntax against https://code.claude.com/docs/en/hooks and /docs/en/settings and rewrites the file if the syntax has moved.

### 5.3 Subagents (`.claude/agents/*.md`; frontmatter `name`, `description`, `model`, `tools`)

| Agent | Model | Job |
|---|---|---|
| `planner` | opus | One-page plan per phase in `docs/superpowers/plans/`, acceptance tests first (writing-plans skill) |
| `builder` | sonnet | One task at a time, TDD, surgical diffs (karpathy). Up to three in parallel on disjoint folders |
| `reviewer` | opus | Reviews `git diff` for the seven safety-critical modules only; rejects with reasons; never edits |
| `designer` | sonnet | Owns `apps/web`; loads frontend-design + design-critique + `docs/UI_BRIEF.md`; screenshots with Playwright and critiques before handoff |
| `red-team` | opus | `/audit`: tries to get generic praise past the guard, hardcoded leads/schemes past the stamp test, engine logic outside core, a non-qualifying scheme shown as qualifying, an LLM-returned score reaching the UI, a scam listing unflagged, a roadmap that lengthens after learning, a CAT that never stops, a tool call missing from the trace, a company fact with no evidence, a date newer than the data, a number not in a tool result, a missing Telugu string |

### 5.4 Slash commands (`.claude/commands/*.md`)

- `/setup` — (session started with `claude --model opus`) installs superpowers (`/plugin marketplace add obra/superpowers-marketplace`, `/plugin install superpowers@superpowers-marketplace`); vendors karpathy-guidelines, `frontend-design` (github.com/anthropics/skills) and design-critique into `.claude/skills/` when the marketplace lacks them; writes `.mcp.json` (Context7, Playwright); verifies every version and model ID in §3 plus current Gemini/Groq free-tier limits, the Adzuna endpoint, the myscheme.gov.in search endpoint and its headers, Nominatim usage policy; scaffolds §6; `gh repo create asura --private --source=. --push`; writes `.env.example`; **stops once** listing the exact `.env` lines; on re-run: `docker compose up -d`, baseline migration, `/health`, web hello screen, the subagent routing check, STATE.md; ends by printing "now run `/model opusplan` then `/go`". Exit criterion: `http://localhost:8000/health` returns `{sha, db, redis, llm:[…], tools, asr: groq, tts: edge, adzuna, myscheme, nominatim, serpapi_budget_left}` and `http://localhost:3000` renders "DAARI · online" in en and te.
- `/go` — reads STATE.md; picks the next task in the current phase plan (or has `planner` write the next phase); runs builders in parallel where folders are disjoint; reviewer on the safety-critical modules; tests + evals; conventional commit; STATE.md; prints five lines: done / verified how / running where / blockers / your to-do. `/go bug: <text>` runs systematic-debugging first. Enforces the clock rule.
- `/lane <core|api|web|data>` — second laptop: git worktree `../asura-lane-<name>`, branch `lane/<name>`, edits scoped to that folder (§12).
- `/demo` — starts compose + api + arq worker + web, seeds personas, runs `scripts/warm_cache.py` (executes every LLM/tool call, ASR for the rehearsed clips, TTS per sentence, all lead and scheme fetches, the notice extraction and the demo companies' corpus in `docs/DEMO.md`, stores them), then replays the demo as a Playwright dry-run with the network blocked, and reports what failed.
- `/audit` — `red-team` then `reviewer`; blocks `/ship` until findings are fixed or accepted in DECISIONS.md.
- `/ship` — tags `v1-synora`, full CI, optional deploy, verifies URLs, writes QR codes into `docs/DEMO.md`, prints the final checklist.

---

## 6. Repository layout

```
asura/
├── DAARI_BUILD_PLAN.md  CLAUDE.md  .mcp.json  docker-compose.yml  .github/workflows/ci.yml
├── .claude/  settings.json  rules/  agents/  commands/  skills/  hooks/
├── docs/  STATE.md  DECISIONS.md  UI_BRIEF.md  DEMO.md  CONSTITUTION.md  superpowers/plans/
├── packages/core/daari_core/
│   ├── graph.py taxonomy.py profile.py match.py roadmap.py demand.py eligibility.py assess.py
│   ├── scam.py geo.py interview_metrics.py prep.py constitution.py telemetry.py
├── packages/core/tests/
├── apps/api/daari/
│   ├── main.py config.py db.py deps.py workers.py
│   ├── llm/        chain.py tools.py cache.py gemini.py groq.py ollama.py
│   ├── agent/      loop.py registry.py trace.py
│   ├── grounding/  verifier.py evidence.py nodata.py
│   ├── voice/      asr.py tts.py stream.py latency.py lang.py
│   ├── leads/      adzuna.py remotive.py serpapi_jobs.py normalize.py refresh.py scam_llm.py geocode.py
│   ├── schemes/    sources.py myscheme.py ap_portals.py central_portals.py datagov.py normalize.py
│   │               extract_rules.py documents.py rag.py slots.py refresh.py telugu.py
│   ├── intel/      gfg.py ambitionbox.py leetcode.py github.py serp.py extract_questions.py dedupe.py corpus.py stats.py
│   ├── prep/       notice.py pack.py schedule.py
│   ├── assess/     items.py session.py
│   ├── interview/  questions.py followup.py prosody.py feedback.py guard.py
│   ├── personas/   student.py rural.py placement.py     # thin adapters; all import daari_core
│   ├── models/ api/   # routers: profile roadmap leads schemes voice assess interview prep questions agent evidence
│   ├── alembic/ tests/ Dockerfile pyproject.toml
├── apps/web/app/   (landing) onboard assess path leads schemes voice interview prep questions evidence
├── apps/web/messages/  en.json te.json hi.json
├── apps/web/components/ lib/ styles/tokens.css mocks/ e2e/
├── data/
│   ├── taxonomy/skills.yaml roles.yaml   items/items.yaml   interview/questions.yaml
│   ├── sources.yaml          # scheme + job + corpus source registry with type, URL template, parser, refresh, ToS note
│   ├── intel/companies.yaml  personas/*.json  notices/
├── evals/  schemes_golden.jsonl roadmap_cases.jsonl match_pairs.jsonl scam_golden.jsonl feedback_golden.jsonl
│           feedback_adversarial.jsonl intel_golden.jsonl notices_golden.jsonl grounding_golden.jsonl
│           nodata_adversarial.jsonl i18n_check.py voice_latency.py run.py report.json
└── scripts/  bootstrap.sh seed.py warm_cache.py push_env.sh
```

---

## 7. Engine specifications

### 7.1 Skill Graph (`daari_core.graph`, `taxonomy`)
Nodes `{id, label_en, label_te, label_hi, aliases[], level 1–5, hours, source, embedding}`; ~300 across tech, trades/livelihoods and cross-cutting skills. Prerequisite edges weighted by hours. Adjacency edges from label-embedding cosine ≥ 0.75 (Tableau ↔ Power BI), weight 0.3 · hours. Transferability edges learned at runtime from live listings: PMI(a, b) over fetched descriptions ≥ 1.0 with count ≥ 5 → edge with weight hours · (1 − min(PMI/3, 0.5)); `edges_added_today` is published. Sources per node: NSQF descriptors, NCO-2015, ESCO labels, Skill India / NPTEL course links.

### 7.2 Vectors (`daari_core.profile`, pgvector)
`profile.vector` = weighted mean of held-skill embeddings (weight = level × (1 − se)); re-embedded on every skill update and stored with a version. `role.vector`, `job.vector` = mean of required-skill embeddings. Matching's `vector_sim` component = cosine(profile, candidate). After every update the UI shows the cosine shift toward the goal ("+0.06 toward Data Analyst"); `/evidence` shows the last shift. This is the "vector update" the mentors ask for, alongside the graph re-weighting.

### 7.3 Matcher (`daari_core.match`)
`match(profile, candidates) -> [Match{score, components{coverage, gap_cost, vector_sim, constraint_fit, demand_bonus}, missing[], surplus[], distance_km?, reasons[]}]`. Coverage is level-aware, using the CAT lower bound. Gap cost = shortest-path hours from the held frontier to each missing skill over all three edge types, normalised. Constraint fit: distance (km from the user's geocoded location; radius from the profile), language, schedule, minimum pay. Score = 0.4 · coverage − 0.2 · gap + 0.15 · vector_sim + 0.15 · fit + 0.10 · demand; components shown in a popover. Ablation on `/evidence`: precision@5 on 40 golden profile–job pairs with graph edges on vs off, and with vector_sim on vs off.

### 7.4 Roadmap, demand, Before | After (`daari_core.roadmap`, `demand`)
`demand(listings_by_district) -> {skill: w}`, w = 1 + log(1 + share · 10), capped at 2×, recomputed on every refresh and on Market shock. `roadmap(profile, goal, demand) -> Path{steps[{skill, hours, why[]}], hours, weeks_at(hpw)}`: Dijkstra with weight = hours / demand, merged per missing skill, topologically ordered, each step with `why`. `diff(before, after) -> {removed[], added[], reordered[], hours_delta, cause: learner|market}`. The UI keeps the last Path as **Before** and renders the new one as **After** side by side (two graphs on desktop, a swipe on mobile) with the diff list under them. Controls, in the statement's words: **"Simulate skill update"** (pick a skill → level up → Before \| After) and **"Market shock"** (pick a skill → +N listings → Before \| After). Invariants: learning a required skill never lengthens the path; a demand increase never moves that skill later; empty diff when nothing changed; both personas produce identical output for identical inputs.

### 7.5 Government schemes — how they get into DAARI, end to end
1. **Source registry** (`data/sources.yaml`): one entry per source, not per scheme. Fields: `id, kind (json_api | html_list | html_detail | pdf | datagov), url_template, parser, refresh_hours, region (central | AP), tos_note`. Entries: myscheme.gov.in search (state = Andhra Pradesh, plus central) and scheme detail pages; AP Grama/Ward Sachivalayam services list and department scheme pages (welfare, skill development, MSME, agriculture, women & child); central livelihood portals: PMKVY, PM Vishwakarma, PMEGP (KVIC), MUDRA, NAPS apprenticeships, NCS schemes; data.gov.in scheme datasets where present. Glassdoor-style ToS exclusions apply to nothing here; all are government sources.
2. **Fetch** (`schemes/*.py`, `arq` every 6 h and on demand): `myscheme.py` calls the site's search endpoint the way its own frontend does (verified at `/setup`; headers recorded in `sources.yaml`), pages through results, then fetches each scheme's detail page for eligibility, benefits, documents and application process; if the endpoint changes, the Playwright fallback renders the same pages. `ap_portals.py` and `central_portals.py` parse HTML lists and detail pages with `trafilatura` + CSS selectors from the registry; `datagov.py` pulls CSV/JSON. Polite: 1 req/s, cache 6 h, content-hash change detection.
3. **Normalise** (`schemes/normalize.py`): `Scheme{id, name_en, level, state, ministry_or_dept, benefit_text, eligibility_text, documents_text, apply_text, url, fetched_at, as_of (source "last updated" if present), content_hash}`. Nothing is shown without `url` and `fetched_at`.
4. **Extract rules** (`schemes/extract_rules.py`, LLM at temperature 0, cached by `id + content_hash`): eligibility text → predicate AST `{all:[{field, op, value, snippet}], any:[…]}` over `age, state, district, gender, category, annual_income, occupation, education, land_holding, disability, bpl, student_status`; documents → checklist; apply text → ordered steps with the channel (Grama/Ward Sachivalayam, MeeSeva, online portal). Every predicate stores the snippet that justified it (Constitution VI).
5. **Index**: chunks embedded with the multilingual model into pgvector + `tsvector`; Telugu summary and Telugu name generated at temperature 0 from the English evidence (`schemes/telugu.py`), diff-tested to add no entity or number; the English text stays as the evidence of record.
6. **Retrieve + decide** (`schemes/rag.py`, `daari_core.eligibility`): query (Telugu or English) → hybrid search (cosine + `ts_rank_cd`, RRF top-20, rerank top-8) → `evaluate(profile, rules) -> (True | False | Unknown, reasons[], missing_fields[])` → only True and Unknown are shown, labelled; False never appears as "qualifies". `slots.py`: exactly one missing field on a top scheme → one question in the user's language, by voice if they spoke; the answer updates the profile and re-evaluates.
7. **Present**: card with Telugu name and summary, "why you qualify" as the matched rules, documents checklist, apply steps naming the Sachivalayam/MeeSeva channel (nearest office via Overpass as a stretch), source link, fetched-at, "source last updated" when known, and "new since your last visit". Spoken in Telugu on the voice screen.
8. **Measure**: `schemes_golden.jsonl` — 40 profile+query pairs (half Telugu, all AP-relevant) → expected scheme ids; precision@5 ≥ 0.8; coverage stats (schemes indexed, AP vs central, last refresh) on `/evidence`.
Why this is "live": the registry names sources, exactly as an API key names an endpoint; the schemes themselves are fetched, hashed, timestamped and re-fetched. A judge pressing Refresh sees the fetch happen.

### 7.6 Live local leads + Scam Shield (`leads/*`, `daari_core.scam`, `geo`)
`Lead{source, source_url, fetched_at, title, org, location, lat, lon, distance_km, pay, description, required_skills[], scam{score, reasons[]}, new_since_visit}`. The user's village/mandal is geocoded once (Nominatim, cached); listings are geocoded by location string (cached); `distance_km` by haversine; radius 25 → 50 → 100 km fallback until ≥ 5 results. Sources: Adzuna India (district keyword + radius), Remotive (remote, students), SerpAPI Google Jobs (local gig queries: delivery, retail, driver, technician, tailor; ≤ 30 calls at rehearsal, cached). `normalize.py` extracts skills via the taxonomy alias table plus an LLM pass at temperature 0 for misses. Scam rules (0–1): asks for fee/registration/training payment +0.5; WhatsApp/Telegram-only contact +0.2; pay > 3× district median for the role +0.2; no verifiable org +0.1; "earn from home, no skills" +0.2; free-mail employer domain +0.1; LLM second opinion adds ≤ 0.2 with a quoted reason. ≥ 0.5 red badge, 0.3–0.5 amber. Golden 30: recall ≥ 0.9, precision ≥ 0.8. Repo-scan test forbids lead literals outside fixtures.

### 7.7 Adaptive assessment (`daari_core.assess`)
Rasch 1PL: items with difficulty b ∈ {−1, 0, +1}, ≥ 8 per skill for the 12 demo-role skills, 60 generic. P(correct) = σ(θ − b). Start θ = 0, choose the item maximising I(θ) = P(1−P), Newton–Raphson update, SE = 1/√ΣI, stop at SE < 0.4 or 6 items. θ → level 1–5 with SE as the error bar; `profile.held[skill] = (level, se)`; the profile vector re-embeds. Rural: spoken self-description → LLM extraction into taxonomy ids with confidence (temperature 0, cached) → confirm chips → level 2, se 0.8 → optional CAT. Property tests: SE decreases monotonically; all-correct ends with θ ≥ +1; stopping always terminates.

### 7.8 Streaming voice, end-to-end Telugu (`voice/*`, i18n)
WebSocket `/ws/voice` on every screen (a mic button in the header): client streams interim transcripts (Web Speech, `te-IN` / `en-IN` / `hi-IN`) and on release the audio blob; server: Groq Whisper final transcript → `lang.py` (te / en / hi / Tenglish) → agent loop with streaming tokens → sentence splitter → verifier per sentence → `edge-tts` per sentence → audio chunks; client plays in order. Barge-in cancels. Five stamps: `t_release, t_asr_final, t_llm_first_token, t_engine_done, t_audio_first_chunk` (+ `t_audio_start` in the browser); HUD with p50/p95. Fallbacks: browser ASR final → Groq; edge-tts → browser `speechSynthesis`. Cached transcripts and per-sentence mp3 for the rehearsed clips. **End-to-end**: `next-intl` with `en.json`, `te.json`, `hi.json` covering every string on every screen; `evals/i18n_check.py` fails CI on a missing `te` key; scheme, job and roadmap step labels come from the taxonomy's Telugu labels; scheme summaries from `schemes/telugu.py`. A language toggle sits in the header; the rural persona defaults to Telugu.

### 7.9 Interview coach (`interview/*`, `daari_core.interview_metrics`)
Five questions: from the company+role corpus when coverage exists (E9), else the bank filtered by the goal's skills, plus one anchored to a live JD. Answer by streaming voice. Text metrics (pure): STAR coverage, quantifiers, filler rate, JD keyword coverage, duration. Prosody (librosa): WPM, pause ratio, pitch std, long-pause count, reported as bands. Feedback schema `[{point, quote (verbatim substring), fix, severity, source: text|prosody}]`, 3–6 items; `guard.py` rejects items without a valid quote or with praise phrases lacking one; one rewrite at temperature 0, then a metrics-only template. `followup.py`: weakest STAR element → one follow-up. Attempt history. Evals: must-mention recall ≥ 0.8; adversarial violations = 0; specificity score on `/evidence`.

### 7.10 Agent orchestrator (`agent/*`)
Tools (Pydantic-typed, thin wrappers): `get_profile, update_skill, assess_next_item, get_roadmap, simulate_skill_update, market_shock, search_jobs, scam_score, match_leads, find_schemes, evaluate_eligibility, ask_missing_field, get_company_questions, build_prep_pack, start_interview, interview_feedback`. Loop: system prompt (persona, language, profile summary, today's date, Constitution Articles I–IV) → LLM with tools → execute → append → repeat, ≤ 6 calls; every call logged `{tool, args, ms, provider}`. The final message passes the verifier; any number, entity or date in it must come from a tool result or evidence (a test compares). Provider chain with tool-schema normalisation; JSON-mode fallback.

### 7.11 Interview Intelligence (`intel/*`)
Seed `companies.yaml`: 60 campus recruiters common to AP colleges with role aliases; the college's real recent recruiters first. Fetchers pull dated public interview experiences (GfG, AmbitionBox, LeetCode Discuss, GitHub, SerpAPI-discovered blogs) → `extract_questions.py` (LLM, temperature 0, cached) → atomic questions `{text, round, topic, skill_ids[], year, source_url, fetched_at}`, authors dropped → dedupe (cosine ≥ 0.92 folds into "similar") → `corpus.py` (pgvector + filters) → `stats.py` (items, sources, year span, round mix, top topics per company+role). Thin (< 5 items or < 2 sources) and none states drive banners and the no-data template. Every card: year, round, source chip, "reported by a candidate". Eval: `intel_golden.jsonl` recall ≥ 0.7.

### 7.12 Placement Prep (`prep/*`, `daari_core.prep`)
Notice (paste, PDF or photo) → `notice.py` extraction `{company, role, interview_date, ctc, eligibility, rounds[], mode}` with a source span per field, `PERSON`/phone spans stripped → student confirms → `pack.py`: required skills = role's taxonomy set ∪ corpus top topics → `match` gap → `roadmap` → `schedule(roadmap, date, hours_per_day)` (day-by-day; says so if the gap exceeds the days and prioritises by demand and corpus frequency) → question set by round, recency-weighted → mock seeded from it → one-page PDF. The pack states corpus coverage and dates. Eval: `notices_golden.jsonl` field accuracy ≥ 0.9.

### 7.13 The Constitution (`docs/CONSTITUTION.md`; enforced by `daari_core.constitution`, `grounding/*`, evals)
Preamble: a wrong fact stated confidently can cost a person an interview, a scheme, or a month. DAARI is not allowed to guess.
**I. Sources of truth** — tool results, evidence with `source_url` + `fetched_at`, the user's own profile. Model memory is not a source for anything that can change. *Enforced:* prompt; evidence bundle required; verifier strikes.
**II. Time** — the prompt states today's date; every evidence item carries `fetched_at` and `as_of` where extractable; the reply states the newest evidence date used; a claim dated later than any evidence is struck; a question about a date newer than all evidence gets "our data ends on <date>", the newest data, and no fill-in. *Enforced:* `check_dates()`; 10 newer-than-data adversarial cases.
**III. Numbers** — every number must appear in a tool result or evidence, unit-aware; otherwise struck. *Enforced:* `check_numbers()`.
**IV. Names and entities** — companies, roles, schemes, exams, tools, places must appear in the bundle or the user's words. *Enforced:* `check_names()`.
**V. Unknowns are answers** — absent or thin evidence → the no-data template: what was searched, nearest data, one next step; thin data labelled on every card; the no-data rate is public. *Enforced:* `stats.py` → `nodata.py`; adversarial violations = 0.
**VI. Citations** — every factual sentence renders a citation chip; uncitable sentences are not shown; predicates show their snippet. *Enforced:* verifier appends `citation_ids`; renderer refuses uncited factual sentences.
**VII. Determinism** — matches, roadmaps, eligibility, estimates, scam scores, distances, schedules, coverage are computed. *Enforced:* trace; numbers-from-tools test.
**VIII. Language** — reply in the user's language; labels from the taxonomy; translation adds no fact; Telugu drafts pass the same checks. *Enforced:* `lang.py`; diff test; verifier pre-TTS.
**IX. Scope and seriousness** — no placement promises, no ranking against others, no invented hiring policies or cut-offs, questions labelled "reported by a candidate on <date>". *Enforced:* forbidden-claim regexes; verifier.
**X. Scams and safety** — money-asking leads flagged before display; never instruct payment to apply. *Enforced:* scam rules; forbidden phrases.
**XI. Data hygiene** — allow-listed sources; polite limits; no personal names stored. *Enforced:* `sources.yaml`; schemas without author fields; span stripping.
**XII. Transparency** — trace shows tools, evidence and struck sentences with reasons; `/evidence` publishes strike rate, citation coverage, no-data rate, grounding F1, article test status. *Enforced:* trace schema; evidence endpoint.
**XIII. Failure mode** — if the verifier fails, degrade to structured cards with no free prose. *Enforced:* exception path.

### 7.14 Grounding verifier (`grounding/*`)
`evidence.py` assembles the bundle (typed tool results, chunks with `source_url/fetched_at/as_of`, profile facts). `verifier.py`: sentence split → deterministic checks (numbers, dates, names, forbidden claims) → LLM SUPPORTED / UNSUPPORTED / NUMERIC-MISMATCH per sentence with `evidence_ids` (temperature 0, cached) → strike → if < 1 factual sentence survives, no-data template → citations → strikes logged. Runs before rendering and before TTS; 400 ms p95 budget (parallel). Evals: `grounding_golden.jsonl` F1 ≥ 0.85; `nodata_adversarial.jsonl` violations = 0.

### 7.15 LLM provider chain (`llm/*`)
`complete(task, messages, tools|schema, temperature=0, stream=False)`: Gemini → Groq → Ollama → cache; circuit breaker (3 failures or 429 → skip 60 s); cache key `sha256(task + model + normalised input)`; `warm_cache.py` pre-executes the demo. Logs provider, model, latency, cache hit, tool calls → `/evidence`.

---

## 8. UI brief — `docs/UI_BRIEF.md` (direction unchanged)

Direction: **"Editorial instrument."** Paper, ink, one signal colour. Counter preloader, oversized display serif, marquee, hairlines, uppercase micro-labels, instrument-like data panels. Reference for feel only: wonjyou.com and Awwwards SOTD. **Two UIs, one engine, deliberately different**: the student surface is dense and keyboard-first; the rural surface is voice-first with three big Telugu buttons and no reading required to complete a task; both run on the same routes and the same tokens.

Palette (OKLCH tokens; unit test: no hue in 250–320, no gradients on product screens): `--bone` oklch(0.965 0.006 85) · `--ink` oklch(0.18 0.01 60) · `--graphite` oklch(0.42 0.01 60) · `--signal` oklch(0.62 0.2 30) (current path, active node, Refresh) · `--sage` oklch(0.68 0.08 150) (qualifies / matched) · `--amber` oklch(0.78 0.15 80) (stale / missing / thin). Dark mode flips bone/ink. No glassmorphism, glow, neon; shadows ≤ 1 px hairline + 4 px blur at 8%.
Type: Instrument Serif or Fraunces 64–140 px; Geist or Inter Tight for UI; Geist Mono for numbers, stamps, ids; Noto Sans Telugu / Noto Serif Telugu paired at the same optical size; scale 1.25; tabular numerals.
Motion (`motion`; d3-force owns the graph): springs 260/28, 120–240 ms micro-interactions, counters on stats; on Before \| After the removed nodes fade to graphite and the new path draws in signal over 600 ms; reduced-motion respected; nothing animates while audio streams.
Screens: `/` (counter → hero "One path. Two worlds." → live lead marquee with stamps → engines spread → evidence numbers → Open demo; 30-min cap), `/onboard` (persona; rural voice-assisted; village/mandal geocoded), `/assess`, `/path` (Before \| After panes; node size = demand; "Simulate skill update" and "Market shock" controls; diff list with `cause`; cosine shift chip), `/leads` (km, match popover, missing chips, scam badge, source + fetched-at, Refresh, "N new"), `/schemes` (Telugu name + summary, why-you-qualify rules, documents, apply steps with the Sachivalayam/MeeSeva channel, source + fetched-at + source-updated, one-question prompt with mic), `/voice` (rural mode), `/interview`, `/prep`, `/questions`, `/evidence` (shared-engine counters + import-graph box, ablations, scheme precision + coverage, scam recall, voice p95 per hop, feedback specificity, freshness, edges added today, last cosine shift, grounding F1, strike rate, no-data rate, Constitution panel, CI sha). Header on every screen: language toggle (en/te/hi) and a mic button. Agent trace drawer on every product screen. 12-col grid, 24 px gutters, max 1440 px; 390 / 768 / 1024 / 1440; every screen usable on a phone.
Gates: Lighthouse a11y ≥ 90; keyboard-complete; contrast AA; design-critique before every handoff; reviewer rejects default-shadcn look and anything identifiable as a reference site.

---

## 9. Data (all free, all public)

Taxonomy (300 skills, 40 roles, sources per node, te/hi labels reviewed by the data lane); item bank (≥ 8 × 3 bands for the 12 demo-role skills + 60 generic); `sources.yaml` (scheme, job and corpus sources with ToS notes); `companies.yaml` (60 recruiters, the college's own first); personas — Ravi (22, Guntur district, village geocoded, 10th pass, OBC, family income unknown → the slot question, two-wheeler, Telugu only, wants income within 30 days), Priya (21, B.Tech CSE 3rd year, Vijayawada, Python + basic SQL, data-analyst goal, en + te), blank; notices (1 real, redacted + 9 synthetic); evals as listed in §6 plus `i18n_check.py`.

---

## 10. Run, CI, deploy

Local: `docker compose up -d`; api 8000; `arq` worker; web 3000; `/demo` warms every cache and replays network-blocked. CI thresholds: scheme precision@5 ≥ 0.8; roadmap invariants pass (incl. market-shock cases); match ablations show graph-on ≥ graph-off and vector-on ≥ vector-off; scam recall ≥ 0.9; feedback adversarial = 0; must-mention recall ≥ 0.8; voice first-audio p95 < 1.5 s and total p95 < 4 s on cached clips; CAT termination; grounding F1 ≥ 0.85; no-data adversarial = 0; intel recall ≥ 0.7; notice field accuracy ≥ 0.9; verifier p95 < 400 ms; `i18n_check` zero missing `te` keys; every Constitution article's test green. Deploy (optional, no card): Vercel + HF Space + Supabase + Upstash via `push_env.sh`.

---

## 11. Demo script (6:45) and mentor Q&A

Laptop runs everything; scripted path network-blocked; hotspot for live questions; wired mic; Edge.
1. (0:00) "Team ASURA. DAARI: one path engine, market-aware, grounded. Two worlds." Landing → Open demo.
2. (0:30) **Ravi, `/voice`.** Telugu: "నాకు గుంటూరు దగ్గర పని కావాలి". Interim text while speaking; Telugu reply starts < 1.5 s (HUD). Three jobs with km and sources; one red scam badge ("asks for ₹500 registration"). One scheme: "we need one thing — your family's annual income" → answered by voice → "qualifies" with the matched rules, documents, and "apply at your Grama Sachivalayam", source and fetched-at. Trace drawer open. Say: "Live sources, deterministic eligibility, a scam filter, Telugu in and out, every hop timed."
3. (2:15) **Priya, `/assess` → `/path`.** Six SQL questions; error bar tightens. Roadmap; node size = demand. Press **Simulate skill update** (SQL → level 4) → Before \| After, diff, cosine shift chip. Press **Market shock** (+50 Power BI) → Before \| After, diff (cause: market). Say: "Graph re-weighted, vector re-embedded, same engine that planned Ravi's 30 days."
4. (3:45) **`/prep`.** Paste the real placement notice → fields with spans → pack: gap, 9-day plan, "37 questions, 2023–2026, 4 sources" by round with year and source. Start mock → first question is one that company asked last year. Answer by voice → quoted feedback + prosody + follow-up.
5. (5:00) **The Constitution, live.** "What did <company with no corpus> ask on 12 September?" → no-data template with the newest data and its date. "Just estimate the CTC." → declines the number, shows the one sourced figure. Trace: two sentences struck, with reasons.
6. (5:50) **`/evidence`.** Counters, import-graph box, ablations, scheme precision + coverage, scam recall, voice p95, edges added today, last cosine shift, grounding F1, strike rate, no-data rate, Constitution panel, CI sha. Flip the header toggle to Telugu: the whole page changes. Say: "End-to-end."
7. (6:30) Close. Stop at 6:45.

Prepared answers (in `docs/DEMO.md`): *Why not Llama self-hosted?* Open models are in the chain via Groq and Ollama; the model never decides a match anyway. *Why not Pinecone/Qdrant?* pgvector beside the graph tables; one query joins search and eligibility. *Why not LinkedIn?* ToS and brittle; Adzuna, Remotive and Google Jobs are real, documented, stamped. *Why not self-hosted Whisper / IndicTrans2?* Whisper large-v3 on Groq's free tier is faster than a laptop; Telugu labels live in the taxonomy; translation only phrases. *Why not WhatsApp/Twilio?* Needs a card and an approved template; the voice screen is the low-literacy interface, installable as a PWA. *Is the engine shared?* Separate package, AST test, live counters. *Is the roadmap adaptive?* Dijkstra with demand-weighted edges; Before \| After is computed, not scripted; the profile vector re-embeds; property tests including market shocks. *Are schemes hardcoded?* The registry lists sources, like an endpoint; schemes are fetched, hashed, timestamped, re-fetched; press Refresh. *How precise is scheme retrieval?* Precision@5 on 40 golden queries, half Telugu, all AP-relevant, on screen; eligibility is predicate evaluation, so a non-qualifying scheme cannot appear as "qualifies". *Voice latency?* Five hops, p50/p95 on screen. *Can the model make something up?* It can draft; the verifier strikes before rendering; strike rate on screen; adversarial set at zero. *What if your data is older than my question?* It says so, with the newest date, and does not fill the gap. *What's next?* NCS + Skill India APIs, WhatsApp voice notes, counsellor and placement-cell dashboards, more languages.

---

## 12. Teammates — lanes `core | api | web | data`; worktrees; merge windows every 90 minutes; one integrator. The data lane (the Telugu speaker) owns: taxonomy te/hi labels, `sources.yaml` AP entries, `companies.yaml` (the college's recruiters first), the redacted notice, golden sets (`schemes_golden` in Telugu, `intel_golden` from recent campus rounds, `nodata_adversarial` phrasing), the four demo clips, pitch slides.

---

## 13. Build order and cut lines

Order (whatever time remains, the order holds): P1 skeleton + Constitution scaffold → P2 engine (graph, vectors, matcher, roadmap + Before \| After, CAT, tool registry) → P3 live leads + geocoding + demand + schemes pipeline + grounding verifier → P4 streaming voice + agent loop + i18n → P5 interview corpus + placement prep + coach → P6 evidence + polish → P7 rehearsal + audit → freeze.
Cut lines (per engine, on a 15-minute overrun): 1 E9 sources → GfG + GitHub only. 2 Notice → paste only. 3 Prep PDF → on-screen. 4 Verifier LLM pass → deterministic checks only. 5 Streaming → whole-reply TTS. 6 Prosody → text metrics; follow-up skipped. 7 CAT → fixed 6-question quiz. 8 SerpAPI → skipped. 9 Slot-filling → "needs: X" shown. 10 Transferability edges → adjacency only. 11 Overpass nearest office → text channel only. 12 Hindi locale → en + te only. 13 Landing → static. 14 Deploy → skipped.
Never cut: `packages/core` + tests, AST shared-engine test, demand-weighted roadmap with Before \| After and "Simulate skill update", profile vector shift, freshness stamps on jobs and schemes, the scheme pipeline with AP sources, eligibility predicates, distance in km, scam rules, feedback guard, agent trace, latency HUD, Telugu locale on every screen, evidence page, deterministic Constitution checks, no-data template, citation chips, Constitution panel, cache warm-up.

---

## 14. Quality audit — v5 → v6

| Area | v5 | v6 | Why it matters against the statement |
|---|---|---|---|
| Roadmap demo | diff list | explicit Before \| After panes + a control named "Simulate skill update" | the statement's exact requirement, in its words |
| "graph/vector updates" | graph only | profile/role/job vectors in pgvector, re-embedded on update, cosine shift shown, vector ablation | the mentor line says both |
| Vernacular | rural screen + Telugu replies | full te/hi locale on every screen, header toggle, i18n CI check, Telugu scheme summaries | "end-to-end" |
| Schemes | "myscheme + AP pages" | an eight-step pipeline with a source registry, fetch, normalise, extract, index, retrieve, present, measure; AP sources mandatory; Sachivalayam apply channel | "regional", "live", "awareness" |
| Local leads | radius keyword | geocoded distance in km, radius fallback | "local" |

---

## 15. How government schemes get into DAARI — the one-paragraph version for a judge

We keep a registry of government sources, not of schemes: myscheme.gov.in, the AP Sachivalayam services list and department pages, and the central livelihood portals. A worker fetches each source every six hours and on demand, turns every scheme page into a record with its URL and fetch time, and hashes it to spot changes. An extraction pass at temperature zero converts the eligibility text into yes/no rules, each rule tied to the sentence that justified it, plus the documents list and the apply steps. Rules are evaluated against the person's profile by code, never by the model; if one fact is missing, the system asks that one question in Telugu. Retrieval is hybrid search in the same database as the skill graph, filtered by those rules, measured on forty golden queries — half in Telugu — and the precision number is on the evidence page. A judge can press Refresh and watch a scheme arrive.

---

## 16. Red-team audit — v6 against the problem statement (18 findings; earlier audits stand)

**Coverage of the statement.** (1) "Before/after … triggered by simulated skill updates" was implicit → explicit panes and a control in their words. Fixed. (2) "graph/vector updates" — no vector existed → profile/role/job vectors, cosine shift, ablation. Fixed. (3) "End-to-end" vernacular was rural-only → full locale, toggle, CI check, Telugu summaries; Hindi as cut line 12. Fixed. (4) "Local job leads" had no notion of distance → geocoding + km + radius fallback. Fixed. (5) "Regional schemes" — AP sources were optional → mandatory registry entries, golden set AP-relevant. Fixed. (6) "Scheme awareness" implies proactive → new-since-visit on schemes, Telugu spoken summaries. Fixed. (7) "Two distinct personas" — the UIs must differ, not just the data → §8 states the two surfaces and their differences. Fixed. (8) "Culturally accessible" → apply steps name the Sachivalayam/MeeSeva channel; Telugu scheme names; voice-first rural surface. Fixed.

**Schemes pipeline.** (9) myscheme's search endpoint may change or need headers → verified at `/setup`, headers in the registry, Playwright fallback, snapshot with stamp as last resort. Mitigated. (10) AP portal HTML is inconsistent → selector-driven parsers per source with `trafilatura` fallback; sources that fail parsing are shown as "source unreachable" on `/evidence`, never silently dropped. Mitigated. (11) LLM-extracted rules can be wrong → snippet per predicate, Unknown state, golden precision, and the rule list is shown so a wrong rule is visible. Mitigated. (12) "Is your registry a hardcoded list?" → it is a list of sources, equivalent to endpoint configuration; the prepared answer and Refresh handle it. Fixed.

**Vectors.** (13) A vector component could let the LLM "decide" through embeddings → the vector is computed from taxonomy embeddings, deterministic, versioned; the LLM never touches it. Fixed. (14) Cosine shift is small and unimpressive → shown as a delta toward the goal with a bar, and the ablation shows the component matters. Accepted.

**i18n.** (15) Telugu on every screen doubles string work → strings generated at temperature 0, reviewed by the data lane, CI check; Hindi is a cut line. Mitigated. (16) Telugu summaries could add facts → diff test forbids new entities/numbers; English stays the evidence of record. Fixed.

**Clock.** (17) The date has moved; remaining time is unknown → §13 gives the order and cut lines independent of hours; the never-cut list is the minimum that satisfies every line of the statement. Accepted. (18) Geocoding (Nominatim 1 req/s) could slow lead refresh → cached per location string; listings without a location are shown without km, labelled. Fixed.

Verdict: pass. Eighteen v6 findings; thirteen fixed, five mitigated or accepted with the reason stated. Every line of the problem statement and every mentor guideline now maps to an engine, a screen, and a test.
