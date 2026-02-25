# Requirements: Miami-Dade County Open Data Encyclopedia

**Defined:** 2026-02-24
**Core Value:** Every Miami-Dade open dataset is discoverable and understandable by a non-technical resident.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Data Ingestion

- [ ] **INGEST-01**: CLI can pull full catalog metadata from Socrata Discovery API with pagination (100 results/request)
- [ ] **INGEST-02**: CLI can pull full catalog metadata from ArcGIS Hub API (/api/v3/datasets)
- [ ] **INGEST-03**: CLI fetches column/field metadata per dataset from Socrata Views API (/api/views/{id}.json)
- [x] **INGEST-04**: All metadata stored in SQLite database with normalized schema (datasets, columns tables)
- [ ] **INGEST-05**: All API calls rate-limited to 1 request/second
- [ ] **INGEST-06**: Datasets appearing on both portals are detected and deduplicated

### AI Enrichment

- [ ] **ENRICH-01**: Claude API generates plain-English description for each dataset
- [ ] **ENRICH-02**: Claude API generates practical use cases ("why a resident or journalist would care")
- [ ] **ENRICH-03**: Claude API generates search keywords a resident would use
- [ ] **ENRICH-04**: Claude API infers likely owning department
- [ ] **ENRICH-05**: Claude API infers expected update frequency
- [ ] **ENRICH-06**: Claude API assigns civic relevance score (HIGH/MEDIUM/LOW)
- [ ] **ENRICH-07**: Enrichment supports `--dry-run` flag showing what would be enriched without calling API
- [ ] **ENRICH-08**: Enrichment supports `--resume` flag to continue from where it left off
- [ ] **ENRICH-09**: Enrichment shows cost estimate before running and prompts for confirmation
- [ ] **ENRICH-10**: Enrichments stored in separate SQLite table (survives metadata re-pulls)

### Quality & Audit

- [ ] **AUDIT-01**: CLI detects stale datasets (last updated exceeds expected frequency)
- [ ] **AUDIT-02**: CLI flags empty datasets (zero rows or missing data)
- [ ] **AUDIT-03**: CLI flags poorly described datasets (missing or very short descriptions)
- [ ] **AUDIT-04**: Each dataset gets a composite quality score (metadata completeness, freshness, column documentation)
- [ ] **AUDIT-05**: Audit results stored in SQLite audits table

### Change Detection

- [ ] **DIFF-01**: CLI compares current pull against previous pull state
- [ ] **DIFF-02**: Diff identifies newly added datasets
- [ ] **DIFF-03**: Diff identifies removed datasets
- [ ] **DIFF-04**: Diff identifies schema changes (column additions/removals)
- [ ] **DIFF-05**: Diff results stored in SQLite for site generation

### Static Site

