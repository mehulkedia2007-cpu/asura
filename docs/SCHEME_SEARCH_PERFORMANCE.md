# Government-support search repair — 2026-10-10

The ordinary Search button now reads the AP/national source library without waiting for external sites, embeddings, model extraction or broad indexing. No-match searches return an honest empty state with instructions to use Refresh sources. A brief, public-record-only catalog cache avoids repeated database connections; copies prevent one user's eligibility decision from leaking into another request. Writes invalidate the cache, and it expires after 30 seconds.

Refresh sources has a six-second external-work budget. Named selections refresh their own source details instead of paging through a national search. Broad refresh reads at most one myScheme page and five relevant records per provider. Slow sources retain the saved selection and original dates. Freshly fetched records take precedence over old results. Profile mismatches remain visible for an explicitly selected scheme, with a clear rule explanation.

The saved-details message is informational, rather than styled as an error. Provider failures show plain-language recovery instructions. Invalid browser visit history cannot convert successful search results into a false error. Exact official scheme titles return the named record. Library counts use the same AP/national scope as the selector.

## Observations

Before: the production no-match query `zzunmatchedschemeneed` took 17.31 seconds and surfaced `ConnectTimeout`. Named/title and category searches took about 0.9–1.0 seconds when the index was already warm.

After, local production build with actual sources and no mocked API responses:

| Search | Observed browser response |
|---|---:|
| Named FutureSkills Prime | 125 ms |
| Real source refresh | 5,290 ms, selection retained |
| Exact title | 78 ms |
| No match | 148 ms, no provider error |
| Education/scholarship category | 149 ms, 5 records |

These timings are measurements, not guaranteed response times. Deployment startup, database wake-up and the user's connection can add time. Official sites can remain unavailable; saved dates and eligibility uncertainty are preserved.

## Checks

- API: 127 tests, Ruff and Pyright, including empty-query latency boundary, selected refresh timeout, successful fresh-data precedence, partial-provider fallback, selected eligibility mismatch and catalog isolation/invalidation.
- Frontend: lint, typecheck, 8 tests and production build.
- Browser regression: From `apps/web`, run `WEB_URL=<site> node scripts/check-scheme-search.mjs`. Default target is the fellowship shown in the user's screenshot. The local snapshot uses `SCHEME_NAME='FutureSkills Prime Incentive Program'`.
- Production results are emitted by that script into `.cache/scheme-search/report.json` after publication.
