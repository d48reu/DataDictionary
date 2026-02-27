# Requirements: Miami-Dade County Open Data Encyclopedia

**Defined:** 2026-02-26
**Core Value:** Every Miami-Dade open dataset is discoverable and understandable by a non-technical resident.

## v1.1 Requirements

Requirements for milestone v1.1 Regional Expansion. Each maps to roadmap phases.

### Multi-Jurisdiction

- [ ] **MULTI-01**: Jurisdiction registry mapping slugs to portal base URLs and display names
- [ ] **MULTI-02**: Hub client parameterized to accept base URL for any ArcGIS Hub portal
- [ ] **MULTI-03**: Schema V3 migration — synthetic composite key, ai_description column, source_portal index, existing data migration
- [ ] **MULTI-04**: CLI `pull --jurisdiction` flag to pull from specific jurisdiction(s)
- [ ] **MULTI-05**: Jurisdiction filter dropdown on browse page
- [ ] **MULTI-06**: Jurisdiction badge on dataset cards and detail pages
- [ ] **MULTI-07**: Jurisdiction field in Lunr.js search index
- [ ] **MULTI-08**: Updated CI pipeline with multi-jurisdiction pull

### Atom Feed

- [ ] **FEED-01**: Atom 1.0 feed generated during site build with recent catalog changes (new, removed, schema changes)
- [ ] **FEED-02**: Feed autodiscovery `<link>` in HTML `<head>`
- [ ] **FEED-03**: `--site-url` parameter on export command for absolute URLs in feed entries

### Catalog Export

- [ ] **EXPORT-01**: Downloadable enriched catalog as JSON with DCAT-US v1.1 field alignment and jurisdiction field
- [ ] **EXPORT-02**: Downloadable enriched catalog as CSV with UTF-8 BOM for Excel
- [ ] **EXPORT-03**: Download links on About page with format and file size

### Field AI

- [ ] **FIELD-01**: AI-generated plain-English descriptions for all columns in B+ quality datasets
- [ ] **FIELD-02**: `enrich-fields` CLI command with `--dry-run`, `--limit`, and `--resume` flags
- [ ] **FIELD-03**: Field descriptions displayed inline in dataset detail page columns table with AI badge
- [ ] **FIELD-04**: Batch all columns per dataset in single API call (not per-column)

## v1.2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Multi-Jurisdiction

- **MULTI-09**: Per-jurisdiction diff snapshots for targeted change detection
- **MULTI-10**: City of Miami Socrata portal integration (`data.miamigov.com`)

### Feed

- **FEED-04**: RSS 2.0 dual format output alongside Atom
- **FEED-05**: Feed validation in CI via xmllint
- **FEED-06**: Per-jurisdiction Atom feeds

### Field AI

- **FIELD-05**: Column enrichment for sub-B datasets (expand threshold after v1.1 prompt validation)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time feed updates (WebSub/PubSubHubbub) | Static site architecture precludes push; weekly cadence makes this irrelevant |
| DCAT-US v3.0 compliance | Draft spec, not yet required; use v1.1 field names and migrate when finalized |
| Jurisdiction-specific enrichment prompts | Single template with `{jurisdiction}` variable is sufficient |
| Data preview (showing actual rows) | Extra API cost, source portal already provides this |
| Real-time data | This is a catalog, not a data warehouse |
| OAuth or user accounts | Pure static site, no auth needed |
| Hosted API for programmatic access | Conflicts with static site architecture; catalog export addresses developer needs |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MULTI-01 | — | Pending |
| MULTI-02 | — | Pending |
| MULTI-03 | — | Pending |
| MULTI-04 | — | Pending |
| MULTI-05 | — | Pending |
| MULTI-06 | — | Pending |
| MULTI-07 | — | Pending |
| MULTI-08 | — | Pending |
| FEED-01 | — | Pending |
| FEED-02 | — | Pending |
| FEED-03 | — | Pending |
| EXPORT-01 | — | Pending |
| EXPORT-02 | — | Pending |
| EXPORT-03 | — | Pending |
| FIELD-01 | — | Pending |
| FIELD-02 | — | Pending |
| FIELD-03 | — | Pending |
| FIELD-04 | — | Pending |

**Coverage:**
- v1.1 requirements: 17 total
- Mapped to phases: 0
- Unmapped: 17

---
*Requirements defined: 2026-02-26*
*Last updated: 2026-02-26 after initial definition*
