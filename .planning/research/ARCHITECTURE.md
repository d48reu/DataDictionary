# Architecture Patterns: v1.1 Feature Integration

**Domain:** Open Data Encyclopedia -- v1.1 milestone (RSS feed, enriched export, field-level AI descriptions, multi-jurisdiction)
**Researched:** 2026-02-26
**Overall Confidence:** HIGH

---

## Executive Summary

The v1.1 features integrate cleanly into the existing architecture with no rewrites required. The codebase's modular separation (ingestion, enrichment, audit, diff, site) creates natural insertion points for each feature. The biggest architectural change is multi-jurisdiction support, which threads a `jurisdiction` concept through every layer from ingestion to rendering. The other three features (RSS, enriched export, field-level AI) are additive -- new modules or extensions to existing ones with modest schema changes.

**Verified findings:**
- Broward County (`geohub-bcgis.opendata.arcgis.com`) and City of Miami (`datahub-miamigis.opendata.arcgis.com`) both expose the identical ArcGIS Hub Search API at `/api/search/v1/collections/dataset/items` -- same OGC Records response schema, same property keys. HIGH confidence (verified via live API calls).
- Broward County has 83 datasets; City of Miami has 83 datasets. Combined with Miami-Dade's 470, the unified catalog will be ~636 datasets.
- 125 B+ graded datasets (105 A, 20 B) with 2,635 total columns are eligible for field-level AI descriptions.
- `python-feedgen` v1.0.0 generates both RSS 2.0 and Atom XML to static files. Mature, stable, no active maintenance needed for this use case. HIGH confidence.

---

## Current Architecture (v1.0 Baseline)

```
CLI (cli.py, Click)
  |
  +-- pull -------> hub_client.py --[httpx]--> ArcGIS Hub API
  |                 normalizer.py                    |
  |                 field_fetcher.py                  |
  |                        |                          |
  |                        v                          |
  |                  db.py (SQLite)  <----------------+
  |                   datasets | columns | enrichments | audit_scores | changes
  |
  +-- enrich -----> enrichment/client.py --[anthropic]--> Claude API
  |                 enrichment/prompts.py
  |                 enrichment/models.py
  |
  +-- audit ------> audit/scorer.py
  |
  +-- diff -------> diff/detector.py
  |
  +-- export -----> site/generator.py
  |                 site/context.py -----> Jinja2 templates ---> static HTML
  |                 site/search_index.py -------> Lunr.js JSON
  |
  +-- stats ------> (inline queries)
  +-- serve ------> (http.server)

GitHub Actions (encyclopedia.yml)
  pull -> audit -> diff -> enrich -> commit DB -> export -> deploy Pages
```

**Key architectural constraints:**
1. Single `source_portal` value today: `"arcgis_hub"` (hardcoded for Miami-Dade)
2. `hub_client.py` has `HUB_BASE_URL = "https://opendata.miamidade.gov"` as a module constant
3. `normalizer.py` builds `source_url` with hardcoded `opendata.miamidade.gov` domain
4. DB schema has `source_portal TEXT` on datasets, currently always `"arcgis_hub"`
5. No `jurisdiction` concept anywhere in the schema or site rendering
6. Site templates show "MDC Data Encyclopedia" and "Miami-Dade County" throughout
7. `changes` table has no jurisdiction awareness
8. `export` command outputs flat static site with no jurisdiction-scoped URLs

---

## Feature 1: RSS/Atom Feed Generation

### Integration Point

The RSS feed is a **new output artifact** of the `export` command, generated alongside the HTML site. It reads from the `changes` table that already exists and is already populated by the `diff` detector during `pull`.

### Architecture Decision

Generate the feed as a static XML file during `export`, not as a separate CLI command. Rationale: the feed is a site artifact (consumed by browsers/readers at a URL), so it belongs in the site output alongside HTML and JSON. This keeps the pipeline simple -- no new CI step needed.

### New Component

```
src/mdc_encyclopedia/site/feed.py    (NEW)
```

### Data Flow

