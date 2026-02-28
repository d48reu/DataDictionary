# Milestones

## v1.0 MVP (Shipped: 2026-02-26)

**Delivered:** A complete CLI tool and static encyclopedia for Miami-Dade County's open data catalog — ingestion, AI enrichment, quality audit, change detection, static site, and automated deployment.

**Stats:**
- Phases: 1-7 (18 plans)
- Files modified: 91
- Lines of code: 5,573 (3,416 Python + 705 HTML + 1,150 CSS + 302 JS)
- Timeline: 2 days (Feb 24 → Feb 26, 2026)
- Git range: `feat(01-01)` → `feat(07-01)`
- Requirements: 52/52 satisfied

**Key accomplishments:**
1. Full catalog ingestion from Miami-Dade ArcGIS Hub with field metadata, dedup, and rate limiting
2. Claude AI enrichment generating plain-English descriptions, use cases, keywords, and civic relevance
3. Three-dimension quality audit with freshness/completeness/documentation scoring and letter grades
4. Change detection between pulls tracking new, removed, and schema-changed datasets
5. Searchable static HTML encyclopedia with Lunr.js search, category browsing, quality reports, and responsive MDC-branded design
6. GitHub Actions weekly pipeline with automated pull/audit/diff/enrich/export/deploy to GitHub Pages

### Known Tech Debt
- 1 cosmetic bug: browse.html uses `grade_class` instead of `grade_css` (one-line fix)
- 1 edge case: push-trigger deploys empty site before first cron run populates DB (self-resolving)
- 15 human verification items across all phases (live API, terminal rendering, browser testing, GitHub infra)

**Archives:** `milestones/v1.0-ROADMAP.md`, `milestones/v1.0-REQUIREMENTS.md`, `milestones/v1.0-MILESTONE-AUDIT.md`

---


## v1.1 Regional Expansion (Shipped: 2026-02-28)

**Delivered:** Multi-jurisdiction coverage (Broward County, City of Miami), subscribable Atom change feeds, developer-friendly catalog exports (JSON + CSV), AI-generated column descriptions, and full UI/CI integration.

**Stats:**
- Phases: 8-13 (9 plans)
- Files modified: 22 (source code)
- Lines changed: +1,748 / -184
- Lines of code: 7,298 (Python 4,861 + HTML/CSS/JS 2,260 + YAML 177)
- Timeline: 3 days (Feb 24 → Feb 27, 2026)
- Git range: `feat(08-01)` → `feat(13-01)`
- Requirements: 18/18 satisfied

**Key accomplishments:**
1. Multi-jurisdiction foundation with jurisdiction registry, Schema V3 migration, synthetic composite keys, and parameterized hub client for Miami-Dade, Broward, and City of Miami
2. Atom 1.0 change feed with autodiscovery and absolute URLs for subscribing to catalog changes
3. DCAT-US aligned JSON and Excel-compatible CSV catalog exports with About page download links
4. AI field-level column descriptions for B+ datasets with structured API output, chunking, and AI badge rendering
5. Jurisdiction filter dropdown, colored badges, Lunr search integration, and multi-jurisdiction CI pipeline
6. Tech debt closure — jurisdiction wiring through enrich command and ai_description preservation in column upserts

### Known Tech Debt
- SUMMARY.md frontmatter does not include `requirements-completed` field (INFO level, non-blocking)
- browse.html grade CSS class mismatch carried from v1.0 (cosmetic, one-line fix)

**Archives:** `milestones/v1.1-ROADMAP.md`, `milestones/v1.1-REQUIREMENTS.md`, `milestones/v1.1-MILESTONE-AUDIT.md`

---

