# Phase 13: Tech Debt — Jurisdiction Wiring & Column Preservation - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Two targeted fixes to CLI internals: (1) wire jurisdiction through to the `enrich` command so AI summaries reference the correct county's departments/services, and (2) fix `upsert_columns()` so standalone `pull` operations preserve existing AI-generated field descriptions. No new capabilities — closing tech debt from v1.1 milestone audit.

</domain>

<decisions>
## Implementation Decisions

### Missing jurisdiction fallback
- When a dataset has no jurisdiction set, `enrich` must SKIP that dataset (do not default to Miami-Dade)
- Print inline warning per skipped dataset: `⚠ Skipping {dataset}: no jurisdiction set`
- No bulk-set command needed — jurisdiction was set during Phase 8; missing ones are edge cases
- `get_unenriched_datasets()` returns ALL datasets (including those without jurisdiction) with a `jurisdiction` field; the enrich command handles skip logic

### Column preservation scope
- Preserve ALL `ai_*` prefixed fields during pull, not just `ai_description` — future-proofs against new AI fields
- New columns from the API get `ai_description = NULL` (shows as unenriched, flagged for future enrichment)
- If the API removes a column that exists locally, DELETE the local record — match API truth, don't keep orphans
- Preservation is silent — no log output when ai_* fields are kept during pull

### Claude's Discretion
- Exact SQL pattern for INSERT OR REPLACE with subquery (success criteria specifies the pattern but Claude picks implementation)
- How jurisdiction gets injected into the AI prompt template
- Any internal refactoring needed to thread jurisdiction through the call chain

</decisions>

<specifics>
## Specific Ideas

- The `upsert_columns()` fix should mirror the existing `upsert_dataset()` pattern — success criteria #4 explicitly calls this out
- The inline skip warning should match the existing CLI output style used by other commands

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 13-tech-debt-jurisdiction-column-preservation*
*Context gathered: 2026-02-27*