```
export command
  |
  +-- site/context.py::build_site_data()   (existing, already queries changes table)
  |        |
  |        v
  |   site_data["changes"]  (list of change dicts with dataset_id, change_type,
  |                           details, detected_at, title)
  |
  +-- site/feed.py::generate_feed(changes, datasets, output_dir, base_url)  (NEW)
         |
         +-- FeedGenerator()
         +-- For each recent change: fg.add_entry(title, link, description, pubDate)
         +-- fg.atom_file("site/feed.xml")
         +-- fg.rss_file("site/rss.xml")
```

### Schema Changes

None. The `changes` table already stores `dataset_id`, `change_type`, `details` (JSON), and `detected_at`. This is exactly what's needed for feed entries.

### Template Changes

- `base.html`: Add `<link rel="alternate" type="application/atom+xml" ...>` in `<head>` block
- `base.html`: Add "RSS Feed" link in footer or nav
- `changes.html`: Add RSS feed link/icon

### New Dependencies

```
feedgen>=1.0.0
```

`python-feedgen` v1.0.0 is stable (released 2023-12-25), supports both RSS 2.0 and Atom, writes directly to files via `rss_file()` and `atom_file()`. No alternative needed -- this library does exactly one thing well. Confidence: HIGH.

### Feed Entry Design

Each change record maps to one feed entry:

| Feed Field | Source |
|------------|--------|
| `title` | `"{change_type}: {dataset_title}"` (e.g., "New Dataset: Fire Stations") |
| `link` | `"{base_url}/dataset/{slug}/"` (for added/schema) or `"{base_url}/changes/"` (for removed) |
| `description` | Change details -- columns added/removed for schema changes, dataset category for additions |
| `published` | `detected_at` from changes table |
| `id` | `"urn:mdc-encyclopedia:change:{change_id}"` (stable unique ID) |

Feed-level metadata:
- Title: "Open Data Encyclopedia - Catalog Changes"
- Link: `"{base_url}/changes/"`
- Description: "New, removed, and schema-changed datasets from South Florida open data portals"
- Max entries: 50 most recent (keeps feed size manageable)

### Estimated Complexity: LOW

One new ~80-line module. No schema changes. No new CLI commands. Two template edits.

---

## Feature 2: Downloadable Enriched Catalog (JSON + CSV)

### Integration Point

Another **new output artifact** of the `export` command. Reads from the same `build_site_data()` output that already joins datasets + enrichments + audit_scores.

### Architecture Decision

Generate as static files during `export`, placed in `site/downloads/`. Rationale: same as RSS -- these are site artifacts consumed via download links. Users access them from the website.

### New Component

```
src/mdc_encyclopedia/site/catalog_export.py    (NEW)
```

### Data Flow

```
export command
  |
  +-- site/context.py::build_site_data()   (existing)
  |        |
  |        v
  |   site_data["datasets"]  (full list with enrichment + audit + columns)
  |
  +-- site/catalog_export.py::export_catalog(datasets, output_dir)  (NEW)
         |
         +-- Build flat list of dicts: id, title, description, ai_description,
         |   category, department, publisher, format, updated_at, letter_grade,
         |   composite_score, civic_relevance, use_cases (joined), keywords (joined),
         |   column_count, source_url, download_url, jurisdiction
         |
         +-- json.dump() -> site/downloads/catalog.json
         +-- csv.DictWriter() -> site/downloads/catalog.csv
```

### Schema Changes

None. All data is already in the database. The export is a different *view* of existing data.

### Template Changes

- `about.html` or new `downloads/index.html`: Add download links for JSON and CSV
- `base.html` nav: Consider adding "Downloads" link (or include on About page)

### New Dependencies

None. Python `json` and `csv` modules are stdlib.

### Export Schema Design

