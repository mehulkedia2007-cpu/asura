# Guided usability verification — 2026-10-10

## Changes

- 20 starter learning roles, up from 2; existing 24 skills retained. New roles are introductory occupational plans, not certification standards or complete job qualifications.
- Clear skill-level meanings and three-step instructions in English, Telugu and Hindi. 428 matching translation keys.
- Common job choices; selectable AP/national scheme names from the existing official-source index. Exact selected schemes bypass unrelated topic results. Saved details retain their original dates and stale warnings; Refresh sources remains available.
- Explicit practice notice button, original pasted text preserved during review, company-role suggestions, and preparation-plan handoff to interview practice.
- “Sources and checks” explains the earlier “Evidence in public” page, including its limits and the fact that personal answers/notices are not published on that board.

## Checks before deployment

- Core: 88 tests passed.
- API: 120 tests passed, Ruff clean, Pyright zero errors.
- Web: 8 tests passed; Biome, TypeScript and production build passed.
- Browser accessibility/layout: 57 accessibility states and 108 responsive route checks across all three languages passed.
- Actual browser rehearsal: 10 chapters passed, no browser exceptions, no mocked API responses.
- Sales / Vijayawada: 37 sourced results, remote disabled, each measured within 100 km; no source errors in this query.
- Named scheme: FutureSkills Prime (`fspip`) returned exactly one record, original source link retained. Eligibility unknown; old snapshot warning correctly shown.
- Default question library: 5 past questions returned.
- Fictional placement notice: correct company, role and date extracted; original text remains available.
- Generated sample plan: 21 days, 335 estimated required hours, 42 available hours. Shortfall honestly reported.
- Interview practice: 5 questions answered, feedback and history returned; demo session deleted after completion.
- Evidence endpoint: HTTP 200.

## Limits

These are observed results, not a guarantee that every search has current vacancies. Always verify closing dates and scheme rules with the original source. No job/scheme records were fabricated to fill empty searches. Saved source browsing improves reliability during external outages but does not close the previously documented broad scheme-retrieval accuracy gap. Refer to `AP_SEARCH_VERIFICATION.md` for that build-plan comparison.

The updated `DAARI-user-demo.md` records the production walkthrough results and chapter timestamps after publication. The video uses an explicitly fictional placement notice and sample answers.

Final visual review found a central-sponsored scholarship explicitly for Afghan students in the source library. Scheme admission now excludes titles targeted to foreign students/nationals while preserving overseas-study support for Indian applicants; a regression covers both cases.
