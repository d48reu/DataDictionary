# Project Research Summary

**Project:** Miami-Dade County Open Data Encyclopedia
**Domain:** Open data catalog with AI enrichment (Python CLI + static site generator)
**Researched:** 2026-02-24
**Confidence:** HIGH

## Executive Summary

The Miami-Dade County Open Data Encyclopedia is a civic tech tool that catalogs, enriches, and publishes all datasets from Miami-Dade's two open data portals (Socrata and ArcGIS Hub) as a fully static, GitHub Pages-hosted website. Experts in this space build such tools using a pipeline-of-commands ETL architecture: a CLI tool ingests raw metadata into SQLite, enriches it with AI, runs quality audits, and exports a static site. This is an established pattern (see JKAN, Datasette's "baked data" philosophy, Simon Willison's sqlite-utils ecosystem) with well-documented tooling choices. The recommended stack — Click + sqlite-utils + Anthropic SDK + Jinja2 + Lunr.js — is purpose-built for exactly this use case, with no unnecessary dependencies.

The core value proposition is AI enrichment: converting cryptic government metadata into plain-English descriptions, use cases, and resident-focused keywords that no existing portal offers. The primary differentiators over existing portals are AI-generated descriptions, automated data quality scoring, a public "What Changed" diff page, and a unified cross-portal view spanning both Socrata and ArcGIS Hub. All table-stakes catalog features (search, browse by category, dataset detail pages, metadata display, source links, column info) are deliverable within the static-site constraint using client-side Lunr.js search with a pre-built JSON index.

