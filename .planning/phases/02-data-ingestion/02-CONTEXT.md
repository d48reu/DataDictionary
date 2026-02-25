# Phase 2: Data Ingestion - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Pull the complete Miami-Dade open data catalog from both Socrata Discovery API and ArcGIS Hub API into the local SQLite database via `mdc-encyclopedia pull`. Includes pagination, column metadata fetching, deduplication of cross-portal datasets, and rate limiting. Enrichment, auditing, and display are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Deduplication strategy
- Match datasets across portals using **normalized title matching** (lowercase, strip whitespace)
- **Exact match only** — no fuzzy matching. Safer: avoids merging distinct datasets like "Building Permits" and "Building Permits - Active"
- When a dataset appears on both portals, **Socrata is the canonical record** (richer column metadata). ArcGIS URL stored as secondary source link. One row in datasets table, both links preserved.
- Dedup reporting: **summary count by default**, detailed per-pair list with `--verbose` flag

### Rate limiting & resilience
- Rate limit: 1 request/second as specified in requirements
- On API failure: **retry with exponential backoff** (3 retries: 2s, 4s, 8s). After 3 failures, skip that dataset and continue. Report skipped datasets at the end.
- Re-pull behavior: **full refresh** every time (upsert). No incremental/skip-if-recent logic. Designed for a weekly refresh workflow.

### Progress & output
- **Two-stage Rich progress bar**: show portal name + bar for each stage ("Socrata [████░░░░] 142/350 datasets" then "ArcGIS Hub [████░░░░] 89/200 datasets")
- After completion: **Rich summary table** showing total datasets, per-portal counts, deduplicated count, new vs updated, skipped/failed (if any), elapsed time

### Claude's Discretion
- HTTP client choice (requests, httpx, etc.)
- Exact normalization logic for title matching
- Pagination implementation details per API
- How to structure the ingestion module internally

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-data-ingestion*
*Context gathered: 2026-02-24*
