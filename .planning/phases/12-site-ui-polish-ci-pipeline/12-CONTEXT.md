# Phase 12: Site UI Polish and CI Pipeline - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Surface jurisdiction context throughout the browsing experience (filter dropdown, badges, search index) and automate the full multi-jurisdiction pipeline in GitHub Actions CI. Scope: MULTI-05 (jurisdiction filter), MULTI-06 (jurisdiction badges), MULTI-07 (search index), MULTI-08 (CI pipeline).

</domain>

<decisions>
## Implementation Decisions

### CI Pipeline
- Trigger: Both weekly cron schedule AND manual workflow_dispatch
- Schedule: Weekly (government data doesn't change hourly — good balance of freshness vs CI minutes)
- Failure handling: Continue pulling remaining jurisdictions if one fails; build site with whatever succeeded; flag failures in workflow summary/logs
- AI enrichment: Optional — skipped on scheduled runs, available as a boolean input on manual dispatch
- Pipeline steps: pull all jurisdictions → (optionally) enrich new datasets → build site with feeds/exports → deploy to GitHub Pages

### Claude's Discretion
- Jurisdiction filter placement and interaction with existing format/publisher/tag filters
- Badge visual design and color coding per jurisdiction
- Search index integration approach for jurisdiction field in Lunr.js
- CI caching strategy (pip cache, database, etc.)
- Exact cron day/time for weekly schedule
- GitHub Pages deployment method (peaceiris/actions-gh-pages vs built-in)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches for the UI elements (filter, badges, search). User focused discussion on CI pipeline behavior.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-site-ui-polish-ci-pipeline*
*Context gathered: 2026-02-27*