- [ ] **SITE-01**: Full-text search via Lunr.js or Fuse.js with JSON index built at export time
- [ ] **SITE-02**: Category/theme browse pages with dataset listings
- [ ] **SITE-03**: Individual dataset pages showing metadata, AI enrichment, columns, quality score, source link
- [ ] **SITE-04**: Related datasets shown on each dataset page (tag/category overlap)
- [ ] **SITE-05**: Freshness indicators on dataset listings and detail pages
- [ ] **SITE-06**: Filtering by format, publisher, and tag on browse pages
- [ ] **SITE-07**: "What Changed" page showing diff results between pulls
- [ ] **SITE-08**: Data quality report page with aggregate stats (% described, stale count, etc.)
- [ ] **SITE-09**: About/disclaimer page with methodology
- [ ] **SITE-10**: Footer on every page: "Not an official Miami-Dade County product. Built by Abreu Data Works LLC."
- [ ] **SITE-11**: MDC blue (#003366), white, amber color scheme
- [ ] **SITE-12**: Responsive layout that works on mobile
- [ ] **SITE-13**: Pure static files — works without a server

### CLI & Packaging

- [x] **CLI-01**: Installable via `pip install .` with pyproject.toml and Hatchling backend
- [ ] **CLI-02**: Entry point `mdc-encyclopedia` available after install
- [ ] **CLI-03**: `pull` command fetches metadata from both portals
- [ ] **CLI-04**: `stats` command shows database summary (dataset counts, enrichment status, quality overview)
- [ ] **CLI-05**: `enrich` command runs AI enrichment pipeline
- [ ] **CLI-06**: `audit` command runs quality audit
- [ ] **CLI-07**: `diff` command shows changes between pulls
- [ ] **CLI-08**: `export` command generates static site in site/ directory
- [ ] **CLI-09**: `serve` command starts local preview server for the static site
- [ ] **CLI-10**: Rich terminal output for all commands (progress bars, tables, colored status)

### Deployment

- [ ] **DEPLOY-01**: Static site deploys to GitHub Pages
- [ ] **DEPLOY-02**: GitHub Actions workflow runs weekly (pull + auto-enrich new + audit + export + deploy)
- [ ] **DEPLOY-03**: ANTHROPIC_API_KEY handled as GitHub Secret (optional — workflow runs without it, skipping enrichment)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Notifications

- **NOTF-01**: RSS feed for catalog changes
- **NOTF-02**: Email alerts for new datasets in specific categories

### Export

- **EXPORT-01**: Downloadable catalog as JSON/CSV for developers
- **EXPORT-02**: Embeddable dataset card widgets for other civic sites

### Multi-Jurisdiction

- **MULTI-01**: Support additional South Florida jurisdictions (Broward, City of Miami)
- **MULTI-02**: Config-driven portal list for easy expansion

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Data preview (showing actual rows) | Extra API calls per dataset, breaks catalog boundary, source portal already provides this |
| Built-in data visualization | Massive scope expansion, maintenance nightmare as schemas change |
| User accounts / saved searches | Requires auth infrastructure, antithetical to static site |
| Hosted API for programmatic access | Requires running a server, conflicts with GitHub Pages architecture |
| User-submitted dataset requests | Requires moderation, creates unfulfillable expectations |
| Real-time data freshness checking | Requires runtime API calls from browser, CORS issues |
| Email/Slack notifications | Requires notification infrastructure and user accounts |
| Comments/discussion on datasets | Requires moderation, backend, user accounts |
| Mobile app | Responsive static site is sufficient |
| OAuth login | No auth needed for a static catalog |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INGEST-01 | Phase 2 | Pending |
| INGEST-02 | Phase 2 | Pending |
| INGEST-03 | Phase 2 | Pending |
| INGEST-04 | Phase 1 | Complete |
| INGEST-05 | Phase 2 | Pending |
| INGEST-06 | Phase 2 | Pending |
| ENRICH-01 | Phase 3 | Pending |
| ENRICH-02 | Phase 3 | Pending |
| ENRICH-03 | Phase 3 | Pending |
| ENRICH-04 | Phase 3 | Pending |
| ENRICH-05 | Phase 3 | Pending |
| ENRICH-06 | Phase 3 | Pending |
| ENRICH-07 | Phase 3 | Pending |
| ENRICH-08 | Phase 3 | Pending |
| ENRICH-09 | Phase 3 | Pending |
| ENRICH-10 | Phase 3 | Pending |
| AUDIT-01 | Phase 4 | Pending |
| AUDIT-02 | Phase 4 | Pending |
| AUDIT-03 | Phase 4 | Pending |
| AUDIT-04 | Phase 4 | Pending |
| AUDIT-05 | Phase 4 | Pending |
| DIFF-01 | Phase 5 | Pending |
| DIFF-02 | Phase 5 | Pending |
| DIFF-03 | Phase 5 | Pending |
| DIFF-04 | Phase 5 | Pending |
| DIFF-05 | Phase 5 | Pending |
| SITE-01 | Phase 6 | Pending |
| SITE-02 | Phase 6 | Pending |
| SITE-03 | Phase 6 | Pending |
| SITE-04 | Phase 6 | Pending |
| SITE-05 | Phase 6 | Pending |
| SITE-06 | Phase 6 | Pending |
| SITE-07 | Phase 6 | Pending |
| SITE-08 | Phase 6 | Pending |
| SITE-09 | Phase 6 | Pending |
| SITE-10 | Phase 6 | Pending |
| SITE-11 | Phase 6 | Pending |
| SITE-12 | Phase 6 | Pending |
| SITE-13 | Phase 6 | Pending |
| CLI-01 | Phase 1 | Complete |
| CLI-02 | Phase 1 | Pending |
| CLI-03 | Phase 2 | Pending |
| CLI-04 | Phase 4 | Pending |
| CLI-05 | Phase 3 | Pending |
| CLI-06 | Phase 4 | Pending |
| CLI-07 | Phase 5 | Pending |
| CLI-08 | Phase 6 | Pending |
| CLI-09 | Phase 6 | Pending |
| CLI-10 | Phase 1 | Pending |
| DEPLOY-01 | Phase 7 | Pending |
| DEPLOY-02 | Phase 7 | Pending |
| DEPLOY-03 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 52 total
- Mapped to phases: 52
- Unmapped: 0

---
*Requirements defined: 2026-02-24*
*Last updated: 2026-02-24 after roadmap creation*