**JSON structure:**
```json
{
  "metadata": {
    "generated_at": "2026-02-26T06:00:00Z",
    "total_datasets": 636,
    "jurisdictions": ["miami-dade", "broward", "city-of-miami"],
    "version": "1.1"
  },
  "datasets": [
    {
      "id": "abc123",
      "title": "Fire Stations",
      "jurisdiction": "miami-dade",
      "ai_description": "...",
      "use_cases": ["...", "..."],
      "keywords": ["...", "..."],
      "department": "Fire Rescue",
      "category": "Public Safety",
      "civic_relevance": "HIGH",
      "letter_grade": "A",
      "composite_score": 0.92,
      "publisher": "...",
      "format": "Feature Service",
      "updated_at": "2026-01-15T...",
      "source_url": "https://...",
      "download_url": "https://...",
      "column_count": 15,
      "columns": [
        {"name": "OBJECTID", "type": "integer", "description": "...", "ai_description": "..."}
      ]
    }
  ]
}
```

**CSV structure:** Same fields, flattened. `use_cases` and `keywords` as semicolon-delimited strings. `columns` excluded from CSV (too complex for flat format; available in JSON).

### Estimated Complexity: LOW

One new ~100-line module. No schema changes. Stdlib-only. One or two template edits.

---

## Feature 3: AI Field-Level Descriptions (B+ Datasets)

### Integration Point

Extension of the existing **enrichment pipeline**. New Pydantic model, new prompt, new DB column, new CLI command. Renders in the existing `dataset.html` template's columns table.

### Architecture Decision

Implement as a new CLI command `enrich-fields` rather than a flag on `enrich`. Rationale: field-level enrichment has different scoping (B+ datasets only), different cost profile (many more API calls), and different resume semantics. Separating it makes the pipeline easier to control in CI.

### New/Modified Components

```
src/mdc_encyclopedia/enrichment/field_prompts.py    (NEW)
src/mdc_encyclopedia/enrichment/field_models.py     (NEW)
src/mdc_encyclopedia/enrichment/client.py           (MODIFIED - add enrich_fields function)
src/mdc_encyclopedia/db.py                          (MODIFIED - schema V3 + new queries)
src/mdc_encyclopedia/cli.py                         (MODIFIED - add enrich-fields command)
src/mdc_encyclopedia/site/context.py                (MODIFIED - include ai_description in columns)
```

### Data Flow

```
enrich-fields command
  |
  +-- Query: datasets with audit grade IN ('A', 'B')
  |          AND columns exist
  |          AND columns.ai_description IS NULL (at least one undescribed)
  |
  +-- For each eligible dataset:
  |     +-- Fetch columns for dataset (existing db.get_columns_for_dataset)
  |     +-- Build field enrichment prompt (all column names + types + dataset context)
  |     +-- Call Claude API with FieldEnrichmentResult model
  |     +-- UPDATE columns SET ai_description = ? WHERE dataset_id = ? AND name = ?
  |
  +-- Summary: enriched N datasets, M columns, cost $X
```

### Schema Changes

**Schema V3 upgrade (partial -- combined with multi-jurisdiction changes below):**

```sql
ALTER TABLE columns ADD COLUMN ai_description TEXT;
```

This adds a single nullable column to the existing `columns` table. Existing rows get NULL, which the template handles gracefully (already shows `--` for missing descriptions).

The `db.py` migration pattern is already established (`PRAGMA user_version` with `SCHEMA_V2_UPGRADE` as precedent). Add `SCHEMA_V3_UPGRADE` following the same pattern.

### Prompt Design

Send all columns for a dataset in one API call (not per-column). Rationale: columns are only meaningful in context of their dataset and sibling columns. A column named `FID` next to `ADDRESS` and `ZONE_CODE` in a zoning dataset gets a much better description than `FID` alone.

System prompt (field-specific):
```
You are a data dictionary specialist for South Florida government datasets.
For each column, write ONE plain-English sentence explaining what it contains
and why a resident might care about it. Be specific to the dataset context.
```

User prompt:
```
Dataset: {title}
About: {ai_description}
Category: {category}, Department: {department}

Describe each column:
- OBJECTID (integer)
- ADDRESS (text)
- ZONE_CODE (text)
...
```

Response model:

