---
phase: 02-data-ingestion
plan: 01
subsystem: ingestion
tags: [httpx, tenacity, arcgis-hub, pagination, rate-limiting, retry, normalizer, upsert, sqlite]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "SQLite database module with datasets/columns tables, installable package skeleton"
provides:
  - "Paginated ArcGIS Hub Search API client with rate limiting and retry"
  - "Data normalizer mapping Hub API responses to datasets table schema"
  - "ESRI field type mapping for column metadata"
  - "upsert_dataset and upsert_columns functions in db.py"
  - "Within-catalog duplicate title detection"
affects: [02-02-PLAN, 03-ai-enrichment, 04-quality-audit, 05-change-detection]

# Tech tracking
tech-stack:
  added: [httpx, tenacity]
  patterns: [paginated-generator, tenacity-retry-decorator, rate-limit-sleep, insert-or-replace-upsert, html-strip-normalize]

key-files:
  created:
    - src/mdc_encyclopedia/ingestion/__init__.py
    - src/mdc_encyclopedia/ingestion/hub_client.py
    - src/mdc_encyclopedia/ingestion/normalizer.py
  modified:
    - pyproject.toml
    - src/mdc_encyclopedia/db.py

key-decisions:
  - "Used synchronous httpx (not async) since rate limiting at 1 req/s makes async pointless"
  - "Rate limiting via time.sleep before each request ensures compliance regardless of retry state"
  - "Within-catalog dedup uses normalized title exact match per locked decision (no fuzzy matching)"
  - "Download URL constructed for Feature Services only; None for File Geodatabases"

patterns-established:
  - "Paginated generator with rel=next link following for ArcGIS Hub API"
  - "tenacity @retry decorator with stop_after_attempt(3) and wait_exponential(2,2,8)"
  - "ESRI_TYPE_MAP dict for normalizing ArcGIS field types to simplified names"
  - "upsert pattern: check existence then INSERT OR REPLACE for new/updated tracking"

requirements-completed: [INGEST-01, INGEST-02, INGEST-05, INGEST-06]

# Metrics
duration: 3min
completed: 2026-02-25
---

# Phase 2 Plan 01: Hub API Client, Normalizer, and Database Upserts Summary

**Paginated ArcGIS Hub Search API client with httpx/tenacity retry, data normalizer with HTML stripping and timestamp conversion, and SQLite upsert functions for full-refresh ingestion**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-25T01:41:22Z
- **Completed:** 2026-02-25T01:44:06Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Hub API client that paginates through all ~576 datasets using rel=next links, with 1 req/s rate limiting and 3-attempt exponential backoff retry
- Data normalizer that converts raw Hub API GeoJSON features to the datasets table schema, stripping HTML from descriptions, converting millisecond timestamps to ISO 8601, parsing categories, and mapping ArcGIS field types
- Database upsert functions (upsert_dataset, upsert_columns) that support the full-refresh pull workflow with new/updated tracking
- Within-catalog duplicate title detection using normalized (lowercase, stripped) exact matching

## Task Commits

Each task was committed atomically:

1. **Task 1: Add dependencies and create Hub API client** - `4626cb5` (feat)
2. **Task 2: Create normalizer module and add database upsert functions** - `c079690` (feat)

## Files Created/Modified
- `pyproject.toml` - Added httpx>=0.28 and tenacity>=9.0 to dependencies
- `src/mdc_encyclopedia/ingestion/__init__.py` - Package marker for ingestion subpackage
- `src/mdc_encyclopedia/ingestion/hub_client.py` - Paginated API client with create_client, fetch_catalog_page, fetch_all_datasets, detect_duplicate_titles
- `src/mdc_encyclopedia/ingestion/normalizer.py` - strip_html, ms_to_iso, normalize_hub_dataset, normalize_field, ESRI_TYPE_MAP
- `src/mdc_encyclopedia/db.py` - Added upsert_dataset and upsert_columns functions

## Decisions Made
- Used synchronous httpx rather than async -- at 1 request/second rate limit, async adds complexity with zero throughput benefit
- Placed time.sleep(RATE_LIMIT_SECONDS) inside fetch_catalog_page before the HTTP call, ensuring rate limiting applies even during retry sequences
- Within-catalog dedup uses exact match on lowercase stripped titles per locked decision; no fuzzy matching to avoid merging distinct datasets
- Download URL is constructed only for Feature Service type datasets; File Geodatabases get None since they lack REST download endpoints

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Hub client, normalizer, and upsert functions are ready for Plan 02-02 (field metadata fetcher and CLI pull command)
- The pull command will import fetch_all_datasets, normalize_hub_dataset, and upsert_dataset to orchestrate the full ingestion flow
- detect_duplicate_titles is available for the pull command's summary report

## Self-Check: PASSED

- All 5 created/modified files exist at expected paths
- Commit `4626cb5` (Task 1) verified in git log
- Commit `c079690` (Task 2) verified in git log

---
*Phase: 02-data-ingestion*
*Completed: 2026-02-25*
