# Project Research Summary

**Project:** Miami-Dade County Open Data Encyclopedia v1.1 — Regional Expansion
**Domain:** Open data catalog / encyclopedia — additive feature milestone
**Researched:** 2026-02-26
**Confidence:** HIGH

## Executive Summary

The v1.1 milestone extends the proven v1.0 architecture in four well-scoped directions: RSS/Atom feed generation for catalog changes, downloadable enriched catalog export (JSON + CSV), AI field-level column descriptions, and multi-jurisdiction support for Broward County and City of Miami. All four features build on the existing Python/SQLite/Anthropic stack. The research confirms zero new pip dependencies are required with the sole exception of `feedgen` — recommended despite the STACK.md finding against it because the RFC 822 date format pitfall for RSS 2.0 is a real correctness risk that feedgen resolves internally. Every other feature uses stdlib (`xml.etree.ElementTree`, `csv`, `json`, `datetime`) and existing dependencies. The v1.0 architecture's modular separation — ingestion, enrichment, audit, diff, site — creates natural insertion points for all four features with no rewrites required.

The recommended implementation order is: (1) multi-jurisdiction foundation, (2) RSS/Atom feed, (3) enriched catalog export, (4) AI field-level descriptions, (5) site UI polish and CI pipeline. Multi-jurisdiction must precede the other features because the RSS feed and catalog export should include jurisdiction metadata from day one — building them first and retrofitting later wastes effort. Multi-jurisdiction is also the most cross-cutting change, touching ingestion, normalization, DB schema, diff detection, site generation, and templates. However, the individual changes per file are modest parameterizations of currently hardcoded values (primarily converting `HUB_BASE_URL = "https://opendata.miamidade.gov"` into a configurable parameter). All three ArcGIS Hub portals (Miami-Dade, Broward, City of Miami) expose identical `/api/search/v1/collections/dataset/items` endpoints with the same OGC Records response schema — verified via live API calls. The existing `hub_client.py` and `normalizer.py` require minimal changes.

