# Phase 4: Quality Audit - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Every dataset gets a composite quality score based on staleness, completeness, and documentation. The `mdc-encyclopedia audit` command analyzes datasets and writes scores to SQLite. The `mdc-encyclopedia stats` command displays a Rich-formatted summary. This phase does NOT build the static site quality page (Phase 6) or change detection (Phase 5).

</domain>

<decisions>
## Implementation Decisions

### Quality scoring model
- Letter grades (A-F) for composite quality score
- Freshness-heavy weighting: ~50% freshness, ~30% metadata completeness, ~20% column documentation coverage
- Store both the letter grade AND individual findings per dataset (e.g., "missing description", "stale by 6 months")
- Findings stored in SQLite alongside the score for downstream use by static site (Phase 6)
- When a dimension can't be scored (e.g., no enrichment data for expected frequency), score what's available and note gaps as "N/A" in findings — do not penalize or assume worst case

### Staleness thresholds
- Primary: Use AI-inferred expected update frequency from enrichment (ENRICH-05) when available — compare last_updated against that expectation
- Fallback (no enrichment): Fixed tiers — >90 days = possibly stale, >180 days = stale, >365 days = abandoned
- Datasets with AI-inferred frequency of "static" or "one-time" are auto-exempt from staleness scoring
- Empty dataset definition: zero rows reported in metadata OR missing row count entirely — both flagged

### Claude's Discretion
- Audit output format and presentation (how `audit` command displays progress and results)
- Stats dashboard layout (how `stats` command organizes the Rich-formatted summary)
- Exact letter grade cutoff thresholds (what numeric score maps to A vs B vs C)
- SQLite schema design for audit_scores and findings tables
- How "poorly described" is defined for AUDIT-03

</decisions>

<specifics>
## Specific Ideas

- Government data updates can be slow — the more lenient 90/180/365 day tiers reflect that reality vs aggressive 30/90/365
- The scoring model should be transparent enough that a resident could understand WHY a dataset got its grade
- Individual findings are important for the static site later (Phase 6 SITE-08 data quality report page)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-quality-audit*
*Context gathered: 2026-02-25*
