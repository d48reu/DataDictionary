# Feature Research: v1.1 Regional Expansion

**Domain:** Open data catalog / encyclopedia -- new features for existing product
**Researched:** 2026-02-26
**Confidence:** HIGH (features build on verified v1.0 architecture; portal APIs confirmed live; library choices validated)

---

## Context: What Already Exists (v1.0 Shipped)

These features are already built and working. The v1.1 features below depend on them.

| Existing Feature | Relevant to v1.1 Because |
|------------------|--------------------------|
| ArcGIS Hub ingestion with field metadata | Multi-jurisdiction reuses this client with different base URLs |
| SQLite storage with `datasets`, `columns`, `enrichments`, `audit_scores`, `changes` tables | All four features read from or extend this schema |
| Claude AI enrichment (dataset-level descriptions, use cases, keywords) | Field-level AI descriptions extend the enrichment pipeline |
| Change detection (added/removed/schema_changed) | RSS feed consumes these records directly |
| Static site generation (Jinja2 templates, Lunr.js search) | Feed and export files are generated alongside existing site output |
| CLI tool with `pull`, `enrich`, `audit`, `diff`, `export`, `stats`, `serve` | New commands or options integrate into existing CLI |
| GitHub Actions weekly pipeline | Must accommodate new jurisdictions and feed generation |

---

## v1.1 Feature Analysis

### Feature 1: RSS/Atom Feed for Catalog Changes

**What it is:** An XML feed (Atom preferred, RSS 2.0 also generated) that surfaces dataset additions, removals, and schema changes detected during weekly pulls. Subscribers get notified of catalog changes via any feed reader.

**Expected behavior in the wild:**
- ArcGIS Hub itself offers GeoRSS feeds for catalog search results, but these show the _datasets themselves_ not _changes to the catalog_ -- a critical distinction. Our feed tracks the delta, not the inventory.
- CKAN exposes `/feeds/dataset.atom` for recently-updated datasets, but not schema-level changes.
- No open data portal surfaces schema change diffs (columns added/removed) in a feed format. This is a differentiator.

**How it works technically:**
- The `changes` table already stores `change_type` (added/removed/schema_changed), `details` (JSON with column diffs), and `detected_at` timestamps. This is the feed's data source.
- The `python-feedgen` library (v1.0.0, stable, last release Dec 2023) generates both Atom and RSS 2.0 XML from the same data. It is the standard Python feed generation library -- no realistic alternatives needed.
- Feed is generated as static XML files (`feed.atom`, `feed.rss`) during the `export` command, alongside HTML pages.
- Each change record becomes a feed entry with: title (e.g., "New dataset: Transit Routes"), link (to dataset page or changes page), description (plain-English summary of the change), and timestamp.
- Feed URL is stable (e.g., `/feed.atom`) so subscribers can bookmark it.

**Dependency on existing:** Direct. Reads from `changes` table via `get_recent_changes()`. No new data collection needed.

| Aspect | Assessment |
|--------|-----------|
| Complexity | LOW |
| New dependencies | `feedgen` (single library, 1.0.0 stable) |
| Schema changes | None -- reads existing `changes` table |
| API calls needed | None -- uses already-collected diff data |
| Risk | Minimal -- well-understood problem, mature library |

---

### Feature 2: Downloadable Enriched Catalog (JSON + CSV)

**What it is:** The full catalog exported as two downloadable files -- a JSON file and a CSV file -- containing all dataset metadata plus AI enrichment data (descriptions, use cases, keywords, department, civic relevance) and quality scores. Available as static files linked from the site.

**Expected behavior in the wild:**
- CKAN exposes a `data.json` file at the catalog root following the DCAT-US schema (required for federal data.gov harvesting). This is the industry standard for catalog exports.
- Socrata/Tyler portals expose the Socrata Discovery API for bulk metadata access but not a single downloadable file.
- ArcGIS Hub offers DCAT feeds for catalog federation, but the output is raw metadata without enrichment.
- No existing portal exports _enriched_ metadata (AI descriptions + quality scores). This is a differentiator.

**Two formats, different audiences:**
- **JSON:** Developer-friendly. Structured, nested. Can include arrays (use_cases, keywords, column lists). Follows DCAT-US field naming conventions where applicable for interoperability, but includes custom enrichment fields.
- **CSV:** Analyst-friendly. Flat, one row per dataset. Arrays are pipe-delimited (e.g., `keyword1|keyword2`). Columns are serialized as a count rather than nested objects. Importable into Excel/Google Sheets.

