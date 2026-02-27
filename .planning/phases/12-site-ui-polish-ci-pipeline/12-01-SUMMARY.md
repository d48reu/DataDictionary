---
phase: 12-site-ui-polish-ci-pipeline
plan: 01
subsystem: ui
tags: [jinja2, lunr, css, javascript, jurisdiction, filtering]

# Dependency graph
requires:
  - phase: 08-multi-jurisdiction-foundation
    provides: "Jurisdiction registry (load_registry), jurisdiction slug on datasets"
provides:
  - "Jurisdiction dropdown filter on browse pages"
  - "Colored jurisdiction badges on browse cards and dataset detail pages"
  - "Jurisdiction field in Lunr search index with boost 5"
  - "Jurisdiction in search result display data"
affects: [12-site-ui-polish-ci-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Jurisdiction badge color convention: miami-dade=blue, broward=orange, miami=green"]

key-files:
  created: []
  modified:
    - src/mdc_encyclopedia/site/generator.py
    - src/mdc_encyclopedia/site/search_index.py
    - src/mdc_encyclopedia/site/templates/browse.html
    - src/mdc_encyclopedia/site/templates/dataset.html
    - src/mdc_encyclopedia/site/static/filter.js
    - src/mdc_encyclopedia/site/static/style.css

key-decisions:
  - "Registry-based display names with title-case fallback for unknown jurisdictions"
  - "Jurisdiction badge placed before department chip on browse cards for visual priority"
  - "Jurisdiction search boost set to 5 (same as description) between keywords and department"

patterns-established:
  - "Jurisdiction badge CSS class convention: .jurisdiction-{slug} for per-jurisdiction colors"
  - "4-tuple filter extraction pattern: (formats, publishers, tags, jurisdictions)"

requirements-completed: [MULTI-05, MULTI-06, MULTI-07]

# Metrics
duration: 3min
completed: 2026-02-27
---

# Phase 12 Plan 01: Jurisdiction UI Summary

**Jurisdiction dropdown filter, colored badges on browse/detail pages, and Lunr search index integration for multi-jurisdiction browsing**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-27T23:24:11Z
- **Completed:** 2026-02-27T23:27:34Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Browse pages now have a 4th dropdown filter for jurisdiction with display-name labels from the registry
- Colored jurisdiction badges (blue for Miami-Dade, orange for Broward, green for Miami) appear on browse cards and dataset detail headers
- Lunr search index includes jurisdiction field at boost 5, enabling users to search by jurisdiction name
- Client-side filtering in filter.js fully supports jurisdiction with chip rendering and clear-all behavior

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire jurisdiction display names into generator and search index** - `1e9db18` (feat)
2. **Task 2: Add jurisdiction filter, badges, and styles to templates and JS** - `5621ee1` (feat)

## Files Created/Modified
- `src/mdc_encyclopedia/site/generator.py` - Added load_registry import, jurisdiction_display_name injection, 4-tuple filter extraction, jurisdiction template context
- `src/mdc_encyclopedia/site/search_index.py` - Added jurisdiction field to lunr documents (boost 5) and search data
- `src/mdc_encyclopedia/site/templates/browse.html` - Added jurisdiction dropdown, data-jurisdiction attribute, jurisdiction badge on cards
- `src/mdc_encyclopedia/site/templates/dataset.html` - Added jurisdiction badge in dataset header
- `src/mdc_encyclopedia/site/static/filter.js` - Added jurisdiction filtering, chip rendering, event listener, clear handler
- `src/mdc_encyclopedia/site/static/style.css` - Added .jurisdiction-badge base styles and per-jurisdiction color classes

## Decisions Made
- Used registry-based display names with title-case fallback for unknown jurisdiction slugs
- Placed jurisdiction badge before department chip on browse cards for visual hierarchy (jurisdiction is higher-level context)
- Set jurisdiction search boost to 5 (matching description), positioned between keywords (8) and department (3) in the lunr field list

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Jurisdiction UI is fully wired and ready for visual verification after site export
- Plan 02 (CI pipeline or remaining polish) can proceed independently

## Self-Check: PASSED

All 6 modified files exist. Both task commits verified (1e9db18, 5621ee1). Summary file exists.

---
*Phase: 12-site-ui-polish-ci-pipeline*
*Completed: 2026-02-27*