The key risks are concentrated in two phases: data ingestion (Socrata's API has three independent pagination/completeness pitfalls and an in-progress SODA3 migration) and AI enrichment (cost blowout without dry-run controls, and prompt drift invalidating existing enrichments). Both are preventable with upfront architecture decisions — a thin SocrataClient abstraction, pagination assertions against resultSetSize, and an enrichment status table with prompt versioning. Build order is dictated by the dependency chain: storage schema must precede API clients, which must precede enrichment, which must precede static site export.

## Key Findings

### Recommended Stack

The stack is a tight, coherent Python ecosystem with no extraneous dependencies. Click provides the CLI framework (same ecosystem as sqlite-utils, Pallets foundation). sqlite-utils handles all SQLite operations with automatic schema inference, FTS5 support, and upsert — eliminating hundreds of lines of boilerplate. The Anthropic SDK's Message Batches API is critical for bulk enrichment at 50% cost reduction. Jinja2 handles templating with inheritance for layout/page hierarchy. lunr.py generates a compatible search index at build time in pure Python, avoiding a Node.js build dependency.

**Core technologies:**
- **Python 3.12+**: Runtime — stable through 2028, best library compat
- **Click 8.3.1**: CLI framework — decorator-based, same ecosystem as sqlite-utils, handles all subcommands cleanly
- **sqlite-utils 3.39**: Database layer — Pythonic SQLite with FTS5, upsert, schema inference; purpose-built for this pattern
- **Jinja2 3.1.6**: HTML templating — template inheritance for layout, battle-tested for static site generation
- **Anthropic SDK >=0.83.0**: AI enrichment — Message Batches API for bulk runs at 50% cost discount
- **httpx 0.28.1**: HTTP client — sync/async parity, connection pooling; use sync mode for rate-limited sequential API calls
- **Rich 14.3.3**: Terminal output — progress bars, formatted tables, colored audit results
- **lunr.py 0.8.0 + Lunr.js 2.3.9**: Search — Python builds index at export time, browser loads pre-built JSON; no Node.js needed

**Do not use:** sodapy (Consumer API only, not Discovery API), SQLAlchemy (overkill), Flask/FastAPI (no server needed), Node.js build pipeline (lunr.py replaces it), Pandas (sqlite-utils + stdlib is sufficient).

### Expected Features

The feature research confirms the MVP is well-scoped. AI enrichment is not a nice-to-have — it IS the product. Without it, this is a worse version of the existing portals. The unified cross-portal view (Socrata + ArcGIS Hub) is the second major differentiator; no existing Miami-Dade tool does this.

**Must have (table stakes):**
- Full-text search — primary discovery mechanism; every catalog leads with it
- Browse by category/theme — users narrow by topic, cannot browse hundreds of datasets manually
- Individual dataset detail pages — atomic unit of a catalog; quality of these pages is where value lives
- Dataset metadata display (title, description, publisher, format, last updated, tags)
- Source portal deep links — broken links destroy trust; catalog is not a data host
- Column/field information — critical for developers and journalists pre-download
- Responsive/mobile layout — static site on GitHub Pages must work on phones
- Filtering by format/publisher/tag — search alone insufficient for large catalogs
- Freshness indicator — stale data without warning erodes trust
- About/methodology/disclaimer page — transparency required for civic tech

**Should have (differentiators):**
- AI plain-English descriptions — #1 differentiator; no existing portal does this well
- AI use cases ("Why you'd care") — transforms reference tool into actionable guide
- Search keyword enrichment — maps government jargon to plain language residents actually search
- Automated data quality scoring — pioneered by Toronto; makes catalog an accountability tool
- Cross-portal unified view — Socrata + ArcGIS Hub as single searchable catalog
- Diff detection + "What Changed" page — public changelog no portal currently offers
- Department attribution browsing — AI-inferred; no Miami-Dade portal offers this today
- Civic relevance scoring — enables "Most Relevant to Residents" browsing
- Data quality report page — aggregate accountability dashboard

**Defer (v2+):**
- RSS feed for changes — low-effort alerting, add after "What Changed" is validated
- Downloadable catalog JSON/CSV — for developers wanting bulk access
- Embeddable widgets — let other civic sites embed dataset cards
- Multi-jurisdiction support — only after Miami-Dade is solid and there is demand

**Anti-features to avoid:** data preview (build time blowout, goes stale), built-in visualization (scope explosion), user accounts (antithetical to static site), runtime API (requires server), real-time freshness checking (requires runtime calls from browser).

### Architecture Approach

The architecture is a pipeline-of-commands ETL system where each CLI command (pull, enrich, audit, diff, export) represents one independent but sequenced stage, with SQLite as the shared state between all stages. Socrata and ArcGIS clients normalize heterogeneous API responses into a common DatasetRecord schema before storage — downstream code (enrichment, audit, export) never knows which portal a dataset came from. Enrichments are stored in a separate table (not inline with datasets) so that pull can freely upsert without overwriting AI-generated content. The static site is "baked" from SQLite at export time: Jinja2 renders HTML pages and lunr.py builds the pre-serialized search JSON.

**Major components:**
1. **CLI Layer (Click)** — user-facing commands, argument parsing, progress display via Rich; wires all other components together
2. **API Clients (socrata.py + arcgis.py)** — each normalizes source-specific JSON into DatasetRecord dataclasses; Socrata requires N+1 calls (Discovery API + per-dataset /api/views/{id}.json)
3. **Storage Layer (sqlite-utils)** — single SQLite file with datasets, columns, enrichments, audit_scores, changes tables; every component reads/writes through db.py
4. **Enrichment Engine (Anthropic SDK)** — reads unenriched datasets from DB, submits Batch API requests, writes structured results back; tracks status per-dataset with prompt versioning
5. **Audit Engine** — pure Python logic computing staleness, completeness, quality scores from SQLite data
6. **Diff Engine** — SQL comparisons against versioned snapshots to detect new/removed/changed datasets
7. **Site Builder (Jinja2 + lunr.py)** — reads all tables via SQL joins, renders HTML pages, builds search JSON index, copies static assets to output directory

**Key pattern:** Normalize-at-ingestion. Separate enrichment table. Pipeline-of-commands with SQLite as shared state. Baked data output to docs/ or _site/ for GitHub Pages.

### Critical Pitfalls

1. **Socrata Discovery API returns fewer datasets than exist** — The API defaults to `dataset` type only, silently filtering charts, maps, filtered views. Assert fetched count matches `resultSetSize`; compare against portal browse count on first pull. Decide explicitly which asset types to include and document in config. Affects Phase 1.

2. **Pagination off-by-one and silent truncation** — Discovery API uses plain `limit`/`offset` (no dollar signs). Off-by-one returns suspiciously round numbers. Use `resultSetSize` from first response as the expected total; assert total fetched matches after pagination completes. Affects Phase 1.

3. **AI enrichment cost blowout** — Testing with 10 datasets then running 800 without cost controls can generate unexpected $10-25+ bills. Implement `--dry-run` and `--cost-estimate` before any enrichment runs. Store enrichment status per-dataset in SQLite with `--resume` support. Add `--max-cost` hard cap. Affects Phase 2.

4. **Enrichment prompt drift invalidating existing enrichments** — Improving the prompt after a full run creates inconsistent quality across the catalog. Store `prompt_version` and `prompt_hash` with every enrichment record. Freeze the prompt before the first full-catalog run; iterate on 10-20 datasets first. Add `--upgrade-from-version` CLI command for targeted re-enrichment. Affects Phase 2.

5. **Client-side search index too large for browser** — AI descriptions, column names, and use cases indexed naively can produce 2-5MB+ JSON. Index only title, AI keywords, department, and category — not full descriptions. Pre-build at export time via lunr.py. Target under 500KB. Measure after first full export. Affects Phase 4.

6. **SODA3 migration breaking Socrata integration** — Socrata defaulted to SODA3 in October 2025; SODA3 requires app tokens and changed endpoint patterns. Register a Socrata app token immediately. Isolate all Socrata calls behind a SocrataClient abstraction so endpoint changes require updating one module. Affects Phase 1.

7. **ArcGIS Hub API v3 undocumented instability** — Minimal official docs; best reference is a 2019 unofficial gist. Use site-specific endpoint (`gis-mdc.opendata.arcgis.com/api/v3/datasets`). Cache raw API responses to disk before parsing. Implement response validation; fail loudly on missing fields. Affects Phase 1.

## Implications for Roadmap

Based on combined research, the architecture's build order dictates the roadmap phase structure. The dependency chain is strict: storage before clients before pull before enrichment before export. Each phase can be tested in isolation.

### Phase 1: Foundation — Storage Schema + Project Skeleton
**Rationale:** Every other component depends on the storage schema. Get this wrong and everything breaks on top of it. Architecture research explicitly puts this first. SQLite schema decisions (separate enrichments table, prompt_version column, migration version table) are harder to change later.
**Delivers:** Working Python package with pyproject.toml, cli.py skeleton, storage/db.py with full schema (datasets, columns, enrichments, audit_scores, changes tables), DatasetRecord and ColumnRecord dataclasses, database initialization logic.
**Addresses:** Foundation for all table-stakes features (metadata storage, column info, enrichment status)
**Avoids:** Pitfall: "No migration strategy for SQLite schema" — schema version table from day one. Pitfall: "Storing enrichments inline with dataset metadata" — separate enrichments table from day one.

### Phase 2: Data Ingestion — Socrata + ArcGIS Pull
**Rationale:** Real data is required to test everything downstream. Cannot validate enrichment, audit, or export without actual catalog data. Architecture says clients come immediately after storage models.
**Delivers:** SocrataClient (Discovery API pagination + per-dataset /api/views/{id}.json column metadata), ArcGISClient (Hub API v3 with site-specific filter), `mdc-encyclopedia pull` command, pagination with resultSetSize assertion, upsert into SQLite.
**Uses:** httpx (sync mode, 1 req/sec rate limiting), Rich progress bars, python-slugify for IDs
**Implements:** API Clients architecture component + Pull CLI command
**Avoids:** Pitfall: "Discovery API returns fewer datasets than exist" — explicit asset type config, resultSetSize assertion. Pitfall: "Pagination off-by-one" — plain limit/offset, assertion against total. Pitfall: "SODA3 migration" — SocrataClient abstraction, app token from day one. Pitfall: "ArcGIS Hub instability" — response validation, raw response caching.
**Research flag:** This phase needs deeper research. Socrata's SODA3 migration status for Miami-Dade specifically is uncertain. ArcGIS Hub API v3 docs are unofficial. Plan for discovery time.

### Phase 3: AI Enrichment Engine
**Rationale:** Enrichment is the product's #1 value proposition. Must come before export so the site has enriched content. Must come after pull so there is real data to enrich. Audit/diff are cheaper (no API cost) but enrichment needs to work before export can demonstrate full value.
**Delivers:** Enrichment engine with `--dry-run`, `--cost-estimate`, `--resume`, `--max-cost`, `--new-only` flags; Anthropic Batch API integration; prompt templates with structured JSON output; `prompt_version` and `prompt_hash` storage; token usage audit table; `mdc-encyclopedia enrich` command.
**Uses:** Anthropic SDK (Message Batches API for 50% cost reduction), claude-sonnet-4-5 (not Opus — sufficient quality at 10x lower cost)
**Implements:** Enrichment Engine architecture component
**Avoids:** Pitfall: "AI enrichment cost blowout" — dry-run and cost estimate required before any full run. Pitfall: "Enrichment prompt drift" — prompt versioning schema from the start. Freeze prompt on 10-20 test datasets before full-catalog run.

### Phase 4: Audit + Quality Scoring
**Rationale:** Pure Python logic with no external API calls — fast to iterate and test. Produces quality scores that can enhance enrichment prompts and are displayed on dataset pages. Architecture research specifically recommends audit before export because export consumes audit results.
**Delivers:** Audit engine computing staleness (last updated vs declared frequency), metadata completeness (% fields filled), column documentation coverage; quality score per dataset written to audit_scores table; `mdc-encyclopedia audit` command.
**Implements:** Audit Engine architecture component
**Avoids:** No major pitfalls here — pure Python logic, no external dependencies.

### Phase 5: Diff Detection
**Rationale:** Requires at least one prior pull to establish baseline. Cannot implement until data has been pulled once and stored. A short, focused phase that adds significant accountability value.
**Delivers:** Snapshot comparison detecting new/removed datasets and schema changes; changes table populated in SQLite; `mdc-encyclopedia diff` command. Output consumed by the "What Changed" page in export.
**Implements:** Diff Engine architecture component
**Avoids:** Note that first run has no diff — this is expected behavior, not a bug.

### Phase 6: Static Site Export + Search
**Rationale:** Consumes outputs from all upstream phases (pull, enrichment, audit, diff). This is the final deliverable visible to users. Architecture research explicitly places this last. Search index sizing must be tested with realistic catalog data, not a handful of test datasets.
**Delivers:** Jinja2 templates (base, index, dataset, category, changes, quality pages); lunr.py search index builder; `mdc-encyclopedia export` command; `mdc-encyclopedia serve` for local preview; responsive CSS with MDC branding (#003366, white, amber); client-side search.js with lazy loading.
**Uses:** Jinja2 (template inheritance), lunr.py (pre-built index), python-slugify (clean URLs), Vanilla JS + CSS
**Implements:** Site Builder architecture component + Static Output layer
**Avoids:** Pitfall: "Search index too large" — index only title + keywords + department + category, measure under 500KB after first full export. Pitfall: "Enrichment output not escaped" — always use `| e` filter, never `| safe` on AI content. Pitfall: "Showing raw API field names" — map all fields to plain-English labels.

### Phase 7: CI/CD — GitHub Actions Weekly Refresh
**Rationale:** Orchestrates all commands that must already exist and be working. This is the deployment automation, not the product itself. Architecture research explicitly puts CI/CD last.
**Delivers:** `.github/workflows/weekly-refresh.yml` cron job running pull -> audit -> diff -> optional enrich -> export -> deploy to GitHub Pages; `timeout-minutes: 30` set explicitly; graceful handling of missing `ANTHROPIC_API_KEY`; GitHub Secrets configuration.
**Implements:** CI/CD flow from architecture data flow section
**Avoids:** Pitfall: "GitHub Actions default timeout" — set explicit 30-minute timeout. Pitfall: "API key in repository" — GitHub Secrets only, never CLI arguments.

### Phase Ordering Rationale

- **Storage first** because the schema is the contract that all other components depend on. Changing the schema after clients or enrichment are built requires cascading fixes.
- **Pull before everything else** because you need real data to validate all downstream components. Testing enrichment with mock data masks real API response shapes.
- **Enrichment before export** because the site without AI descriptions is not meaningfully better than the existing portals. The export is the packaging of the enrichment, not a standalone deliverable.
- **Audit before export** because audit scores appear on dataset pages. Pure Python, no API cost — there is no reason to delay it.
- **Diff before export** because "What Changed" page is an export template that needs the changes table populated.
- **Export before CI/CD** because CI orchestrates commands that must already be debugged locally.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Data Ingestion):** The Socrata SODA3 migration status for Miami-Dade specifically is uncertain (official docs say "October 2025 default" but real-world rollout may vary). ArcGIS Hub API v3 documentation is an unofficial 2019 gist — field names and pagination may have changed. Recommend a discovery spike: make 3-5 live API calls to both portals before writing client code, document actual response shapes.
- **Phase 3 (AI Enrichment):** The optimal enrichment prompt structure (balancing output quality, token count, and structured JSON reliability) requires iteration. Recommend a prompt development sprint with 15-20 real Miami-Dade datasets before finalizing the prompt schema.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Storage Schema):** sqlite-utils is extremely well-documented via Context7. Schema design follows established patterns (separate tables, FK constraints, version tracking). No novel decisions.
- **Phase 4 (Audit Engine):** Pure Python logic. Quality scoring algorithms (staleness, completeness) are straightforward to implement. Toronto's Open Data quality score methodology is publicly documented.
- **Phase 5 (Diff Detection):** Standard SQL snapshot comparison. SQLite makes this trivial with the schema already in place.
- **Phase 6 (Static Site Export):** Jinja2 template inheritance is well-documented. Lunr.js pre-built index pattern is documented. Main risk (index size) is mitigated by measuring after first full export.
- **Phase 7 (CI/CD):** GitHub Actions + GitHub Pages deployment is a mature, well-documented pattern. No novel decisions.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies verified via Context7, PyPI, and official docs. No cross-package conflicts. lunr.py/Lunr.js version compatibility flagged as MEDIUM — verify index format compatibility before full export. |
| Features | HIGH | Grounded in analysis of CKAN, Socrata, Magda, OpenDataSoft, Toronto quality score, academic usability research. Feature prioritization is well-reasoned and consistent with comparable civic tech tools. |
| Architecture | HIGH | Pipeline-of-commands + baked data pattern is battle-tested (Datasette, JKAN). Component boundaries are clear and consistent across all research sources. Build order is unambiguous. |
| Pitfalls | HIGH | Most critical pitfalls verified against official Socrata/GitHub/Anthropic docs. ArcGIS Hub pitfall has LOW-confidence source (2019 unofficial gist) but is corroborated by the API's known poor documentation. |