**DCAT-US v1.1 alignment (for JSON export):**
The JSON export should include DCAT-US required fields where data exists, making the catalog harvestable by data.gov or other aggregators:

| DCAT-US Field | Our Source | Required? |
|---------------|------------|-----------|
| `title` | `datasets.title` | Yes |
| `description` | `enrichments.description` (AI) or `datasets.description` (original) | Yes |
| `keyword` | `enrichments.keywords` (AI-enriched) | Yes |
| `modified` | `datasets.updated_at` | Yes |
| `publisher` | `datasets.publisher` | Yes |
| `identifier` | `datasets.id` | Yes |
| `accessLevel` | "public" (all datasets are open data) | Yes |
| `contactPoint` | Not available -- omit | Required but unavailable |
| `distribution` | `datasets.download_url`, `datasets.api_endpoint` | Required-if |
| `license` | `datasets.license` | Required-if |
| `spatial` | `datasets.bbox` | Required-if |

Custom enrichment fields (prefixed `mdc:` or nested under `enrichment`) include: `ai_description`, `use_cases`, `civic_relevance`, `department`, `update_frequency`, `quality_score`, `letter_grade`.

**Dependency on existing:** Direct. Reads from `datasets` + `enrichments` + `audit_scores` tables via existing queries in `context.py`. The `build_site_data()` function already joins all three tables.

| Aspect | Assessment |
|--------|-----------|
| Complexity | LOW |
| New dependencies | None -- `json` and `csv` are stdlib |
| Schema changes | None -- reads existing tables |
| API calls needed | None -- uses already-collected data |
| Risk | Minimal -- straightforward serialization |

---

### Feature 3: AI Field-Level Descriptions (B+ Datasets)

**What it is:** Claude-generated plain-English descriptions for individual columns/fields within datasets that already have high quality scores (B+ grade or above). Transforms cryptic field names like `OBJECTID`, `Shape__Length`, `ZONING_DESC` into human-readable explanations.

**Expected behavior in the wild:**
- Enterprise data catalogs (DataHub, Atlan, OpenMetadata) use LLMs to generate column descriptions at scale. This is an established pattern in enterprise data management but has not been applied to civic open data portals.
- Research confirms column descriptions should be under 20 words for readability and downstream usefulness. Longer descriptions hurt more than they help.
- Context matters: the same column name means different things in different datasets. "AGE" in a `Customer` table vs a `Building` table. The prompt must include the dataset context (title, description, other columns) when describing each field.
- Best practice from Grab's engineering team: batch related columns together in a single LLM call rather than one call per column. This reduces cost and improves contextual accuracy.

**Why B+ datasets only:**
- B+ datasets (composite_score >= 0.8) have sufficient metadata for the AI to produce accurate descriptions: they have documented columns, descriptions, and recent updates.
- Lower-quality datasets may have garbage column names, no context, or stale metadata -- AI descriptions would be unreliable.
- This keeps API costs controlled. With 570+ datasets and potentially 20-50 columns each, enriching all columns would cost 10x+ the dataset-level enrichment.
- Based on existing audit data, roughly 20-30% of datasets score B+ or above, so this targets ~115-170 datasets.

**How it works technically:**
- New table `column_enrichments` (or extend existing `columns` table with `ai_description` and `enriched_at` columns).
- New enrichment prompt that includes dataset context + all column names/types, asks for a short (10-20 word) plain-English description per column.
- Uses structured output (Pydantic model) like existing dataset enrichment.
- Single API call per dataset (all columns described at once), not per column.
- Only targets datasets where `audit_scores.letter_grade IN ('A', 'B')` AND `columns` table has entries.
- Display on dataset detail page alongside existing column table (currently shows name + type + raw description).

**Cost estimation:**
- ~150 datasets at B+ or above with columns
- ~30 columns average per dataset = 4,500 column descriptions
- One API call per dataset (all columns in one prompt) = ~150 API calls
- At Haiku pricing ($1/MTok input, $5/MTok output): estimated $0.50-$1.50 total
- Well within the existing $5 auto-proceed threshold

**Dependency on existing:** Extends the enrichment pipeline. Requires `columns` table (populated during pull), `audit_scores` table (to filter B+ datasets), and the Anthropic client infrastructure.