```python
class FieldDescription(pydantic.BaseModel):
    name: str
    description: str  # 1-sentence plain English

class FieldEnrichmentResult(pydantic.BaseModel):
    fields: list[FieldDescription]
```

### Cost Estimation

- 125 B+ datasets, average ~21 columns each (2,635 total columns)
- Estimated ~300 input tokens per dataset + ~20 tokens per column = ~720 tokens avg
- Estimated ~30 output tokens per column = ~630 tokens avg
- Total: ~90K input + ~79K output tokens
- At Haiku 4.5 pricing ($1/$5 per MTok): ~$0.49
- Very affordable. No cost threshold concerns.

### Template Changes

- `dataset.html`: In the columns table, add a 4th column "AI Description" showing `col.ai_description` when present
- Alternatively, replace the existing `Description` column with AI description when available, falling back to the ArcGIS alias

### Estimated Complexity: MEDIUM

New prompt/model files, one schema migration, new CLI command with cost estimation, template update. The enrichment client pattern is already established so this is mostly copy-and-adapt.

---

## Feature 4: Multi-Jurisdiction Support

### Integration Point

This is the most **cross-cutting** feature. It touches ingestion, normalization, DB schema, diffing, site generation, templates, search index, and CI pipeline.

### Architecture Decision

Use a **jurisdiction registry** pattern -- a configuration dict mapping jurisdiction slugs to their portal URLs and display names. This avoids hardcoding and makes adding future jurisdictions trivial. The `source_portal` column in the datasets table (currently always `"arcgis_hub"`) gets repurposed to store the jurisdiction slug.

### Jurisdiction Registry

```python
# src/mdc_encyclopedia/jurisdictions.py  (NEW)

JURISDICTIONS = {
    "miami-dade": {
        "name": "Miami-Dade County",
        "hub_base_url": "https://opendata.miamidade.gov",
        "short_name": "MDC",
    },
    "broward": {
        "name": "Broward County",
        "hub_base_url": "https://geohub-bcgis.opendata.arcgis.com",
        "short_name": "Broward",
    },
    "city-of-miami": {
        "name": "City of Miami",
        "hub_base_url": "https://datahub-miamigis.opendata.arcgis.com",
        "short_name": "Miami",
    },
}

DEFAULT_JURISDICTIONS = ["miami-dade"]  # Backward compatible default
```

### New/Modified Components

```
src/mdc_encyclopedia/jurisdictions.py               (NEW)
src/mdc_encyclopedia/ingestion/hub_client.py         (MODIFIED)
src/mdc_encyclopedia/ingestion/normalizer.py         (MODIFIED)
src/mdc_encyclopedia/ingestion/field_fetcher.py      (MODIFIED - pass client with correct base_url)
src/mdc_encyclopedia/db.py                           (MODIFIED - schema V3 + jurisdiction index)
src/mdc_encyclopedia/diff/detector.py                (MODIFIED - per-jurisdiction snapshots)
src/mdc_encyclopedia/site/context.py                 (MODIFIED - jurisdiction grouping + filter data)
src/mdc_encyclopedia/site/generator.py               (MODIFIED - jurisdiction filter pages)
src/mdc_encyclopedia/site/search_index.py            (MODIFIED - include jurisdiction in index)
src/mdc_encyclopedia/site/templates/base.html        (MODIFIED - jurisdiction in nav/title)
src/mdc_encyclopedia/site/templates/browse.html      (MODIFIED - jurisdiction filter dropdown)
src/mdc_encyclopedia/site/templates/dataset.html     (MODIFIED - show jurisdiction badge)
src/mdc_encyclopedia/site/templates/index.html       (MODIFIED - per-jurisdiction stats)
src/mdc_encyclopedia/site/static/filter.js           (MODIFIED - jurisdiction filter logic)
src/mdc_encyclopedia/cli.py                          (MODIFIED - --jurisdiction flag on pull)
.github/workflows/encyclopedia.yml                   (MODIFIED - pull for each jurisdiction)
```

### Data Flow Changes

**Ingestion (pull command):**

