# Production deployment

The frontend and API deploy from the same repository as separate Vercel projects.
Frontend root: `apps/web`, Next.js. API root: `.`, FastAPI entrypoint `app.py`.
Both persona routes continue importing the shared `packages/core` engine.

## API setup

- Python 3.12. Root `requirements.txt` is exported from `apps/api/uv.lock`:
  `uv export --frozen --no-dev --no-hashes --no-emit-project --no-emit-package daari-core --format requirements-txt --output-file ../../requirements.txt`.
- Vercel installs those requirements and runs `scripts/deploy_backend.py`. It
  applies Alembic migrations and idempotently seeds the sourced taxonomy vectors
  and reviewed interview excerpts. It does not copy local profiles, sessions,
  credentials, ASR clips or source caches.
- Connect free Neon and Upstash resources privately to the API project. Neon
  supplies `DATABASE_URL` and `DATABASE_URL_UNPOOLED`; the latter takes precedence
  for asyncpg. Copy the Redis TLS URL into `REDIS_URL` if the integration uses
  another variable name. No `NEXT_PUBLIC_` variable may contain a credential.
- Set `APP_ENV=production` and `CORS_ORIGINS=https://asura-five.vercel.app`.
  Vercel sets `VERCEL=1`. Runtime cache writes use `/tmp/daari-cache`; they are
  best-effort ephemeral caches, not durable storage. PostgreSQL source snapshots,
  anonymous profiles and expiring interview sessions remain durable.
- Optional provider keys: `GEMINI_API_KEY`, `GROQ_API_KEY`, `ADZUNA_APP_ID`,
  `ADZUNA_APP_KEY`, `SERPAPI_KEY`. Without them, the documented deterministic
  agent, public source and browser speech fallbacks apply. Never commit keys.

## Frontend setup

Set private `DAARI_API_URL` to the API's HTTPS production domain and redeploy.
The HTTP proxy and `/api/connection` read it at request time. Voice receives the
equivalent WSS endpoint; public build-time key settings are unnecessary.
Missing production configuration returns 503 rather than contacting localhost.

## Verification

- `/ready` must return 200 and `ok: true` after checking pgvector, migration
  head, seeded catalog and Redis. The workspace online badge uses this endpoint.
- `/health` reports optional provider availability separately; its HTTP 200 is
  a diagnostic response and does not by itself indicate production readiness.
- Check actual roadmap/profile writes, assessment, source-stamped search,
  question retrieval, notice/prep, interview persistence and voice events.
- Run `pnpm check:journeys`, `pnpm check:ui`, and the three-language P5 browser
  script with `WEB_URL` set to the deployment being checked. Use synthetic data.

## Hosting limits

Vercel's current FastAPI runtime supports ASGI WebSockets with Fluid compute;
the API has a 300-second function duration. The browser reconnects on the next
turn after a closed connection. This is not an always-running arq worker.
Source refresh happens on request with existing six-hour snapshot freshness.
The separately configured six-hour arq job remains available for a persistent
worker host; it is not claimed to be running on this serverless deployment.

Verified against [Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi),
[WebSocket support](https://vercel.com/docs/functions/websockets), and
[SQLAlchemy asyncpg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg)
on 2026-10-01. Neon and Upstash provisioning used only their free, no-card plans
with explicit user approval of the provider terms.