| Aspect | Assessment |
|--------|-----------|
| Complexity | MEDIUM |
| New dependencies | None -- uses existing Anthropic SDK and Pydantic |
| Schema changes | YES -- new `column_enrichments` table or new columns on `columns` table (schema V3 migration) |
| API calls needed | ~150 Anthropic API calls (one per qualifying dataset) |
| Risk | MEDIUM -- prompt engineering needed to handle diverse column types; cost must be estimated accurately |

---

### Feature 4: Multi-Jurisdiction Support (Broward County + City of Miami)

**What it is:** Extending the encyclopedia to pull, enrich, audit, and display datasets from two additional jurisdictions alongside Miami-Dade County. All three jurisdictions appear in a unified catalog with jurisdiction filtering.

**Portal landscape (verified live, 2026-02-26):**

| Jurisdiction | Portal | URL | Platform | API | Datasets |
|-------------|--------|-----|----------|-----|----------|
| Miami-Dade County | Open Data Hub | `opendata.miamidade.gov` | ArcGIS Hub | `/api/search/v1` | ~570 |
| Broward County | GeoHub | `geohub-bcgis.opendata.arcgis.com` | ArcGIS Hub | `/api/search/v1` | ~83 |
| City of Miami (GIS) | Open Data GIS | `datahub-miamigis.opendata.arcgis.com` | ArcGIS Hub | `/api/search/v1` | ~83 |
| City of Miami (non-GIS) | Open Data Portal | `data.miamigov.com` | Socrata/Tyler | SODA API | Unknown |

**Critical finding:** All three primary portals (Miami-Dade, Broward, City of Miami GIS) use the same ArcGIS Hub platform with the identical `/api/search/v1` search endpoint. The existing `hub_client.py` can be reused with zero changes to the API interaction logic -- only the base URL needs to be configurable.

**The City of Miami Socrata complication:** City of Miami also has a Socrata/Tyler portal at `data.miamigov.com` with non-GIS datasets (budget, permits, etc.). This uses a completely different API (Socrata Discovery API / SODA). Recommendation: **defer Socrata ingestion** to v1.2. The three ArcGIS Hub portals give plenty of coverage for v1.1 without adding a second API client.

**Architecture implications:**

1. **Hub client parameterization:** Change `HUB_BASE_URL` from a constant to a configuration parameter. The `create_client()` function takes a `base_url` argument.

2. **Dataset `source_portal` field:** Already exists in the schema (`datasets.source_portal TEXT NOT NULL`). Currently set to "ArcGIS Hub" for all records. For multi-jurisdiction, this should be the jurisdiction name (e.g., "Miami-Dade County", "Broward County", "City of Miami").

3. **Jurisdiction configuration:** A config dict or YAML file mapping jurisdiction names to portal URLs:
   ```python
   JURISDICTIONS = {
       "Miami-Dade County": "https://opendata.miamidade.gov",
       "Broward County": "https://geohub-bcgis.opendata.arcgis.com",
       "City of Miami": "https://datahub-miamigis.opendata.arcgis.com",
   }
   ```

4. **Pull command changes:** The `pull` command iterates over all configured jurisdictions (or accepts `--jurisdiction` flag to pull one). Each jurisdiction's datasets are stored with the appropriate `source_portal` value.

5. **Deduplication across jurisdictions:** Possible but unlikely that the same dataset appears on multiple ArcGIS Hub portals with different IDs. The existing `id` field (ArcGIS-assigned UUID) is globally unique. Cross-jurisdiction dedup is a non-issue for ArcGIS Hub.

6. **Site UI changes:** Jurisdiction filter on browse page (similar to existing format/publisher/tag filters). Jurisdiction badge on dataset cards and detail pages. Stats breakdown by jurisdiction on homepage.

7. **Rate limiting:** Three portals at 1 req/s each. Pulling sequentially means 3x longer pull times. With Broward (83 datasets) and City of Miami (83 datasets) being much smaller than Miami-Dade (570), the total pull time increases by roughly 30% -- manageable within GitHub Actions timeout.

8. **Enrichment scope:** New datasets from new jurisdictions need enrichment. The existing `get_unenriched_datasets()` query works unchanged -- it returns any dataset without an enrichment record regardless of source_portal. The enrichment prompt currently references "Miami-Dade County" explicitly and must be generalized.

