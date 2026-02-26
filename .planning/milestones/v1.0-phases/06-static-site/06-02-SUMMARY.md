---
phase: 06-static-site
plan: 02
subsystem: site
tags: [lunr, lunr.js, search, homepage, jinja2, client-side-search]

# Dependency graph
requires:
  - phase: 06-static-site
    plan: 01
    provides: Site generator pipeline, base template, CSS system, search.js stub
provides:
  - Lunr.py search index builder generating search-index.json and search-data.json
  - Client-side instant search dropdown via Lunr.js with title/snippet/department results
  - Search-first homepage with tagline, stat cards, and category browse grid
  - Recently updated datasets section on homepage
affects: [06-03, 06-04]

# Tech tracking
tech-stack:
  added: [lunr.js-cdn]
  patterns: [pre-built-search-index, client-side-search, search-first-homepage]

key-files:
  created:
    - src/mdc_encyclopedia/site/search_index.py
  modified:
    - src/mdc_encyclopedia/site/static/search.js
    - src/mdc_encyclopedia/site/templates/index.html
    - src/mdc_encyclopedia/site/generator.py
    - src/mdc_encyclopedia/site/templates/base.html
    - src/mdc_encyclopedia/site/static/style.css

key-decisions:
  - "Lunr.js loaded from CDN (jsdelivr) rather than vendored file to reduce repo size"
  - "Search index uses field boosts: title(10) > keywords(8) > description(5) > department/category(3)"
  - "Wildcard suffix (query + '*') used for as-you-type matching with Lunr fallback on syntax errors"
  - "Search dropdown capped at 8 results -- no pagination in dropdown"
  - "Homepage category grid shows top 15 categories sorted alphabetically with dataset counts"

patterns-established:
  - "Pre-built search: index built at export time (Python lunr.py), loaded at runtime (JS Lunr.js)"
  - "Search data separation: search-index.json for Lunr queries, search-data.json for result display metadata"
  - "Homepage hero pattern: tagline + large search bar + stat cards + category browse"

requirements-completed: [SITE-01]

# Metrics
duration: 4min
completed: 2026-02-26
---

# Phase 6 Plan 02: Homepage & Search Summary

**Lunr.js pre-built search index with instant dropdown results, search-first homepage with stat cards and category browse grid**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-26T05:32:46Z
- **Completed:** 2026-02-26T05:36:37Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Built Lunr.py search index generator that creates search-index.json and search-data.json at export time with field boosts for title, keywords, description, department, and category
- Replaced stub search.js with full client-side search: instant dropdown showing title, snippet, and department chip for top 8 results as user types
- Created search-first homepage with centered tagline, large search bar with CSS magnifying glass icon, 3 stat cards (total datasets, % described, new this week), category browse grid, and recently updated datasets section

## Task Commits

Each task was committed atomically:

1. **Task 1: Lunr.py search index builder and search.js dropdown** - `3441bdb` (feat)
2. **Task 2: Search-first homepage with stat cards and category links** - `785ed3e` (feat)

## Files Created/Modified
- `src/mdc_encyclopedia/site/search_index.py` - Lunr.py index builder: builds documents with boosts, serializes index, writes JSON files
- `src/mdc_encyclopedia/site/static/search.js` - Full client-side search: fetches index on load, runs wildcard queries on keyup, renders dropdown with results
- `src/mdc_encyclopedia/site/templates/index.html` - Homepage template: hero search section, stat cards row, category browse grid, recent datasets
- `src/mdc_encyclopedia/site/generator.py` - Imports and calls build_search_index after page rendering, passes recent_datasets to homepage context
- `src/mdc_encyclopedia/site/templates/base.html` - Added Lunr.js CDN script tag before search.js
- `src/mdc_encyclopedia/site/static/style.css` - Hero section, search dropdown, category grid, and recent datasets CSS

## Decisions Made
- Used Lunr.js CDN (jsdelivr v2.3.9) rather than vendoring the file to keep repo clean
- Field boost weights: title(10) > keywords(8) > description(5) > department/category(3) for relevance
- Wildcard suffix on queries (`query + '*'`) enables as-you-type matching; try-catch fallback handles Lunr syntax errors
- Dropdown limited to 8 results maximum, no pagination -- search is for quick navigation
- Homepage category grid caps at 15 categories with "View all" link when more exist
- Recently updated datasets section only renders when data is available (graceful empty handling)
- Empty datasets list writes empty JSON objects rather than throwing errors

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Linter auto-committed Task 2 files with unrelated template changes**
- **Found during:** Task 2 commit
- **Issue:** An automated process committed index.html and generator.py changes alongside unrelated template improvements (dataset.html, changes.html, quality.html, context.py, style.css additions) under a single commit
- **Fix:** Accepted the combined commit since Task 2 work is verified present; noted the commit contains additional template work from future plans
- **Files affected:** Commit 785ed3e includes both Task 2 homepage work and forward-looking template improvements
- **Verification:** Verified index.html content in commit matches the intended homepage template

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor commit organization issue only. All Task 2 code is correct and verified.

## Issues Encountered
None -- both tasks executed smoothly.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Search index builds during export; homepage renders with all sections
- Category browse links ready for Plan 03 browse page implementation
- Dataset detail links from search results ready for Plan 03/04 detail pages
- CSS for hero, dropdown, category grid, stat cards, and recent datasets all in place
- Lunr.js CDN loaded globally via base.html for all pages

---
*Phase: 06-static-site*
*Completed: 2026-02-26*