```
pull --jurisdiction miami-dade broward city-of-miami
  |
  +-- For each jurisdiction slug:
        +-- Look up JURISDICTIONS[slug]
        +-- create_client(base_url=jurisdiction["hub_base_url"])  <-- CHANGED
        +-- fetch_all_datasets(client)
        +-- normalize_hub_dataset(feature, jurisdiction=slug)     <-- CHANGED
        +-- upsert_dataset(conn, normalized)
        +-- fetch_fields_for_dataset(client, ...)
```

**Key change to hub_client.py:**

```python
# BEFORE (hardcoded)
HUB_BASE_URL = "https://opendata.miamidade.gov"

def create_client() -> httpx.Client:
    return httpx.Client(base_url=HUB_BASE_URL, ...)

# AFTER (parameterized)
def create_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, ...)
```

**Key change to normalizer.py:**

```python
# BEFORE (hardcoded source_url)
"source_portal": "arcgis_hub",
"source_url": f"https://opendata.miamidade.gov/datasets/{feature_id}",

# AFTER (jurisdiction-aware)
"source_portal": jurisdiction_slug,  # e.g., "miami-dade"
"source_url": f"{hub_base_url}/datasets/{feature_id}",
```

### Schema Changes

**Schema V3 (combined with field AI description):**

```sql
-- Add ai_description to columns
ALTER TABLE columns ADD COLUMN ai_description TEXT;

-- Add index on source_portal for jurisdiction filtering
CREATE INDEX IF NOT EXISTS idx_datasets_source_portal ON datasets(source_portal);

-- Migrate existing data to use jurisdiction slug
UPDATE datasets SET source_portal = 'miami-dade' WHERE source_portal = 'arcgis_hub';
```

Note: The existing `source_portal` column is reused. Currently all rows have value `"arcgis_hub"`. A data migration step updates existing rows. No new columns needed on the `datasets` table -- `source_portal` already serves as the jurisdiction identifier.

### Diff/Change Detection

