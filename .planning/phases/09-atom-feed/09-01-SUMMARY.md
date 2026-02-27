---
phase: 09-atom-feed
plan: 01
subsystem: site
tags: [atom, feed, feedgen, rss, xml, autodiscovery]

# Dependency graph
requires:
  - phase: 08-multi-jurisdiction
    provides: jurisdiction field on datasets table for feed summaries
provides:
  - Atom 1.0 feed generation module (feed.py)
  - --site-url CLI parameter on export command
  - HTML autodiscovery link tag for feed readers
affects: [12-ui-polish]

# Tech tracking
tech-stack:
  added: [feedgen]
  patterns: [conditional feature gating via CLI parameter, tag URI for entry IDs]

key-files:
  created:
    - src/mdc_encyclopedia/site/feed.py
  modified:
    - pyproject.toml
    - src/mdc_encyclopedia/cli.py
    - src/mdc_encyclopedia/site/generator.py
    - src/mdc_encyclopedia/site/context.py
    - src/mdc_encyclopedia/site/templates/base.html

key-decisions:
  - "Prefix tag format for entry titles: [New], [Removed], [Schema Change]"
  - "Tag URI scheme for entry IDs ensures stability across rebuilds"
  - "Jurisdiction displayed as title-cased slug rather than requiring registry lookup"
  - "Feed generation gated on --site-url presence; omitting skips feed with warning"

patterns-established:
  - "Conditional feature gating: CLI parameter controls optional output generation"
  - "site_url passed through env.globals for template access"

requirements-completed: [FEED-01, FEED-02, FEED-03]

# Metrics
duration: 3min
completed: 2026-02-27
---

# Phase 9 Plan 1: Atom Feed Summary

**Atom 1.0 feed generation using feedgen with jurisdiction-aware change summaries, --site-url CLI gating, and HTML autodiscovery**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-27T06:20:36Z
- **Completed:** 2026-02-27T06:23:40Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Created feed.py module generating valid Atom 1.0 XML with tag URI entry IDs
- Added --site-url CLI parameter that gates feed generation; omitting it prints a warning and skips
- Wired feed into export pipeline: cli.py -> generator.py -> feed.py
- Added conditional autodiscovery `<link>` tag in base.html template
- Updated changes query to include jurisdiction for context-rich feed summaries
- Feed entries use prefix tags ([New], [Removed], [Schema Change]) and mention jurisdiction when available

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Atom feed module with feedgen dependency and jurisdiction-aware change data** - `0c88ec1` (feat)
2. **Task 2: Wire feed into CLI export pipeline and add HTML autodiscovery tag** - `3ac05f0` (feat)

## Files Created/Modified
- `src/mdc_encyclopedia/site/feed.py` - New module: generate_atom_feed() with tag URI IDs, prefix titles, jurisdiction summaries
- `pyproject.toml` - Added feedgen>=1.0,<2.0 dependency and feed.py force-include
- `src/mdc_encyclopedia/cli.py` - Added --site-url option, warning on omission, feed entries in summary table
- `src/mdc_encyclopedia/site/generator.py` - Added site_url parameter, env.globals, conditional feed generation call
- `src/mdc_encyclopedia/site/context.py` - Added d.jurisdiction to changes query SELECT
- `src/mdc_encyclopedia/site/templates/base.html` - Added conditional autodiscovery link tag

## Decisions Made
- Prefix tag format chosen for entry titles per user decision: [New], [Removed], [Schema Change]
- Tag URI scheme (tag:domain,date:dataset_id/change_type) ensures stable entry IDs across rebuilds
- Jurisdiction slug title-cased for display (e.g., "miami-dade" -> "Miami Dade") instead of loading full registry
- Feed generation gated on --site-url; clean warning when omitted rather than error

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added feed.py to hatch force-include**
- **Found during:** Task 1
- **Issue:** pyproject.toml force-include section lists all site module files individually for wheel builds; feed.py would be missing from installed packages
- **Fix:** Added force-include entry for feed.py
- **Files modified:** pyproject.toml
- **Verification:** pip install -e . succeeds, import works
- **Committed in:** 0c88ec1 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for correct packaging. No scope creep.

## Issues Encountered
None - plan executed smoothly.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Atom feed generation complete and integrated into export pipeline
- Feed works with zero entries (empty catalog) and populated catalogs
- Ready for Phase 10 (GitHub Actions) which can use --site-url in CI builds
- Ready for Phase 12 (UI polish) which may want to style the feed link in navigation

## Self-Check: PASSED

All 7 files verified present. Both task commits (0c88ec1, 3ac05f0) found in git log.

---
*Phase: 09-atom-feed*
*Completed: 2026-02-27*
