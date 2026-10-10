# Andhra Pradesh search repair — 2026-10-10

## Build-plan comparison

| Requirement | Implementation and verification |
| --- | --- |
| §7.5 AP and central support schemes | Admit AP/statewide national records, reject other-state restrictions and explicit foreign-only target groups. Eligibility remains unknown without complete source rules. |
| E3 nearby jobs, 25 → 50 → 100 km | Verify the user's AP address independently; compute distance in the shared core. Exclude unmeasured or out-of-radius local listings. Remote results require explicit opt-in. |
| E3 Adzuna, Remotive and Google Jobs | Add Google Jobs fallback through the existing private SerpAPI credential. Require a free plan, enforce a maximum 100-search monthly ceiling and use six-hour caches. Never use paid credits. |
| Source evidence and freshness | Job publication must be within 60 days. Fetch time cannot renew an old vacancy. Unknown dates are excluded. Cards retain source links and publication/fetch stamps. |
| Government vacancies and support | Add a separate government recruitment mode using official APPSC, AP High Court and configured district notice sources. Exam results and expired district notices are excluded. Statewide notices carry no invented local distance or open-status claim. |
| Shared engine and languages | Distance, matching, demand, scam scoring and eligibility remain in the shared engine. New controls/messages exist in en/te/hi; 381 translation keys match. |

## Bugs repaired

- Default nearby search mixed worldwide remote cards into AP results.
- Provider search results were trusted without independently checking the role/skill and publication date.
- Unknown coordinates could pass into nearby cards; invalid coordinates are now excluded.
- Unscoped geocode caches could accept places outside AP.
- Nearest embedding candidates received relevance credit without a similarity floor.
- Specific scheme requests were padded with generic training or incidental ministry terminology.
- Editing filters left old results visible; cancelled requests could overwrite a newer query.

## Retest results

- 88 core tests, 116 API tests and 7 web tests; lint, API types, web types and production build.
- 57 accessibility states, 108 responsive route checks, all three languages.
- Motion/sound and cursor-responsive background checks passed, including reduced motion, pause and fallback paths.
- AP controls passed in en/te/hi: remote opt-in, government browsing with an empty keyword, stale card clearing and cancelled-response rejection. The real government browser check rendered official notices without invented distance.
- Live jobs/schemes/assessment journey passed. The source outage case displayed truthful no-data; scheme eligibility follow-up and persisted assessment profile worked.
- Frozen 40-query scheme regression: precision@5 **0.805**, passing the ≥0.80 gate. Current 342-record local live index lexical precision@5 is **0.745**, below the gate. These are development regressions, not field accuracy.
- Real official AP High Court recruitment notices were returned with dates and source links. APPSC was unreachable from this local environment; this is surfaced as a source error.
- IT training returned digital/electronics/internship support records; an unrelated ASEAN-only research fellowship was excluded. Cached scheme records are marked stale where their source has not refreshed.
- Production retesting exposed a legacy Central record restricted to North-East India. Source-text scope checks now reject regional restrictions even when old snapshots lack beneficiary-state metadata. The official [NEBPS source](https://www.meity.gov.in/writereaddata/files/NEBPS_12_v0.3.pdf) confirms its eight-state regional scope.

The source registry currently has one district recruitment adapter (Guntur), alongside statewide AP sources. Other district-specific adapters, broader scheme portal ingestion, complete vacancy deadline extraction and the live retrieval accuracy gate remain open. A source-linked notice does not establish that an application window is currently open.