9. **Search index:** Lunr.js index builds from all datasets regardless of source_portal. Jurisdiction becomes a searchable/filterable field.

**Dependency on existing:** High reuse. The hub_client, normalizer, field_fetcher, enrichment pipeline, audit scorer, diff detector, and site generator all work with minimal changes. The main work is parameterization and UI updates.

| Aspect | Assessment |
|--------|-----------|
| Complexity | MEDIUM-HIGH |
| New dependencies | None |
| Schema changes | Minimal -- `source_portal` already exists; may add `jurisdiction` as explicit field |
| API calls needed | ~166 additional ArcGIS Hub API calls (83+83 datasets from two new portals) |
| Risk | MEDIUM -- enrichment prompt must be jurisdiction-aware; pull time increases; CI pipeline must handle three sequential pulls |

---

## Table Stakes for v1.1

Features that users of the _existing_ product will expect once v1.1 ships. Missing these makes the upgrade feel incomplete.

| Feature | Why Expected | Complexity | Depends On |
|---------|--------------|------------|------------|
| **Jurisdiction filter on browse page** | If catalog has datasets from 3 jurisdictions, users must be able to filter by jurisdiction. Without it, Broward datasets mixed into Miami-Dade results confuse users. | LOW | Multi-jurisdiction support |
| **Jurisdiction badge on dataset cards** | Users need to see at a glance which government a dataset belongs to. Otherwise "Building Permits" is ambiguous -- Miami-Dade's or City of Miami's? | LOW | Multi-jurisdiction support |
| **Feed autodiscovery link in HTML head** | Standard `<link rel="alternate" type="application/atom+xml">` tag so browsers and feed readers auto-detect the feed. Without it, users must manually find the feed URL. | LOW | RSS/Atom feed |
| **Feed linked from site navigation** | Prominent link to feed in site header/footer. RSS icon is universally recognized. | LOW | RSS/Atom feed |
| **Download links on about page or data page** | JSON and CSV exports must be discoverable. A "Download Catalog" section with format options. | LOW | Downloadable catalog |
| **Field descriptions visible on dataset page** | AI column descriptions must appear inline in the existing column table on dataset detail pages. Users should not have to navigate elsewhere. | LOW | AI field descriptions |
| **Enrichment cost estimate for new jurisdictions** | `--dry-run` must show costs for new jurisdiction datasets before spending API credits. Already works, but must be verified with multi-jurisdiction datasets. | LOW | Multi-jurisdiction + existing enrichment |

---

## Differentiators for v1.1

Features that set v1.1 apart. These create value beyond what any existing open data portal offers.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Schema change diff in RSS feed** | No open data portal surfaces column additions/removals in a subscribable feed. Developers and journalists can track when datasets gain or lose fields. | LOW | Unique in the open data space. Builds on existing diff detection. |
| **AI-enriched catalog export** | Downloadable JSON/CSV with AI descriptions, use cases, quality scores -- not just raw metadata. Developers get a richer dataset than the source portal provides. | LOW | No portal offers enriched exports. DCAT-US alignment makes it harvestable. |
| **Field-level plain-English descriptions** | Column names like `ZONING_DESC` become "Zoning designation code describing the allowed land use for a parcel." Makes datasets accessible to non-technical users at the field level. | MEDIUM | Enterprise data catalogs do this internally; no public open data portal does. |
| **Tri-county unified catalog** | Searching "building permits" returns results from Miami-Dade, Broward, and City of Miami in one place. No existing tool unifies South Florida open data. | MEDIUM-HIGH | Regional view that no government portal provides. Journalists and researchers need cross-jurisdiction comparison. |
| **Per-jurisdiction quality comparison** | Quality scores across jurisdictions enable comparison: "Broward's data quality averages B while City of Miami averages C." Accountability extends beyond one government. | LOW | Falls out naturally from applying existing audit to new jurisdictions. |

---

## Anti-Features for v1.1

Features to explicitly NOT build in this milestone.

