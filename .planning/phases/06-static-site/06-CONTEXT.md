# Phase 6: Static Site - Context

**Gathered:** 2026-02-26
**Status:** Ready for planning

<domain>
## Phase Boundary

A fully static, searchable HTML encyclopedia where Miami-Dade residents can browse, search, and understand every open dataset in the catalog. Generates from SQLite data via `mdc-encyclopedia export`. Consumes enrichment (Phase 3), quality audit (Phase 4), and change detection (Phase 5) data. Deployment/CI is Phase 7.

</domain>

<decisions>
## Implementation Decisions

### Homepage & search layout
- Search-first homepage: large search bar front and center with tagline above ("Every county dataset, explained in plain English")
- Instant dropdown search results as user types (like Spotlight/Algolia), top 5-8 matches
- Each search result shows: dataset title, 1-line AI description snippet, department tag
- Below search: 3 stat cards (total datasets, % described, new this week) plus a row of top category/department browse links
- No pagination on search dropdown — click result to go to dataset page, or browse categories

### Visual tone & personality
- Modern civic tech aesthetic: clean, accessible, confident with generous whitespace and clear hierarchy
- Not government-institutional stuffy, not editorial/magazine — professional startup feel applied to civic data
- MDC palette: #003366 (primary blue), white, amber for accents/highlights

### Dataset listing style
- Compact list rows on browse pages: one dataset per row with title, 1-line description, department chip, quality dot
- Dense and scannable for 450+ datasets — similar density to GitHub repo lists
- Not cards — too much vertical space for this volume of data

### Quality grade display
- Letter grade badges: A, B, C, D, F with color coding (green through red)
- Shown on both listing rows and individual dataset detail pages
- Familiar grading system that residents understand immediately

### Freshness indicators
- Relative time label ("Updated 3 days ago") plus colored dot (green/yellow/red)
- Color based on staleness relative to expected update frequency from audit data
- Shown on listings and detail pages

### Claude's Discretion
- Typography and font choices
- Exact spacing and card/row component sizing
- Search index library choice (Lunr.js vs Fuse.js)
- Dataset detail page section ordering and layout
- Navigation structure (top nav, sidebar, breadcrumbs)
- Category/browse page filtering UX
- "What Changed" page layout
- Data quality report page layout
- About/disclaimer page content structure
- Mobile responsive breakpoints and layout adjustments
- Empty state designs
- Error state handling

</decisions>

<specifics>
## Specific Ideas

- Homepage should feel like the search-first mockup: tagline, big search bar, stat cards, category links — clean and purposeful
- Search dropdown should feel instant and lightweight, not a full page reload
- Letter grades make quality immediately understandable — a resident knows "C" means mediocre without explanation
- Freshness dots give at-a-glance health — green means current, red means potentially stale
- Compact list rows keep the site feeling like a working reference tool, not a marketing site

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-static-site*
*Context gathered: 2026-02-26*
