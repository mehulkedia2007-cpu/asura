# Local demonstration and acceptance checks

This is a local demo, not a production release certification. See STATE.md and
P7.md for the remaining data-coverage and field-validation gates.

## Start

From the repository root, start the configured Postgres and Redis services:

```sh
docker compose up -d
```

In separate terminals:

```sh
cd apps/api
uv run uvicorn daari.main:app --host 127.0.0.1 --port 8000
```

```sh
cd apps/web
pnpm dev
```

Open http://localhost:3000/en (or `/te`, `/hi`). The API is required for all
data-backed flows, not just voice. Existing local database migrations and seed
data must be installed; API provider credentials stay in the local environment.
Never publish them in screenshots or source control.

## User journey

1. Open My path in a fresh browser profile. No skill should be prefilled as held.
2. Add SQL level 4, inspect Before/After, then run a market-demand simulation.
   Reload and verify the saved goal and skills. Start the SQL assessment.
3. Search job leads and schemes. Inspect source dates and eligibility status;
   unavailable sources and no-data results are valid outcomes, not permission
   to fabricate matches.
4. Search TCS / Prime reports in Interview intelligence. Change the role to
   Data Analyst and verify the no-coverage state.
5. Paste a placement notice with a future interview date. Review extracted
   fields, confirm them, create the plan and start a practice interview.
6. Answer five prompts, reload the saved session, then delete it.
7. Repeat in Telugu and Hindi. Check mobile layout and keyboard focus.
8. Open Evidence to inspect recorded evaluations and their limitations.

## Repeatable checks

From `apps/web`:

```sh
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm start --port 3001
```

In another terminal in `apps/web`, with the API running:

```sh
WEB_URL=http://localhost:3001 node scripts/audit-web.mjs
WEB_URL=http://localhost:3001 node scripts/check-p5.mjs
```

The browser scripts require Playwright Chromium (`pnpm exec playwright install
chromium`). Outputs are in `.cache/web-audit` and `.cache/p5`. The interview
microphone regression uses generated audio and substituted transcription; it
does not measure human ASR accuracy. Tests create anonymous local test profiles.
Do not run build and browser checks against the development server concurrently.

P7 field acceptance still needs an independently reviewed real Telugu recording
and transcript. Synthetic clips and cached latency are not substitutes. No public
deployment URL or release tag is claimed here.