| Anti-Feature | Why Tempting | Why Avoid | What to Do Instead |
|--------------|-------------|-----------|-------------------|
| **Socrata ingestion for City of Miami** | City of Miami has a Socrata portal (data.miamigov.com) with non-GIS datasets. Feels incomplete to skip it. | Adds a completely different API client (SODA), different metadata schema, different rate limiting, and cross-platform dedup complexity. Doubles the ingestion code surface for ~50 additional datasets. | Defer to v1.2. Ship v1.1 with ArcGIS Hub only for all three jurisdictions. Note on the site that non-GIS City of Miami data is coming soon. |
| **DCAT-US v3.0 compliance** | DCAT-US 3.0 was recently drafted. Future-proofing feels smart. | v3.0 is not yet finalized or required. v1.1 alignment is the current standard for data.gov harvesting. Building for a draft spec risks rework. | Use DCAT-US v1.1 field names in JSON export. Migrate to v3.0 when finalized. |
| **Full DCAT-AP / JSON-LD export** | Linked Data export would make the catalog interoperable with European data portals and semantic web tools. | Massive scope expansion for near-zero user value. None of the target audience (Miami residents, journalists, local developers) uses JSON-LD or RDF. | Plain JSON and CSV are sufficient. Add a `conformsTo` field pointing to DCAT-US v1.1 for discoverability. |
| **Feed filtering / per-jurisdiction feeds** | Users might want a feed for only Broward changes, not all three jurisdictions. | Multiplies feed files (3 jurisdictions x 2 formats = 6 files instead of 2). Adds complexity for a feature that may have single-digit subscribers initially. | Single feed with all jurisdictions. Each entry includes jurisdiction in title. Revisit per-jurisdiction feeds if demand emerges. |
| **Real-time feed updates** | Push notifications or WebSub/PubSubHubbub for instant feed delivery. | Static site cannot push. Weekly pull cadence means feed updates weekly anyway. Real-time infra is antithetical to the architecture. | Weekly feed updates match the weekly pull cadence. This is appropriate for a catalog that changes slowly. |
| **Enriching all dataset columns regardless of quality** | More coverage sounds better. | Low-quality datasets have cryptic, undocumented columns. AI descriptions would be unreliable (garbage in, garbage out). Cost would be 5-10x higher. | B+ threshold ensures AI has enough context to produce accurate descriptions. Expand threshold downward in v1.2 once prompt quality is validated. |
| **CLI command for feed subscription management** | "Subscribe to the feed from the CLI." | The CLI generates static files. Subscription management implies a server or notification system. Users subscribe via their own feed reader. | Document the feed URL in the CLI output after `export` and on the site's about page. |
| **Jurisdiction-specific enrichment prompts** | Different system prompts for different jurisdictions. "You are a Broward County data librarian..." | Unnecessary complexity. The enrichment prompt can be jurisdiction-aware by receiving the jurisdiction name as a variable. The core task (describe this dataset in plain English) is the same. | Single prompt template with a `{jurisdiction}` variable. "You are a {jurisdiction} data librarian helping residents understand open datasets." |

---

## Feature Dependencies (v1.1)

```
[Multi-Jurisdiction Support]
    ├──requires──> [Hub Client Parameterization]
    │                  └── hub_client.py: HUB_BASE_URL -> configurable parameter
    ├──requires──> [Jurisdiction Config]
    │                  └── jurisdictions dict/YAML with name -> URL mapping
    ├──requires──> [Pull Command Iteration]
    │                  └── Loop over jurisdictions or accept --jurisdiction flag
    ├──requires──> [Enrichment Prompt Generalization]
    │                  └── Replace "Miami-Dade County" with {jurisdiction} variable
    ├──enables──> [Per-Jurisdiction Stats on Homepage]
    ├──enables──> [Jurisdiction Filter on Browse Page]
    ├──enables──> [Jurisdiction Badge on Dataset Cards]
    └──enables──> [Cross-Jurisdiction Quality Comparison]

[RSS/Atom Feed]
    ├──requires──> [changes table data] (already exists)
    ├──requires──> [feedgen library] (new dependency)
    ├──requires──> [Feed generation in export command]
    │                  └── Generate feed.atom + feed.rss alongside HTML
    ├──enables──> [Feed autodiscovery in HTML <head>]
    └──enables──> [Feed link in site navigation]

[Downloadable Enriched Catalog]
    ├──requires──> [datasets + enrichments + audit_scores data] (already exists)
    ├──requires──> [JSON serialization logic] (stdlib)
    ├──requires──> [CSV serialization logic] (stdlib)
    ├──requires──> [Export generation in export command]
    │                  └── Generate catalog.json + catalog.csv alongside HTML
    └──enables──> [Download links on site]

[AI Field-Level Descriptions]
    ├──requires──> [columns table data] (already exists)
    ├──requires──> [audit_scores data for B+ filtering] (already exists)
    ├──requires──> [Schema V3 migration] (new column_enrichments table or columns extension)
    ├──requires──> [New Pydantic model for field enrichment output]
    ├──requires──> [New enrichment prompt for column descriptions]
    ├──requires──> [New CLI command or --fields flag on enrich command]
    └──enables──> [Enhanced dataset detail pages with field descriptions]
```

