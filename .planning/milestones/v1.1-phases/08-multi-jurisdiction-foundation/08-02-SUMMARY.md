---
phase: 08-multi-jurisdiction-foundation
plan: 02
subsystem: ingestion
tags: [multi-jurisdiction, arcgis-hub, cli, parameterization, normalizer, prompts]

# Dependency graph
requires:
  - phase: 08-01
    provides: "Jurisdiction registry, Schema V3 with jurisdiction/arcgis_id columns"
provides:
  - "Parameterized hub client accepting any ArcGIS Hub base_url"
  - "Jurisdiction-aware normalizer with synthetic IDs and dynamic URL building"
  - "Template-driven enrichment prompts with per-jurisdiction department handling"
  - "Multi-jurisdiction CLI pull command with --jurisdiction flag and error isolation"
  - "Per-jurisdiction stats breakdown in stats command"
  - "V3-compatible upsert_dataset with jurisdiction and arcgis_id columns"
affects: [09-cross-jurisdiction-search, 10-quality-dashboard, 11-field-enrichment, 12-ui-polish]

# Tech tracking
tech-stack:
  added: []
  patterns: [parameterized-hub-client, jurisdiction-aware-normalizer, template-driven-prompts, per-jurisdiction-error-isolation]

key-files:
  created: []
  modified:
    - src/mdc_encyclopedia/ingestion/hub_client.py
    - src/mdc_encyclopedia/ingestion/normalizer.py
    - src/mdc_encyclopedia/enrichment/prompts.py
    - src/mdc_encyclopedia/cli.py
    - src/mdc_encyclopedia/db.py

key-decisions:
  - "Default parameters for backward compatibility -- hub_url defaults to Miami-Dade, jurisdiction defaults to miami-dade"
  - "Generic department guidance for non-Miami-Dade jurisdictions to avoid incorrect department assignments"
  - "PROMPT_VERSION bumped to v1.1 to track template-driven prompt change"

patterns-established:
  - "Parameterized hub client: create_client(base_url) instead of hardcoded constant"
  - "Per-jurisdiction error isolation: try/except around each jurisdiction in pull loop, continue on failure"
  - "Template-driven prompts: build_system_prompt(jurisdiction_display_name) with per-jurisdiction department handling"

requirements-completed: [MULTI-02, MULTI-04]

# Metrics
duration: 4min
completed: 2026-02-27
---

# Phase 8 Plan 2: Multi-Jurisdiction Pipeline Parameterization Summary

**Parameterized hub client, normalizer, and enrichment prompts for any ArcGIS Hub portal, plus CLI pull loop with --jurisdiction flag and per-jurisdiction stats**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-27T05:03:21Z
- **Completed:** 2026-02-27T05:08:13Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Hub client, normalizer, and prompts fully parameterized -- any registered jurisdiction's ArcGIS Hub portal can be pulled without code changes
- CLI pull command loops all registered jurisdictions (or one via --jurisdiction flag) with per-jurisdiction error isolation
- Stats command shows per-jurisdiction dataset count breakdown table
- upsert_dataset updated for V3 schema compatibility with jurisdiction and arcgis_id columns

## Task Commits

Each task was committed atomically:

1. **Task 1: Parameterize hub client, normalizer, and enrichment prompts** - `58302f1` (feat)
2. **Task 2: Wire CLI pull command for multi-jurisdiction loop and add stats breakdown** - `b3c667c` (feat)

## Files Created/Modified
- `src/mdc_encyclopedia/ingestion/hub_client.py` - create_client() accepts base_url parameter, DEFAULT_HUB_URL replaces HUB_BASE_URL
- `src/mdc_encyclopedia/ingestion/normalizer.py` - normalize_hub_dataset() accepts jurisdiction and hub_url, generates synthetic IDs, builds URLs from hub_url
- `src/mdc_encyclopedia/enrichment/prompts.py` - SYSTEM_PROMPT_TEMPLATE with build_system_prompt(), Miami-Dade dept list vs generic guidance, PROMPT_VERSION v1.1
- `src/mdc_encyclopedia/cli.py` - Multi-jurisdiction pull loop with --jurisdiction/-j flag, per-jurisdiction field fetch, results table, stats jurisdiction breakdown, load_registry import
- `src/mdc_encyclopedia/db.py` - upsert_dataset includes jurisdiction and arcgis_id columns for V3 schema compatibility

## Decisions Made
- Used default parameters (hub_url, jurisdiction) for backward compatibility so existing single-jurisdiction code continues to work without changes
- Used generic department guidance ("identify the most likely {jurisdiction} government department") for non-Miami-Dade jurisdictions rather than attempting to list departments for each county
- Bumped PROMPT_VERSION from v1.0 to v1.1 to track the template-driven prompt change in enrichment records

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated upsert_dataset for V3 schema compatibility**
- **Found during:** Task 1 (parameterization)
- **Issue:** The existing upsert_dataset INSERT statement did not include the jurisdiction and arcgis_id columns required by Schema V3, which would cause pipeline failures when the normalizer returns these new fields
- **Fix:** Updated the INSERT OR REPLACE statement in upsert_dataset to include jurisdiction and arcgis_id columns with safe defaults for backward compatibility
- **Files modified:** src/mdc_encyclopedia/db.py
- **Verification:** normalizer output dict includes jurisdiction/arcgis_id keys, upsert_dataset SQL matches
- **Committed in:** 58302f1 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential fix for V3 schema compatibility. No scope creep.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Full multi-jurisdiction pipeline is operational: registry -> hub client -> normalizer -> upsert -> stats
- Ready for Phase 9 (cross-jurisdiction search), Phase 10 (quality dashboard), Phase 11 (field enrichment)
- The enrichment command will need future updates to pass jurisdiction context to build_system_prompt() (out of scope for this plan, tracked for Phase 11)

## Self-Check: PASSED

All files and commits verified:
- FOUND: src/mdc_encyclopedia/ingestion/hub_client.py
- FOUND: src/mdc_encyclopedia/ingestion/normalizer.py
- FOUND: src/mdc_encyclopedia/enrichment/prompts.py
- FOUND: src/mdc_encyclopedia/cli.py
- FOUND: src/mdc_encyclopedia/db.py
- FOUND: commit 58302f1 (Task 1)
- FOUND: commit b3c667c (Task 2)

---
*Phase: 08-multi-jurisdiction-foundation*
*Completed: 2026-02-27*