**Overall confidence:** HIGH

### Gaps to Address

- **Socrata SODA3 rollout status for Miami-Dade specifically:** The SODA3 migration is documented as an October 2025 platform default, but individual domain rollout timelines vary. Before writing the SocrataClient, make 3-5 live authenticated and unauthenticated requests to `opendata.miamidade.gov/api/catalog/v1` to determine current endpoint behavior.

- **ArcGIS Hub API v3 current field schema for Miami-Dade:** The best available reference is a 2019 gist. Make live requests to `gis-mdc.opendata.arcgis.com/api/v3/datasets?page[size]=5` and document the actual response shape before building arcgis.py. The fields array, pagination metadata, and total count location may differ from 2019 documentation.

- **lunr.py / Lunr.js index format compatibility:** lunr.py 0.8.0 claims to produce Lunr.js-compatible indexes, but this should be verified by building a test index with lunr.py and loading it with `lunr.Index.load()` in the browser before committing to this approach. If incompatible, the fallback is Fuse.js (raw JSON, no pre-build step needed).

- **Miami-Dade catalog size:** The actual number of datasets on both portals is not quantified in the research. This directly affects enrichment cost estimates and search index sizing decisions. A quick initial pull (without column metadata) should be run early in Phase 2 to establish the catalog size before making cost commitments.

