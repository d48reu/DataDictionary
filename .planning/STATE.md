# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-26)

**Core value:** Every Miami-Dade open dataset is discoverable and understandable by a non-technical resident.
**Current focus:** Phase 13 - Tech Debt: Jurisdiction Column Preservation

## Current Position

Phase: 13 of 13 (Tech Debt: Jurisdiction Column Preservation)
Plan: 1 of 1 in current phase (complete)
Status: Phase 13 complete
Last activity: 2026-02-28 -- Completed 13-01 (Jurisdiction Wiring & Column Preservation)

Progress: [================================] 100% (v1.0 complete, phases 8-13 complete)

## Performance Metrics

**Velocity (v1.0 baseline):**
- Total plans completed: 18
- Average duration: 2.7 min
- Total execution time: ~49 min

**By Phase (v1.1):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 08 (Multi-Jurisdiction Foundation) | 2/2 | 8 min | 4.0 min |
| 09 (Atom Feed) | 1/1 | 3 min | 3.0 min |
| 10 (Enriched Catalog Export) | 1/1 | 4 min | 4.0 min |
| 11 (AI Field-Level Descriptions) | 2/2 | 6 min | 3.0 min |
| 12 (Site UI Polish & CI Pipeline) | 1/2 | 4 min | 4.0 min |
| 13 (Tech Debt: Jurisdiction & Column Preservation) | 1/1 | 2 min | 2.0 min |

*Updated after each plan completion*

## Accumulated Context

### Decisions

All v1.0 decisions archived in PROJECT.md Key Decisions table.

- Roadmap: Multi-jurisdiction foundation (Phase 8) must precede all other v1.1 features to avoid retrofitting jurisdiction metadata
- Roadmap: Phases 9, 10, 11 are independent of each other but all depend on Phase 8
- Roadmap: Phase 12 (UI polish + CI) depends on all prior phases being functional
- 08-01: YAML over JSON for jurisdiction config (supports comments, more human-editable)
- 08-01: Synthetic composite key (jurisdiction_arcgis_id) preserves single-column FK pattern
- 08-01: Denormalized ai_description from enrichments into datasets for faster queries
- 08-02: Default parameters for backward compatibility in hub client and normalizer
- 08-02: Generic department guidance for non-Miami-Dade jurisdictions (avoid incorrect assignments)
- 08-02: PROMPT_VERSION bumped to v1.1 for template-driven prompt change
- 09-01: Prefix tag format for feed entry titles: [New], [Removed], [Schema Change]
- 09-01: Tag URI scheme for entry IDs ensures stability across rebuilds
- 09-01: Feed generation gated on --site-url; omitting skips with warning
- 10-01: ext_ prefix convention for AI enrichment fields in DCAT-US JSON avoids namespace collisions
- 10-01: Catalog export runs unconditionally (no gating flag) unlike Atom feed
- 10-01: About page render moved after catalog export so file sizes are available in template
- 11-01: Case-insensitive fallback for column name matching in update_column_ai_descriptions
- 11-01: Best-effort sample value fetch with 10s httpx timeout (non-blocking on failure)
- 11-01: Batch size of 30 columns per API call for field enrichment chunking
- 11-02: DEFAULT_MODEL from models.py used for enrich-fields command (consistent with enrich command pattern)
- 11-02: Retry-once on API failure with 2s delay before skip-and-continue for batch resilience
- 11-02: AI badge uses var(--mdc-blue) CSS custom property for consistent brand styling
- 12-01: Registry-based display names with title-case fallback for unknown jurisdictions
- 12-01: Jurisdiction badge placed before department chip on browse cards for visual priority
- 12-01: Jurisdiction search boost set to 5 (same as description) between keywords and department
- 12-02: Enrichment gated on workflow_dispatch + enrich_ai true, preventing accidental API spend on scheduled runs
- 12-02: enrich-fields added alongside enrich in same conditional step for single opt-in control
- 12-02: Pull output piped to GITHUB_STEP_SUMMARY (tail -20) for concise failure reporting
- 13-01: INSERT OR REPLACE with subquery mirrors upsert_dataset() pattern for column preservation
- 13-01: Orphan columns deleted to match API truth rather than keeping stale records
- 13-01: Registry-based display name resolution with title-case fallback for enrich command

### Pending Todos

None.

### Blockers/Concerns

- Phase 11 field enrichment cost needs re-estimation after Phase 8 adds new jurisdiction data
- RESOLVED: Enrichment command now passes jurisdiction context to build_system_prompt() (wired in 11-01)

## Session Continuity

Last session: 2026-02-28
Stopped at: Completed 13-01-PLAN.md (Jurisdiction Wiring & Column Preservation) -- Phase 13 complete
Resume file: None
