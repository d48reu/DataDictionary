---
phase: 13-tech-debt-jurisdiction-column-preservation
plan: 01
subsystem: database, api
tags: [sqlite, upsert, jurisdiction, cli, enrichment]

# Dependency graph
requires:
  - phase: 08-multi-jurisdiction-foundation
    provides: jurisdiction column on datasets table, registry with display names
  - phase: 11-ai-field-level-descriptions
    provides: ai_description column on columns table, enrich_dataset jurisdiction kwarg
provides:
  - upsert_columns preserves ai_description during re-pull via INSERT OR REPLACE + subquery
  - get_unenriched_datasets returns jurisdiction field for each dataset
  - enrich command resolves jurisdiction to display name and passes to enrich_dataset
  - enrich command skips datasets without jurisdiction with inline warning
  - orphan column cleanup after upsert
affects: [enrich, pull, field-enrichment]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "INSERT OR REPLACE with subquery for preserving computed fields during upsert"
    - "Orphan record cleanup after upsert via NOT IN"

key-files:
  created: []
  modified:
    - src/mdc_encyclopedia/db.py
    - src/mdc_encyclopedia/cli.py

key-decisions:
  - "INSERT OR REPLACE with subquery mirrors existing upsert_dataset() pattern for consistency"
  - "Orphan columns deleted to match API truth rather than keeping stale records"
  - "Registry-based display name with title-case fallback for unknown jurisdictions"

patterns-established:
  - "INSERT OR REPLACE with subquery: preserve computed/AI fields during data refresh"
  - "Registry slug-to-display-name resolution with fallback"

requirements-completed: []

# Metrics
duration: 2min
completed: 2026-02-28
---

# Phase 13 Plan 01: Tech Debt -- Jurisdiction & Column Preservation Summary

**INSERT OR REPLACE with subquery preserves ai_description during pull; enrich command resolves jurisdiction via registry and skips datasets without one**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-28T02:21:12Z
- **Completed:** 2026-02-28T02:23:42Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- upsert_columns() now preserves ai_description values during re-pull using INSERT OR REPLACE with subquery pattern
- Orphan columns (removed by API) are cleaned up after upsert
- get_unenriched_datasets() returns jurisdiction field for each dataset
- enrich command loads registry, resolves jurisdiction slug to display name, and passes to enrich_dataset()
- Datasets without jurisdiction are skipped with inline warning during enrichment

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix upsert_columns() to preserve ai_* fields and delete orphan columns** - `67e989d` (fix)
2. **Task 2: Wire jurisdiction through enrich command and add jurisdiction to get_unenriched_datasets()** - `ff78d25` (feat)

## Files Created/Modified
- `src/mdc_encyclopedia/db.py` - Fixed upsert_columns() with INSERT OR REPLACE + subquery; added d.jurisdiction to get_unenriched_datasets() SELECT
- `src/mdc_encyclopedia/cli.py` - Added registry load, jurisdiction skip logic, and display_name passthrough in enrich command

## Decisions Made
- Used INSERT OR REPLACE with subquery to carry forward ai_description, mirroring the existing upsert_dataset() pattern for consistency
- Orphan columns deleted to match API truth (per user decision in CONTEXT.md)
- Registry-based display name resolution with title-case fallback for unknown jurisdictions
- Preservation is silent -- no log output when ai_* fields are kept

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both tech debt items from v1.1 milestone audit are now closed
- AI summaries will reference the correct county for non-Miami-Dade jurisdictions
- pull operations preserve existing field-level AI descriptions
- No blockers for future phases

## Self-Check: PASSED

- FOUND: src/mdc_encyclopedia/db.py
- FOUND: src/mdc_encyclopedia/cli.py
- FOUND: 13-01-SUMMARY.md
- FOUND: commit 67e989d
- FOUND: commit ff78d25

---
*Phase: 13-tech-debt-jurisdiction-column-preservation*
*Completed: 2026-02-28*