**Critical path:** Multi-jurisdiction should be built BEFORE RSS feed and catalog export, because feeds and exports should include all jurisdictions from the start. Field-level AI descriptions are independent and can be built in parallel.

**Recommended build order:**
1. Multi-jurisdiction support (unlocks full catalog scope)
2. RSS/Atom feed (consumes changes from all jurisdictions)
3. Downloadable catalog export (exports full multi-jurisdiction catalog)
4. AI field-level descriptions (independent, can be last)

---

## Complexity and Effort Summary

| Feature | Complexity | Estimated Effort | New Dependencies | Schema Changes | API Cost |
|---------|-----------|-----------------|-----------------|---------------|----------|
| RSS/Atom Feed | LOW | 1-2 days | `feedgen` | None | $0 |
| Downloadable Catalog (JSON+CSV) | LOW | 1-2 days | None (stdlib) | None | $0 |
| AI Field Descriptions | MEDIUM | 2-3 days | None | V3 migration | ~$1 |
| Multi-Jurisdiction | MEDIUM-HIGH | 3-5 days | None | Minimal | ~$0.50 (enrichment for ~166 new datasets) |

**Total estimated effort:** 7-12 days
**Total estimated API cost:** ~$1.50

---

## Sources

### RSS/Atom Feed
- [python-feedgen library (v1.0.0)](https://github.com/lkiesow/python-feedgen) -- HIGH confidence, verified on PyPI
- [python-feedgen documentation](https://feedgen.kiesow.be/) -- Official docs, API reference
- [ArcGIS Hub catalog feeds (GeoRSS, DCAT)](https://www.esri.com/arcgis-blog/products/arcgis-hub/data-management/arcgis-hub-catalog-feeds-support-dcat-rss-ogc/) -- Context on how ArcGIS Hub does feeds differently

### Downloadable Catalog Export
- [DCAT-US Schema v1.1 (Project Open Data)](https://resources.data.gov/resources/dcat-us/) -- HIGH confidence, official US government standard
- [DCAT-US field mappings](https://resources.data.gov/resources/podm-field-mapping/) -- Required/optional field details
- [DCAT-US v3.0 draft](https://doi-do.github.io/dcat-us/) -- Future direction, not yet required

### AI Field Descriptions
- [Automatic database description generation (arXiv)](https://arxiv.org/html/2502.20657v1) -- Research on LLM column descriptions
- [LLM-powered data classification at Grab](https://engineering.grab.com/llm-powered-data-classification) -- Batch column enrichment patterns
- [IBM Knowledge Catalog LLM enrichment](https://guptaneeru.medium.com/with-the-advances-in-technology-a-large-amount-of-data-is-produced-daily-3556a9b643b1) -- Enterprise metadata enrichment patterns
- [DataHub AI-assisted catalogs](https://datahub.com/blog/ai-assisted-data-catalogs-an-llm-powered-by-knowledge-graphs-for-metadata-discovery/) -- Industry context

### Multi-Jurisdiction Portals (verified live 2026-02-26)
- [Broward County GeoHub](https://geohub-bcgis.opendata.arcgis.com/) -- ArcGIS Hub, 83 datasets, `/api/search/v1` confirmed working
- [City of Miami Open Data GIS](https://datahub-miamigis.opendata.arcgis.com/) -- ArcGIS Hub, 83 datasets, `/api/search/v1` confirmed working
- [City of Miami Socrata portal](https://data.miamigov.com/) -- Socrata/Tyler platform, deferred to v1.2
- [Socrata Developer Portal (City of Miami)](https://dev.socrata.com/foundry/data.miamigov.com/ub3m-qgg5) -- Confirms Socrata platform

---
*Feature research for: MDC Open Data Encyclopedia v1.1*
*Researched: 2026-02-26*
