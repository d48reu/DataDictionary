---
phase: 06-static-site
plan: 01
subsystem: site
tags: [jinja2, lunr, python-slugify, static-site, css, responsive]

# Dependency graph
requires:
  - phase: 05-change-detection
    provides: changes table for What Changed page
  - phase: 04-quality-audit
    provides: audit_scores table for quality grades and findings
  - phase: 03-ai-enrichment
    provides: enrichments table for AI-generated descriptions
provides:
  - Site generator pipeline (SQLite -> Python dicts -> Jinja2 -> HTML)
  - Context query layer (build_site_data with JOIN across all tables)
  - Base HTML template with MDC branding and responsive layout
  - Complete CSS system with grade badges, freshness dots, stat cards
  - CLI export command generating static site directory
  - CLI serve command for local preview
affects: [06-02, 06-03, 06-04]

# Tech tracking
tech-stack:
  added: [Jinja2, lunr, python-slugify]
  patterns: [template-inheritance, context-dict-pipeline, slug-collision-detection]

key-files:
  created:
    - src/mdc_encyclopedia/site/__init__.py
    - src/mdc_encyclopedia/site/context.py
    - src/mdc_encyclopedia/site/generator.py
    - src/mdc_encyclopedia/site/templates/base.html
    - src/mdc_encyclopedia/site/templates/index.html
    - src/mdc_encyclopedia/site/templates/browse.html
    - src/mdc_encyclopedia/site/templates/dataset.html
    - src/mdc_encyclopedia/site/templates/changes.html
    - src/mdc_encyclopedia/site/templates/quality.html
    - src/mdc_encyclopedia/site/templates/about.html
    - src/mdc_encyclopedia/site/static/style.css
    - src/mdc_encyclopedia/site/static/search.js
  modified:
    - pyproject.toml
    - src/mdc_encyclopedia/cli.py

key-decisions:
  - "Used python-slugify for URL slug generation with collision detection via dataset ID suffix"
  - "Pure CSS hamburger menu (checkbox hack) to avoid JavaScript dependency for navigation"
  - "Related datasets scored by category match (3 pts) plus shared keywords (1 pt each)"
  - "Added force-include in pyproject.toml to ensure templates and static files ship in wheel"

patterns-established:
  - "Template inheritance: all page templates extend base.html"
  - "Context pipeline: build_site_data() returns complete dict for all page rendering"
  - "Generator pattern: generate_site() orchestrates all rendering via individual _render_* functions"

requirements-completed: [CLI-08, CLI-09, SITE-10, SITE-11, SITE-12, SITE-13]

# Metrics
duration: 4min
completed: 2026-02-26
---

# Phase 6 Plan 01: Site Generator Foundation Summary

**Jinja2 static site generator with SQLite context queries, MDC-branded base template, responsive CSS system, and CLI export/serve commands**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-26T05:25:48Z
- **Completed:** 2026-02-26T05:29:49Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- Built complete rendering pipeline: SQLite -> context dicts -> Jinja2 -> static HTML files
- Created responsive base template with MDC blue (#003366) branding, hamburger menu, and disclaimer footer
- Implemented full CSS system with grade badges, freshness dots, stat cards, dataset rows, and responsive breakpoints at 768px and 480px
- CLI export command generates site/ directory with Rich progress spinner and summary table
- CLI serve command starts local HTTP server with directory validation

## Task Commits

Each task was committed atomically:

1. **Task 1: Site package with context queries and generator orchestrator** - `eae6fe1` (feat)
2. **Task 2: Base template, CSS system, and CLI export/serve commands** - `fbaa504` (feat)

## Files Created/Modified
- `src/mdc_encyclopedia/site/__init__.py` - Site package init
- `src/mdc_encyclopedia/site/context.py` - SQLite query helpers building template context dicts (build_site_data, related datasets, slug generation)
- `src/mdc_encyclopedia/site/generator.py` - Main export orchestrator with Jinja2 setup and page rendering
- `src/mdc_encyclopedia/site/templates/base.html` - Base layout with nav, footer, CSS/JS includes, hamburger menu
- `src/mdc_encyclopedia/site/templates/index.html` - Homepage stub extending base
- `src/mdc_encyclopedia/site/templates/browse.html` - Browse stub extending base
- `src/mdc_encyclopedia/site/templates/dataset.html` - Dataset detail stub extending base
- `src/mdc_encyclopedia/site/templates/changes.html` - Changes stub extending base
- `src/mdc_encyclopedia/site/templates/quality.html` - Quality report stub extending base
- `src/mdc_encyclopedia/site/templates/about.html` - About stub extending base
- `src/mdc_encyclopedia/site/static/style.css` - Complete CSS with MDC palette, responsive layout, grade badges
- `src/mdc_encyclopedia/site/static/search.js` - Stub search module for Plan 02
- `pyproject.toml` - Added Jinja2, lunr, python-slugify dependencies and force-include for templates/static
- `src/mdc_encyclopedia/cli.py` - Real export and serve commands replacing stubs

## Decisions Made
- Used python-slugify for URL slug generation with collision detection via dataset ID suffix
- Pure CSS hamburger menu (checkbox hack) to avoid JavaScript dependency for navigation
- Related datasets scored by category match (3 pts) plus shared keywords (1 pt each), top 5 returned
- Added force-include in pyproject.toml to ensure templates and static files ship in wheel
- Generator creates all subdirectories (browse/, dataset/, changes/, quality/, about/, static/) even when empty

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 6 stub templates ready for Plans 02-04 to fill with real content
- Context query layer provides complete site_data dict for template rendering
- CSS system has all visual components (grades, freshness dots, stat cards, dataset rows, responsive breakpoints)
- Search.js stub ready for Lunr.js integration in Plan 02

## Self-Check: PASSED

All 14 files verified present. Both task commits (eae6fe1, fbaa504) verified in git history.

---
*Phase: 06-static-site*
*Completed: 2026-02-26*