The primary architectural risk is the Database Schema V3 migration. The current `datasets.id TEXT PRIMARY KEY` is portal-scoped, and adding multiple jurisdictions creates an ID collision risk (federated ArcGIS content could share UUIDs across portals, and `INSERT OR REPLACE` would silently overwrite one jurisdiction's data). This must be resolved with a synthetic composite key (`"{jurisdiction}:{original_id}"`) before any multi-portal data enters the database, and the migration must be tested against the committed production database with `PRAGMA foreign_key_check` to verify no enrichment or audit data is lost. City of Miami operates a second Socrata portal (`data.miamigov.com`) that is explicitly out of scope for v1.1 — the ArcGIS Hub portal covers GIS datasets, and adding a Socrata client would double the ingestion code surface for minimal gain at this milestone.

## Key Findings

### Recommended Stack

No new pip dependencies are needed for v1.1 features, with one justified exception: `feedgen>=1.0.0` for RSS/Atom feed generation. The STACK.md research recommended against feedgen (citing an outdated concern about lxml dependency — feedgen's actual dependency is `python-dateutil`, not lxml), while PITFALLS.md identifies the RFC 822 date format requirement for RSS 2.0 as a real trap that feedgen resolves internally. Accept feedgen as the single new dependency. All other features use stdlib modules (`xml.etree.ElementTree` is suitable for Atom-only output but feedgen handles both formats and date conversion). The Schema V3 migration adds two SQL alterations to the existing `db.py` migration pattern: `ALTER TABLE columns ADD COLUMN ai_description TEXT` and a `CREATE INDEX` on `source_portal`.

**Core technologies:**
- `feedgen>=1.0.0`: RSS 2.0 + Atom 1.0 feed generation — handles RFC 822/ISO 8601 date format conversion internally; single new dependency justified by correctness risk
- `csv.DictWriter` + `json` (stdlib): JSON and CSV catalog export — zero new dependencies; `build_site_data()` already produces the joined dataset struct
- Anthropic SDK (existing) + new `FieldEnrichmentResult` Pydantic model: Field-level AI descriptions — extends existing structured output pattern; same `messages.parse()` call
- `httpx` (existing, parameterized): Multi-jurisdiction ArcGIS Hub ingestion — convert module-level constant to `create_client(base_url: str)` parameter
- SQLite Schema V3: `ai_description` column on `columns` table + index on `source_portal` + data migration of existing rows from `"arcgis_hub"` to `"miami-dade"` slug

**Version requirements:** Python 3.12+, SQLite 3.41+ (shipped with Python 3.12). `ALTER TABLE ADD COLUMN` confirmed supported. No compilation-dependent packages introduced.

**Do not add:** `lxml` (not needed; feedgen does not require it), `pandas` (stdlib `csv` + `json` are sufficient for export), `sodapy` (City of Miami Socrata is out of scope for v1.1), `aiohttp` / async patterns (three portals at 1 req/sec each = ~12 min total sequential pull; acceptable for weekly CI runs), `python-feedgen` installed via old feedgen path (install as `feedgen`, not `python-feedgen`).

### Expected Features

**Must have (table stakes):**
- Jurisdiction filter on browse page — without it, Broward/City of Miami datasets mix confusingly into Miami-Dade results
- Jurisdiction badge on every dataset card and detail page — "Building Permits" is ambiguous without knowing the source government
- Feed autodiscovery `<link rel="alternate">` in HTML `<head>` — standard browser and reader auto-detection
- Feed linked from site navigation with RSS icon
- Download links discoverable on About page — JSON and CSV exports must be findable without hunting
- Field descriptions displayed inline in existing columns table on dataset detail page
- Enrichment `--dry-run` cost estimate verified working for new jurisdiction datasets

**Should have (differentiators):**
- Schema change diffs in RSS feed — no open data portal surfaces column additions/removals as a subscribable feed; unique in the open data space
- AI-enriched catalog export (JSON + CSV with DCAT-US v1.1 alignment) — richer than raw portal metadata; enables data.gov harvesting
- Field-level plain-English column descriptions — enterprise catalogs do this internally; no public civic data portal does
- Tri-county unified search — no existing tool unifies South Florida open data across Miami-Dade, Broward, and City of Miami
- Per-jurisdiction quality score comparison — accountability metric across governments; falls out naturally from applying existing audit to new jurisdictions

**Defer to v1.2+:**
- City of Miami Socrata portal (`data.miamigov.com`) — requires a separate `SocrataClient`, different metadata schema, cross-platform deduplication
- DCAT-US v3.0 compliance — draft spec, not yet required; use v1.1 field names and migrate when finalized
- Per-jurisdiction RSS feeds — single feed with jurisdiction-tagged entries is sufficient for initial subscriber base
- Real-time feed updates (WebSub/PubSubHubbub) — static site architecture precludes push; weekly cadence makes this irrelevant
- Column enrichment for sub-B datasets — garbage-in-garbage-out risk; expand threshold in v1.2 after prompt quality validation
- Jurisdiction-specific enrichment system prompts — a `{jurisdiction}` variable in a single template is sufficient

### Architecture Approach

The v1.1 architecture is additive rather than structural. Six new files (approximately 345 lines estimated) and thirteen existing files modified with contained, low-risk changes. The most important new abstraction is `jurisdictions.py` — a registry mapping jurisdiction slug keys to portal URLs and display names. This single-source-of-truth config replaces the hardcoded constants scattered across six files and ensures adding v1.2 jurisdictions requires only config changes. Feed and catalog export are generated inside the existing `generate_site()` function using the same `site_data` dict that drives HTML rendering, ensuring exports always match the published site content exactly.

**Major components and v1.1 changes:**
1. `jurisdictions.py` (NEW) — jurisdiction registry dict; all portal configuration in one place
2. `ingestion/hub_client.py` (MODIFIED) — `create_client(base_url: str)` replaces `HUB_BASE_URL` module constant
3. `ingestion/normalizer.py` (MODIFIED) — accepts `jurisdiction` parameter; builds correct `source_portal` and `source_url` per jurisdiction
4. `db.py` (MODIFIED) — Schema V3: `ai_description` column on `columns`, `source_portal` index, data migration from `"arcgis_hub"` to `"miami-dade"` slug
5. `diff/detector.py` (MODIFIED) — per-jurisdiction snapshot filtering to prevent cross-jurisdiction noise on first pull
6. `site/feed.py` (NEW) — RSS/Atom generation via feedgen, called from `generate_site()`
7. `site/catalog_export.py` (NEW) — JSON + CSV export, called from `generate_site()` using same `site_data` dict
8. `enrichment/field_prompts.py` + `enrichment/field_models.py` (NEW) — field enrichment prompt templates and `FieldEnrichmentResult` Pydantic model
9. Templates (MODIFIED) — jurisdiction badges, filter dropdown, RSS autodiscovery link, field description column, download links

**Key patterns to follow:**
- Generate feed and export inside `generate_site()`, never as separate CLI commands — keeps pipeline simple and artifacts in sync
- Batch all columns for a dataset into one API call, not per-column — 125 calls total vs 2,635
- Sequential per-jurisdiction pulls, not async — rate limits are per-portal; sequential is fine for weekly CI

### Critical Pitfalls

1. **Dataset ID collision across jurisdictions** — the `datasets.id TEXT PRIMARY KEY` is portal-scoped; federated ArcGIS content could collide via `INSERT OR REPLACE`. Prevention: migrate to a synthetic key (`"{jurisdiction_slug}:{original_id}"`) in Schema V3 before any multi-portal pull. Test on a DB copy; verify `PRAGMA foreign_key_check` passes; confirm enrichment and audit counts are unchanged post-migration.

2. **RSS feed relative URLs break every feed reader** — the site uses relative `base_url` paths in Jinja2; feed readers do not resolve relative URLs. Prevention: define a separate `site_url` (full canonical URL) used exclusively in feed link elements; add `--site-url` to `export` command; fail loudly if absent rather than generating a broken feed silently.

3. **RSS 2.0 requires RFC 822 date format, not ISO 8601** — the codebase stores timestamps as ISO 8601; passing them directly into RSS `<pubDate>` breaks feed readers. Prevention: use feedgen which accepts Python `datetime` objects and handles format conversion; parse `detected_at` strings back into `datetime` objects before passing to feedgen.

4. **Schema V3 migration data loss** — SQLite primary key changes require table recreation; dropping `datasets` with foreign keys enabled will cascade-delete all child rows. Prevention: `PRAGMA foreign_keys=OFF` during migration; migrate parent table before child tables; re-enable and run `PRAGMA foreign_key_check`.

5. **Field-level AI enrichment cost explosion** — output tokens scale with column count (not fixed like dataset enrichment); 2,635 columns across 125 B+ datasets estimated at ~$0.49 but this grows after multi-jurisdiction adds new B+ datasets. Prevention: always run `--dry-run` before batch; cap columns per call at 30; re-estimate after Phase 1 completes and new jurisdiction data is in DB.

6. **Field AI hallucination of column semantics** — ambiguous column names (e.g., `STATUS`, `FLD_ZONE`) produce plausible but wrong descriptions without sufficient context. Prevention: include dataset title, AI description, category, and department in the field enrichment prompt; add visible disclaimer and visual distinction (AI badge) on dataset detail page; keep portal-provided aliases in a separate display row.

## Implications for Roadmap

Based on the dependency graph from FEATURES.md and the architecture build order from ARCHITECTURE.md, a 5-phase structure is recommended.

### Phase 1: Multi-Jurisdiction Foundation
**Rationale:** Every other feature benefits from having all jurisdictions in the catalog from day one. RSS and export built before multi-jurisdiction would need rework. This phase also contains the highest-risk element (Schema V3 migration and ID key strategy) — front-loading it limits downstream blast radius. City of Miami Socrata scope decision must also be documented explicitly here.
**Delivers:** Unified catalog with Miami-Dade, Broward County, and City of Miami GIS datasets; `jurisdictions.py` registry; parameterized `hub_client.py`; Schema V3 (synthetic composite key, `ai_description` column, `source_portal` index, data migration); per-jurisdiction diff snapshots; `pull --jurisdiction` CLI option.
**Addresses:** Multi-jurisdiction feature; dataset ID collision pitfall; hardcoded URL pitfall; City of Miami Socrata scope (document as out-of-scope in config).
**Avoids:** Pitfalls 1 (ID collision), 4 (schema migration data loss). Establishes jurisdiction registry that prevents future hardcoding proliferation.

### Phase 2: RSS/Atom Feed
**Rationale:** Second because it should include all jurisdictions' change events, and the `feedgen` dependency is worth validating early before investing further. RSS feed delivers clear user value (subscribable changelog) at LOW implementation complexity once Phase 1 is complete.
**Delivers:** `site/feed.xml` (Atom 1.0) and `site/rss.xml` (RSS 2.0) generated inside `generate_site()`; max 25 most recent change entries; `<ttl>10080</ttl>` matching weekly cadence; autodiscovery link in HTML `<head>`; feed linked from site navigation; `--site-url` parameter on `export` command; feed XML validation in CI (`xmllint --noout`).
**Uses:** `feedgen>=1.0.0`; existing `changes` table via `get_recent_changes(limit=25, order_by='detected_at DESC')`.
**Avoids:** Pitfalls 2 (relative URLs), 3 (RFC 822 date format), and unbounded feed growth.

### Phase 3: Enriched Catalog Export
**Rationale:** Third because it benefits from multi-jurisdiction data and has zero implementation risk (stdlib only, no schema changes, no new deps). Independent of field AI descriptions and can ship immediately after Phase 1 if Phase 2 encounters issues.
**Delivers:** `site/downloads/catalog.json` (metadata envelope, jurisdiction field, AI enrichment fields, DCAT-US v1.1 field alignment) and `site/downloads/catalog.csv` (flat, pipe-delimited arrays, UTF-8 BOM for Excel on Windows); download links on About page with format and file size noted.
**Uses:** `json` and `csv` stdlib; existing `build_site_data()` — generates inside `generate_site()` from the same `site_data` dict used for HTML.
**Avoids:** Export-site data drift (same `site_data` dict, same function call), JSON serialization crash on non-serializable types (explicit field extraction), CSV encoding failure in Excel (UTF-8 BOM).

### Phase 4: AI Field-Level Descriptions
**Rationale:** Last among the core features because it has the highest complexity and the only real API cost. The site delivers full value without it. Benefits from having all three jurisdictions' B+ datasets in the DB before running — more eligible columns. Prompt quality validation on a sample (5-10 datasets) must precede any full batch run.
**Delivers:** Plain-English descriptions for all columns in ~125 B+ datasets (2,635 columns estimated pre-multi-jurisdiction); `enrich-fields` CLI command with `--dry-run`, `--limit`, and `--resume` flags; `columns.ai_description` displayed inline in dataset detail page columns table with AI badge and disclaimer; field description quality validation on sample before full batch.
**Uses:** Existing Anthropic SDK; new `FieldEnrichmentResult` Pydantic model; new `field_prompts.py`; `columns.ai_description` column added in Phase 1 Schema V3.
**Avoids:** Per-column API calls (30 columns per call cap), cost explosion (dry-run gate before batch), hallucination (full dataset context in prompt), PII exposure in sample values (filter by column type).

### Phase 5: Site UI Polish and CI Pipeline
**Rationale:** Depends on all prior phases being functional. Unifies the UI changes that span multiple features and confirms the full pipeline runs correctly end-to-end in GitHub Actions before release.
**Delivers:** Jurisdiction filter dropdown on browse page (JS + template); jurisdiction badges on dataset cards; per-jurisdiction stats chips on homepage; jurisdiction field in Lunr.js search index; per-jurisdiction slug disambiguation (`/dataset/{jurisdiction}/{slug}/` URL scheme); updated CI pipeline (`pull --jurisdiction miami-dade broward city-of-miami`); feed XML validation step (`xmllint --noout`); full end-to-end pipeline test.
**Avoids:** Slug collision across jurisdictions (jurisdiction-scoped URL scheme), search index bloat (jurisdiction as filterable field not full-text indexed content), CI shipping broken feed silently.

### Phase Ordering Rationale

- Multi-jurisdiction must precede all other features — RSS feed and catalog export need jurisdiction metadata baked in from their first generation; rebuilding them post-multi-jurisdiction would duplicate effort.
- RSS before export — `feedgen` dependency validation is worth doing early; if feedgen causes environment issues, the export (stdlib-only) can ship independently as a fallback.
- Export before field AI — export has zero risk and delivers immediate value to power users; field AI requires careful prompt engineering and a cost estimation gate.
- Site polish last — requires all features functional before testing their integration; attempting UI polish mid-feature causes repeated template rework.
- Schema migration (ID composite key) must happen in Phase 1 before any multi-portal data enters the DB — post-load recovery from a collision is expensive and requires re-importing enrichments.

### Research Flags

Phases needing deeper research during planning:
- **Phase 1:** Schema V3 migration strategy for the synthetic composite key — research the exact SQLite migration sequence (`PRAGMA foreign_keys=OFF`, table recreation with rename, FK check) against the specific foreign key relationships in the existing schema. The V1-to-V2 migration in `db.py` is the template but the primary key change is more complex than the prior migration.
- **Phase 4:** Field enrichment prompt engineering — validate prompt output quality on 5-10 B+ datasets manually before batch run. Ambiguous single-word column names (`STATUS`, `TYPE`, `NAME`) need a confidence-flagging strategy documented before the batch.

Phases with standard, well-documented patterns (skip research-phase):
- **Phase 2:** RSS/Atom feed generation with feedgen v1.0.0 is thoroughly documented. The feed entry design and URL requirements are clear from PITFALLS.md.
- **Phase 3:** JSON and CSV export via stdlib is a solved problem. DCAT-US v1.1 field mapping is documented in the official spec.
- **Phase 5:** Static site UI additions (filter dropdowns, badges, stats chips) follow existing Jinja2/Lunr.js patterns already in the codebase. CI pipeline update is a one-line change to the pull command.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All three portals verified via live API calls; stdlib choices are official Python docs. One STACK.md vs PITFALLS.md divergence on feedgen resolved in favor of feedgen (RFC 822 date pitfall is real; lxml concern was misdirected). |
| Features | HIGH | All portal APIs live-verified; dataset counts confirmed (MDC 575, Broward 83, City of Miami 83); City of Miami dual-portal complication documented and explicitly scoped out. Build order validated against dependency graph in FEATURES.md. |
| Architecture | HIGH | Existing codebase analyzed directly; OGC API Records response schema confirmed identical across all three portals; B+ dataset and column counts queried from production DB (125 datasets, 2,635 columns). |
| Pitfalls | HIGH | Most pitfalls verified against actual codebase source (hardcoded constants confirmed in `hub_client.py` and `normalizer.py`); RFC 822 date issue confirmed against feedgen docs and W3C Feed Validator requirements; schema migration risk confirmed against SQLite documentation. |

**Overall confidence:** HIGH

### Gaps to Address

- **feedgen lxml dependency claim:** STACK.md states feedgen requires lxml, but PITFALLS.md and the feedgen GitHub repo indicate the dependency is `python-dateutil`, not lxml. Before Phase 2, run `pip show feedgen` in the project environment to confirm the actual dependency tree and verify no conflict with existing packages.

- **Synthetic key ID format for existing data:** The migration plan prefixes existing Miami-Dade IDs as `"miami-dade:{original_id}"`. Verify whether the published site exposes dataset IDs in any external-facing URL or API (e.g., dataset page URLs, search index, API endpoints). If dataset pages use slug-based URLs externally, the internal ID change is safe. If IDs appear in page URLs, this needs a URL redirect strategy.

- **B+ dataset count post-multi-jurisdiction:** The 125 B+ datasets figure is from the current Miami-Dade-only DB. After adding Broward (83 datasets) and City of Miami (83 datasets), the B+ count could increase by 20-50%, raising Phase 4 field enrichment cost proportionally. Re-run `--dry-run` cost estimate after Phase 1 completes before committing to Phase 4.

- **feedgen maintenance window:** Last PyPI release December 2023. For a static site with weekly CI, a stable release is acceptable. Verify `pip install feedgen` resolves without dependency conflicts against the existing `pyproject.toml` before Phase 2 implementation.

- **City of Miami ArcGIS Hub dataset completeness:** City of Miami ArcGIS Hub has 83 datasets (GIS-focused). The Socrata portal at `data.miamigov.com` covers non-GIS datasets (budget, permits, code enforcement). If stakeholders ask about missing City of Miami datasets, have the coverage explanation ready and documented in the site's About page.

## Sources

### Primary (HIGH confidence)
- Broward County GeoHub API: `https://geohub-bcgis.opendata.arcgis.com/api/search/v1/collections/dataset/items` — live API verified, 83 datasets, identical OGC Records schema
- City of Miami Open Data GIS API: `https://datahub-miamigis.opendata.arcgis.com/api/search/v1/collections/dataset/items` — live API verified, 83 datasets, identical OGC Records schema
- Miami-Dade Open Data Hub: `https://opendata.miamidade.gov` — existing portal, verified, ~575 datasets
- [python-feedgen 1.0.0 on PyPI](https://pypi.org/project/feedgen/) — version confirmed, release date Dec 2023
- [feedgen documentation](https://feedgen.kiesow.be/) — RSS 2.0 + Atom support, `datetime` object API
- [W3C Feed Validation Service](https://validator.w3.org/feed/) — RSS/Atom specification requirements
- [DCAT-US Schema v1.1](https://resources.data.gov/resources/dcat-us/) — required and optional field definitions for catalog JSON export
- [Python stdlib docs: csv, json, xml.etree.ElementTree, datetime](https://docs.python.org/3/library/) — official documentation
- Existing codebase: `db.py`, `hub_client.py`, `normalizer.py`, `generator.py`, `context.py`, `detector.py`, `cli.py`, `enrichment/client.py` — direct source code analysis confirming hardcoded constants and schema structure
- Production DB query: 125 B+ datasets (105 A, 20 B), 2,635 total columns — confirmed via live DB

### Secondary (MEDIUM confidence)
- [City of Miami Socrata portal](https://data.miamigov.com/) — active Socrata platform confirmed; DNS resolution intermittently failed during research
- [Socrata Developer Portal (City of Miami)](https://dev.socrata.com/foundry/data.miamigov.com/ub3m-qgg5) — confirms Socrata platform for `data.miamigov.com`
- [LLM-powered data classification at Grab](https://engineering.grab.com/llm-powered-data-classification) — batch column enrichment pattern (single API call per dataset vs per column)
- [arXiv: Using LLMs to Enrich Documentation](https://arxiv.org/html/2404.15320v1) — hallucination risks in column-level AI descriptions
- [arXiv: Automatic database description generation](https://arxiv.org/html/2502.20657v1) — LLM column description research

### Tertiary (LOW confidence)
- [Generative AI and Data Dictionary Descriptions (Medium)](https://medium.com/@fedenolasco/generative-ai-and-data-dictionary-descriptions-a2ba8c832afb) — single practitioner report; directionally consistent with arXiv sources
- [arXiv: Zero-Shot Topic Classification of Column Headers](https://arxiv.org/abs/2403.00884) — column classification accuracy context; methodology differs from civic data use case

---
*Research completed: 2026-02-26*
*Ready for roadmap: yes*
