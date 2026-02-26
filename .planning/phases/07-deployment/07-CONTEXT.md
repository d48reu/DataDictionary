# Phase 7: Deployment - Context

**Gathered:** 2026-02-26
**Status:** Ready for planning

<domain>
## Phase Boundary

GitHub Actions workflow that auto-refreshes the encyclopedia weekly and deploys to GitHub Pages. Supports manual dispatch with options. Push-to-main triggers site re-export. ANTHROPIC_API_KEY is optional — workflow runs without it.

</domain>

<decisions>
## Implementation Decisions

### Enrichment guardrails
- Auto-enrich only if fewer than 25 new datasets are found in the pull
- If 25+ new datasets appear, skip enrichment and auto-create a GitHub issue ("25+ new datasets found, manual enrichment needed")
- Pin to Haiku model (`--model haiku`) in CI for cost savings — user can run Sonnet manually for higher quality
- When no ANTHROPIC_API_KEY secret is set, skip enrichment entirely (no error)

### Workflow triggers
- **Weekly cron:** Full pipeline — pull, audit, diff, enrich (if under threshold and key exists), export, deploy
- **Push to main:** Export-only — re-export site from current DB state and deploy (no pull, no enrich, fast)
- **Manual dispatch (workflow_dispatch):** Full pipeline with two input options:
  - `skip_enrichment` (boolean) — skip the enrich step entirely
  - `force_enrich` (boolean) — override the 25-dataset threshold and enrich all unenriched datasets

### Claude's Discretion
- Cron schedule timing (day of week, hour)
- GitHub Pages deployment method (gh-pages branch vs actions artifact)
- Workflow job structure (single job vs matrix)
- How to persist SQLite DB between workflow runs (artifact caching strategy)
- Error handling and retry logic for API calls in CI

</decisions>

<specifics>
## Specific Ideas

- Push-to-main should be fast — just re-export and deploy, no API calls
- The GitHub issue created when enrichment is skipped should be actionable: include the count of new datasets and a suggested command to run manually

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-deployment*
*Context gathered: 2026-02-26*