- **Enrichment prompt structure and output quality:** The prompt design (what fields to request, JSON schema for structured output, system prompt content) requires iteration on real Miami-Dade datasets. Budgeting 1-2 hours of prompt iteration with 15-20 test datasets before the first full-catalog run is recommended.

## Sources

### Primary (HIGH confidence)
- `/simonw/sqlite-utils` (Context7) — FTS5 API, insert_all, enable_fts, transform for schema migration
- `/pallets/click` (Context7) — Group/command pattern, options/arguments, decorator model
- `/anthropics/anthropic-sdk-python` (Context7) — Message Batches API, retry behavior, RateLimitError handling
- [PyPI: sqlite-utils 3.39](https://pypi.org/project/sqlite-utils/) — Current version, Python compat
- [PyPI: anthropic 0.83.0](https://pypi.org/project/anthropic/) — Current version, API surface
- [PyPI: click 8.3.1](https://pypi.org/project/click/) — Current version
- [SODA3 migration announcement](https://support.socrata.com/hc/en-us/articles/34730618169623-SODA3-API) — Endpoint changes, token requirements
- [SODA3 October 2025 release](https://support.socrata.com/hc/en-us/articles/35710697739799-October-2025-Product-Release) — Deployment timeline
- [Anthropic batch processing docs](https://docs.claude.com/en/docs/build-with-claude/batch-processing) — Batch API usage, 50% cost reduction
- [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits) — 1GB site limit
- [GitHub Actions limits](https://docs.github.com/en/actions/reference/limits) — Default 6-hour timeout
- [Lunr.js pre-building guide](https://lunrjs.com/guides/index_prebuilding.html) — Index serialization pattern
- [JKAN static data portal](https://github.com/timwis/jkan) — Static site data catalog proof-of-concept
- [Datasette architecture (Architecture Notes)](https://architecturenotes.co/p/datasette-simon-willison) — Baked data pattern

### Secondary (MEDIUM confidence)
- [Socrata Discovery API docs](https://dev.socrata.com/docs/other/discovery) — Catalog endpoint, pagination (docs lag API)
- [PyPI: lunr 0.8.0](https://pypi.org/project/lunr/) — Python Lunr port, version currency
- [Socrata dataset count mismatch (SO)](https://stackoverflow.com/questions/58130323) — asset type filtering issue independently reproduced
- [Lunr.js performance limits](https://www.previousnext.com.au/blog/fast-and-fuzzy-client-side-search-lunrjs-and-drupal) — Practical testing at scale
- [Fuse.js large dataset issues (SO)](https://stackoverflow.com/questions/70984437/fuse-js-takes-10-seconds-with-semi-long-queries) — 10-second query time on large datasets
- [Toronto data quality score](https://medium.com/open-data-toronto/towards-a-data-quality-score-in-open-data-part-1-525e59f729e9) — Quality scoring methodology
- [SODA3 token requirements](https://munozbravo.github.io/dotgov/guides/versions/) — Third-party detailed guide
- Academic portal usability research — Feature expectations from user studies

### Tertiary (LOW confidence)
- [ArcGIS Hub API v3 reference (unofficial gist)](https://gist.github.com/jgravois/1b7ec5080e992a59f65cf7a2190e4365) — 2019, best available; validate against live API before building client
- [ArcGIS Hub API v3 gist (haoliangyu)](https://gist.github.com/haoliangyu/0d0abcccfd3b25beb8b7597b4b2fc497) — Pagination, metadata fields; unofficial
- [Python build backends 2025](https://medium.com/@dynamicy/python-build-backends-in-2025-what-to-use-and-why-uv-build-vs-hatchling-vs-poetry-core-94dd6b92248f) — Hatchling recommendation; blog post

---
*Research completed: 2026-02-24*
*Ready for roadmap: yes*