The `diff/detector.py` currently takes a full-database snapshot. With multi-jurisdiction support, the snapshot should be per-jurisdiction to avoid cross-jurisdiction noise (e.g., Broward's first pull shouldn't show 83 "added" changes mixing with Miami-Dade's stable catalog).

```python
# BEFORE
pre_snapshot = capture_snapshot(conn)

# AFTER
pre_snapshot = capture_snapshot(conn, jurisdiction="broward")
# Filters: SELECT id FROM datasets WHERE source_portal = ?
```

### Site Generation Changes

**Unified catalog with jurisdiction filter:**

The site remains a single static site (not separate sites per jurisdiction). The browse page gets a jurisdiction filter dropdown alongside existing format/publisher/tag filters.

```
Homepage:
  - Stats cards: "636 datasets across 3 jurisdictions"
  - Per-jurisdiction stat chips: "MDC: 470 | Broward: 83 | Miami: 83"

Browse page:
  - Jurisdiction filter dropdown (Miami-Dade, Broward, City of Miami, All)
  - Existing filters (format, publisher, tags) remain
  - Dataset cards show jurisdiction badge

Dataset detail page:
  - Jurisdiction badge in header
  - Source link uses correct portal URL

Search:
  - Jurisdiction added as searchable/filterable field in Lunr index
  - Search data includes jurisdiction for display

Footer:
  - Update data source links to list all three portals
```

### CI Pipeline Changes

```yaml
# BEFORE
- name: Pull latest data
  run: mdc-encyclopedia pull

# AFTER
- name: Pull latest data
  run: mdc-encyclopedia pull --jurisdiction miami-dade broward city-of-miami
```

### Dedup Across Jurisdictions

The existing `detect_duplicate_titles` function operates within a single pull. With multi-jurisdiction support, the same dataset could appear on multiple portals (e.g., a County dataset re-published by a city). The dataset `id` is unique per portal (ArcGIS item ID), so there is no primary key collision. Cross-jurisdiction dedup is out of scope for v1.1 -- it can be a future enhancement if needed.

### Estimated Complexity: HIGH

Touches nearly every module. However, the changes within each module are modest (parameterizing what is currently hardcoded). The risk is in the breadth, not the depth.

---

## Component Boundary Map (v1.1)

```
CLI (cli.py)
  |
  +-- pull --jurisdiction X Y Z
  |     |
  |     +-- jurisdictions.py (NEW) -----------> jurisdiction registry lookup
  |     +-- hub_client.py (MODIFIED) ---------> parameterized base_url
  |     +-- normalizer.py (MODIFIED) ---------> jurisdiction-aware source_portal/source_url
  |     +-- field_fetcher.py (MODIFIED) ------> uses client with correct base_url
  |     +-- db.py (MODIFIED) -----------------> V3 schema, jurisdiction index
  |     +-- diff/detector.py (MODIFIED) ------> per-jurisdiction snapshots
  |
  +-- enrich (UNCHANGED)
  |
  +-- enrich-fields (NEW)
  |     +-- enrichment/field_prompts.py (NEW)
  |     +-- enrichment/field_models.py (NEW)
  |     +-- enrichment/client.py (MODIFIED)
  |     +-- db.py (MODIFIED) -----------------> update columns.ai_description
  |
  +-- audit (UNCHANGED - works on all datasets regardless of jurisdiction)
  |
  +-- diff (MODIFIED - per-jurisdiction filtering in display)
  |
  +-- export (MODIFIED)
  |     +-- site/generator.py (MODIFIED) -----> call feed + catalog_export
  |     +-- site/context.py (MODIFIED) -------> jurisdiction grouping
  |     +-- site/feed.py (NEW) ---------------> RSS/Atom XML generation
  |     +-- site/catalog_export.py (NEW) -----> JSON/CSV catalog export
  |     +-- site/search_index.py (MODIFIED) --> jurisdiction field in index
  |     +-- templates (MODIFIED) -------------> jurisdiction UI
  |
  +-- stats (MODIFIED - per-jurisdiction breakdown)
  +-- serve (UNCHANGED)
```

### New Files (6)

| File | Purpose | Lines (est) |
|------|---------|-------------|
| `jurisdictions.py` | Jurisdiction registry | ~30 |
| `site/feed.py` | RSS/Atom feed generation | ~80 |
| `site/catalog_export.py` | JSON/CSV catalog export | ~100 |
| `enrichment/field_prompts.py` | Field description prompt templates | ~60 |
| `enrichment/field_models.py` | Pydantic model for field enrichment | ~25 |
| templates (new/modified) | Jurisdiction UI elements | ~50 |

### Modified Files (13)

| File | Change Scope | Risk |
|------|-------------|------|
| `hub_client.py` | Parameterize `base_url` | LOW |
| `normalizer.py` | Accept jurisdiction slug, build correct URLs | LOW |
| `field_fetcher.py` | Accept client (already parameterized) | LOW |
| `db.py` | V3 migration, new queries, jurisdiction index | MEDIUM |
| `diff/detector.py` | Per-jurisdiction snapshot filtering | LOW |
| `cli.py` | New command + `--jurisdiction` flag | MEDIUM |
| `site/generator.py` | Call feed + catalog_export, jurisdiction subdirs | LOW |
| `site/context.py` | Jurisdiction grouping in site data | MEDIUM |
| `site/search_index.py` | Add jurisdiction to index fields | LOW |
| `base.html` | RSS link, jurisdiction in title/footer | LOW |
| `browse.html` | Jurisdiction filter dropdown | LOW |
| `dataset.html` | Jurisdiction badge, AI field descriptions | LOW |
| `encyclopedia.yml` | Multi-jurisdiction pull command | LOW |

---

## Database Schema V3

```sql
-- Migration from V2 to V3
-- Step 1: Add AI description column to columns table
ALTER TABLE columns ADD COLUMN ai_description TEXT;

-- Step 2: Create index on source_portal for jurisdiction filtering
CREATE INDEX IF NOT EXISTS idx_datasets_source_portal ON datasets(source_portal);

-- Step 3: Migrate existing data to use jurisdiction slug
UPDATE datasets SET source_portal = 'miami-dade' WHERE source_portal = 'arcgis_hub';
```

Implementation in `db.py`:
```python
CURRENT_SCHEMA_VERSION = 3

SCHEMA_V3_UPGRADE = """
ALTER TABLE columns ADD COLUMN ai_description TEXT;
CREATE INDEX IF NOT EXISTS idx_datasets_source_portal ON datasets(source_portal);
UPDATE datasets SET source_portal = 'miami-dade' WHERE source_portal = 'arcgis_hub';
"""
```

Full schema after V3:

| Table | Columns | Changes in V3 |
|-------|---------|---------------|
| `datasets` | id, source_portal, source_url, title, description, category, publisher, format, created_at, updated_at, row_count, tags, license, api_endpoint, bbox, download_url, metadata_json, pulled_at | `source_portal` repurposed (now stores jurisdiction slug), new index |
| `columns` | id, dataset_id, name, data_type, description, **ai_description** | **NEW: ai_description TEXT** |
| `enrichments` | (unchanged) | -- |
| `audit_scores` | (unchanged) | -- |
| `changes` | (unchanged) | -- |

---

## Suggested Build Order

Based on dependency analysis and risk:

### Phase 1: Multi-Jurisdiction Foundation (build first -- everything else depends on it)

1. **`jurisdictions.py`** -- jurisdiction registry (no dependencies)
2. **`db.py` V3 migration** -- schema changes needed before any data flows
3. **`hub_client.py`** -- parameterize `base_url` (backwards compatible)
4. **`normalizer.py`** -- jurisdiction-aware normalization
5. **`cli.py` pull --jurisdiction** -- wire up the new flow
6. **`diff/detector.py`** -- per-jurisdiction snapshots
7. **Test:** Pull from all 3 portals, verify data in DB with correct jurisdiction slugs

### Phase 2: RSS/Atom Feed (lowest risk, highest user visibility)

1. **`site/feed.py`** -- feed generation module
2. **`site/generator.py`** -- call feed generator during export
3. **Template updates** -- RSS link in head/nav
4. **`pyproject.toml`** -- add `feedgen` dependency
5. **Test:** Verify feed.xml and rss.xml validate, render in feed reader

### Phase 3: Enriched Catalog Export (low risk, no new deps)

1. **`site/catalog_export.py`** -- JSON + CSV export
2. **`site/generator.py`** -- call catalog export during export
3. **Template updates** -- download links on about/downloads page
4. **Test:** Verify JSON schema, CSV opens in Excel/Sheets

### Phase 4: Field-Level AI Descriptions (highest cost, most new code)

1. **`enrichment/field_prompts.py`** -- field enrichment prompt
2. **`enrichment/field_models.py`** -- Pydantic model
3. **`enrichment/client.py`** -- add `enrich_fields` function
4. **`cli.py` enrich-fields** -- new command with dry-run, cost estimation
5. **`site/context.py`** -- include `ai_description` in column data
6. **`dataset.html`** -- show AI descriptions in columns table
7. **Test:** Dry-run cost estimate, enrich 5 datasets, verify on site

### Phase 5: Site UI Polish (depends on all above)

1. **Jurisdiction filter** on browse page (JS + template)
2. **Homepage stats** per jurisdiction
3. **Search index** jurisdiction field
4. **CI pipeline** update for multi-jurisdiction
5. **Test:** Full end-to-end: pull all jurisdictions, enrich, audit, export, verify site

### Rationale for This Order

- **Multi-jurisdiction first** because the RSS feed and catalog export should include jurisdiction data from day one. Building them before multi-jurisdiction means reworking them later.
- **RSS before export** because RSS has an external dependency (feedgen) worth validating early.
- **Export before field AI** because export has zero risk and can ship independently.
- **Field AI last** because it has the highest complexity and cost, and the site works fine without it. It also benefits from having multi-jurisdiction data already in the DB (more B+ datasets from new jurisdictions could become eligible).

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Separate DBs Per Jurisdiction
**What:** Creating a separate SQLite database for each jurisdiction.
**Why bad:** Breaks unified catalog. Makes cross-jurisdiction queries impossible. Triples CI complexity.
**Instead:** Single DB with `source_portal` as jurisdiction discriminator. One `export` produces one site.

### Anti-Pattern 2: Feed Generation as a Separate CLI Command
**What:** `mdc-encyclopedia feed` as a standalone command.
**Why bad:** Feed is a site artifact. Separate command means CI must know to run it. Easy to forget. Feed falls out of sync with site.
**Instead:** Generate feed inside `export` command. Feed is always in sync with site content.

### Anti-Pattern 3: Per-Column API Calls for Field Descriptions
**What:** Calling Claude once per column to generate descriptions.
**Why bad:** 2,635 columns = 2,635 API calls. At 1 call/sec = 44 minutes. Rate limit risk. Cost overhead from repeated system prompts.
**Instead:** Batch all columns for a dataset into one API call. 125 calls total. ~2 minutes.

### Anti-Pattern 4: Async Rewrite for Multi-Portal
**What:** Converting to async httpx for concurrent pulls across portals.
**Why bad:** Over-engineering. Each portal has 1 req/s rate limit. Concurrent requests just hit rate limits faster. Complexity of async for no performance gain.
**Instead:** Sequential pulls per jurisdiction. 83 datasets at 1 req/s = ~2 minutes per new portal. Total pipeline remains under 15 minutes.

### Anti-Pattern 5: Dynamic Jurisdiction Filtering (JavaScript Only)
**What:** Loading all datasets and filtering client-side only.
**Why bad:** Works for 636 datasets, but browse page HTML will be large. More importantly, if a user wants "just Broward" they have to load everything.
**Instead:** Hybrid -- render all datasets with data-jurisdiction attributes, and use client-side JS filter for interactive use. Static pages are fine at 636 datasets since the browse page already renders all 470 Miami-Dade datasets today.

---

## Scalability Considerations

| Concern | Current (470 datasets) | v1.1 (~636 datasets) | At 2,000 datasets |
|---------|----------------------|---------------------|-------------------|
| DB size | 3.8 MB | ~5 MB | ~15 MB |
| Pull time | ~8 min | ~12 min (3 portals) | ~30 min |
| Export time | ~5 sec | ~8 sec | ~20 sec |
| Search index | ~200 KB | ~300 KB | ~1 MB |
| Site files | ~480 pages | ~650 pages | ~2100 pages |
| GitHub repo size | ~4 MB | ~6 MB | ~18 MB |
| Feed XML | N/A | ~20 KB | ~30 KB |
| Catalog JSON | N/A | ~500 KB | ~2 MB |
| Catalog CSV | N/A | ~200 KB | ~800 KB |

No scalability concerns at v1.1 scope. The architecture scales linearly. The committed-DB-to-repo pattern starts to feel heavy above ~50 MB, which would require ~3,000+ datasets with full metadata -- well beyond v1.1 scope.

---

## Sources

- Broward County GeoHub API: `https://geohub-bcgis.opendata.arcgis.com/api/search/v1/collections/dataset/items` -- verified live, 83 datasets, same OGC Records schema (HIGH confidence)
- City of Miami Open Data GIS API: `https://datahub-miamigis.opendata.arcgis.com/api/search/v1/collections/dataset/items` -- verified live, 83 datasets, same OGC Records schema (HIGH confidence)
- [python-feedgen 1.0.0](https://feedgen.kiesow.be/) -- stable, supports RSS 2.0 + Atom, file output (HIGH confidence)
- [feedgen on PyPI](https://pypi.org/project/feedgen/) -- v1.0.0 released 2023-12-25 (HIGH confidence)
- [ArcGIS Hub Search API definition](https://hub.arcgis.com/api/search/definition/) -- OGC API Records standard (HIGH confidence)
- Existing codebase analysis: all source files in `src/mdc_encyclopedia/` read and analyzed (HIGH confidence)
- DB query: 125 B+ datasets, 2,635 columns eligible for field descriptions (HIGH confidence)
