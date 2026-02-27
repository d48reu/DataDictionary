# Pitfalls Research

**Domain:** Adding RSS feeds, catalog exports, field-level AI enrichment, and multi-jurisdiction support to an existing open data encyclopedia
**Researched:** 2026-02-26
**Confidence:** HIGH (verified against codebase, live API responses, and official documentation)

## Critical Pitfalls

### Pitfall 1: Dataset ID Collision When Adding Multiple Jurisdictions to a Single-ID Primary Key

**What goes wrong:**
The current `datasets` table uses `id TEXT PRIMARY KEY` where the ID comes from the ArcGIS Hub feature ID (a hex UUID like `acd9791dc1fd49a8aaeaab261dd61b89`). These IDs are generated independently by each ArcGIS organization. While UUID collisions are astronomically unlikely, the real danger is different: if Miami-Dade, Broward County, and City of Miami share federated datasets (one organization publishes, another links), the same dataset ID could appear from two portals. An `INSERT OR REPLACE` on a collision silently overwrites one jurisdiction's data with another's, and you lose a dataset from your catalog without any error.

**Why it happens:**
The v1.0 schema was designed for a single portal. The `id` column is the sole primary key, and `source_portal` is just a metadata field with no role in uniqueness. When you add Broward (`geohub-bcgis.opendata.arcgis.com`) and City of Miami (`datahub-miamigis.opendata.arcgis.com`), the `upsert_dataset()` function uses `INSERT OR REPLACE` keyed on `id` alone. If two portals happen to serve the same ArcGIS item (federated content), the second pull overwrites the first.

**How to avoid:**
- Change the primary key to a composite key: either `(id, source_portal)` or create a synthetic key like `f"{source_portal}:{id}"`. The composite approach is cleaner because it preserves the original ID for API callbacks.
- This requires a schema migration (V2 to V3). Use the existing `PRAGMA user_version` pattern -- the codebase already demonstrates V1-to-V2 migration in `db.py`.
- Update ALL queries that reference `datasets.id` -- this includes `enrichments.dataset_id`, `columns.dataset_id`, `audit_scores.dataset_id`, `changes.dataset_id`, and every lookup in `context.py`, `detector.py`, and `cli.py`.
- Add a deduplication strategy: when the same ArcGIS item appears from two portals, keep both records (tagged by jurisdiction) but flag the relationship for display.

**Warning signs:**
- Dataset count after multi-portal pull is less than the sum of per-portal counts.
- Running `SELECT id, COUNT(*) FROM datasets GROUP BY id HAVING COUNT(*) > 1` returns rows after pulling from multiple portals.
- Enrichments or audit scores seem to "disappear" after a pull that includes a second jurisdiction.

**Phase to address:**
Phase 1 (Multi-jurisdiction DB schema). Must be the first thing implemented before any multi-portal pulling.

---

### Pitfall 2: Hardcoded Hub Base URL and Single-Portal Assumptions Throughout the Codebase

**What goes wrong:**
The current `hub_client.py` hardcodes `HUB_BASE_URL = "https://opendata.miamidade.gov"` as a module constant. The `normalizer.py` hardcodes `source_portal = "arcgis_hub"` and constructs `source_url` using the Miami-Dade domain: `f"https://opendata.miamidade.gov/datasets/{feature_id}"`. The CLI `pull` command creates a single client and pulls from one portal. Adding Broward and City of Miami requires changing at least 6 files, and a naive approach of duplicating `hub_client.py` per jurisdiction creates unmaintainable copy-paste code.

**Why it happens:**
v1.0 correctly scoped to a single jurisdiction. The simplification was appropriate then. But every layer -- from HTTP client creation to data normalization to URL construction to CLI commands -- bakes in the assumption of one portal. There is no "portal config" abstraction.

**How to avoid:**
- Create a `JurisdictionConfig` dataclass or dict with: `name`, `slug`, `hub_base_url`, `search_endpoint`, `portal_label`, `source_url_template`. Store these in a registry (Python dict or YAML config file).
- Refactor `create_client()` to accept a `base_url` parameter instead of using the module constant. Refactor `normalize_hub_dataset()` to accept a `jurisdiction` parameter that controls `source_portal` and `source_url` construction.
- Refactor the `pull` CLI command to accept `--jurisdiction` (default: all configured jurisdictions) and iterate over the registry.
- Keep the current behavior as the default (Miami-Dade only) so existing users see no change unless they opt in.

**Warning signs:**
- You find yourself copy-pasting `hub_client.py` to create `broward_client.py`.
- `source_url` links on Broward datasets point to `opendata.miamidade.gov` (wrong domain).
- The `source_portal` column shows `arcgis_hub` for all jurisdictions with no way to filter.

**Phase to address:**
Phase 1 (Multi-jurisdiction). Extract jurisdiction config before adding any new portals.

---

### Pitfall 3: City of Miami Has BOTH Socrata AND ArcGIS Portals

**What goes wrong:**
Research confirms City of Miami operates two separate open data portals:
1. `datahub-miamigis.opendata.arcgis.com` -- ArcGIS Hub (GIS-focused datasets)
2. `data.miamigov.com` -- Socrata platform (general open data)

If you only integrate the ArcGIS Hub portal, you miss the Socrata datasets entirely. If you integrate both, you face cross-platform deduplication (the same dataset might exist on both portals with different IDs, different metadata, and different update timestamps). The v1.0 architecture was built specifically to avoid Socrata after research confirmed Miami-Dade County has no active Socrata presence. Adding City of Miami re-introduces the Socrata complexity that was intentionally excluded.

**Why it happens:**
The v1.0 project correctly scoped to ArcGIS Hub only because Miami-Dade County uses only ArcGIS. But City of Miami is a different government entity with its own infrastructure decisions. Assuming "all South Florida jurisdictions use ArcGIS Hub" is wrong.

**How to avoid:**
- For v1.1, scope City of Miami to ArcGIS Hub only (`datahub-miamigis.opendata.arcgis.com`). This keeps the single-API-client architecture intact. Document that City of Miami Socrata datasets are excluded with a note about why.
- If Socrata support is needed later, treat it as a v1.2 or v2.0 feature requiring a `SocrataClient` abstraction, separate normalization pipeline, and cross-platform deduplication.
- Verify at development time how many datasets each City of Miami portal has. If the ArcGIS Hub has 80%+ coverage, the Socrata exclusion is acceptable.

**Warning signs:**
- Stakeholders ask "Where is dataset X?" and it only exists on `data.miamigov.com`.
- City of Miami ArcGIS Hub has significantly fewer datasets than their Socrata portal.
- You start building a Socrata client "just for City of Miami" and it grows into a full parallel pipeline.

**Phase to address:**
Phase 1 (Multi-jurisdiction scoping). Make the decision explicitly and document it in the jurisdiction config before writing code.

---

### Pitfall 4: RSS Feed with Relative URLs Breaks Every Feed Reader

**What goes wrong:**
The existing site uses `base_url` (e.g., `/DataDictionary`) for all internal links. If you generate the RSS/Atom feed using the same relative URL pattern, feed readers (Feedly, NewsBlur, Thunderbird, etc.) will try to resolve `/DataDictionary/dataset/some-slug/` relative to the feed URL, producing broken links like `https://feedly.com/DataDictionary/dataset/some-slug/`. RSS and Atom specifications require absolute URLs in `<link>` and `<guid>` elements.

**Why it happens:**
The Jinja2 templates use `{{ base_url }}/dataset/{{ ds.slug }}/` which produces a relative path. Developers reuse the same URL construction pattern for the RSS feed without realizing that feeds have stricter URL requirements than HTML pages (browsers resolve relative URLs, feed readers often do not).

**How to avoid:**
- Define a `site_url` (the full canonical URL, e.g., `https://username.github.io/DataDictionary`) separate from `base_url` (the path prefix). Use `site_url` exclusively in RSS/Atom feed generation.
- Use the `python-feedgen` library rather than hand-crafting XML. feedgen enforces absolute URLs for Atom `<link href="">` elements (href is mandatory and must be absolute).
- Add a `--site-url` parameter to the `export` CLI command. The RSS feed should fail to generate if no site URL is provided, rather than silently producing broken links.
- Validate the generated feed XML against the W3C Feed Validation Service during development.

**Warning signs:**
- Feed reader shows dataset titles but clicking links goes nowhere or to the wrong domain.
- Running the feed through `https://validator.w3.org/feed/` returns errors about relative URLs.
- `<link>` elements in the feed XML start with `/` instead of `https://`.

**Phase to address:**
Phase 2 (RSS Feed generation). Must be correct from the first implementation.

---

### Pitfall 5: RSS Feed Date Format Wrong (ISO 8601 vs RFC 822)

**What goes wrong:**
The existing codebase stores all timestamps in ISO 8601 format (e.g., `2026-02-26T12:00:00+00:00`). RSS 2.0 requires dates in RFC 822 format (e.g., `Wed, 26 Feb 2026 12:00:00 +0000`). If you pass ISO 8601 dates directly into RSS `<pubDate>` elements, some feed readers will silently ignore the dates (showing "Unknown date"), while others will parse them incorrectly or show January 1, 1970.

**Why it happens:**
ISO 8601 is the sensible default for programming -- it is what the ArcGIS API returns, what Python `datetime.isoformat()` produces, and what SQLite stores. Developers naturally use the same format everywhere. But RSS 2.0 predates widespread ISO 8601 adoption and mandates RFC 822. Atom feeds, by contrast, do use ISO 8601, which adds to the confusion.

**How to avoid:**
- Use `python-feedgen` which handles date format conversion internally. Pass Python `datetime` objects and let feedgen serialize them correctly for each format.
- If generating both RSS and Atom, test both outputs separately. An Atom feed with ISO 8601 dates and an RSS feed with RFC 822 dates from the same source data.
- Parse the `detected_at` timestamps from the `changes` table back into `datetime` objects before passing to feedgen, rather than passing string timestamps.

**Warning signs:**
- Feed reader shows all items with the same date or no date.
- W3C Feed Validator reports "pubDate is not an RFC 822 date."
- Atom feed works perfectly but RSS feed dates are garbled.

**Phase to address:**
Phase 2 (RSS Feed generation). Use feedgen to avoid manual date formatting entirely.

---

### Pitfall 6: Field-Level AI Enrichment Cost Explosion on B+ Datasets

**What goes wrong:**
The v1.1 plan enriches field-level (column) descriptions for B+ quality datasets. The current `columns` table shows that many datasets have 20-60+ columns. A single field-enrichment prompt that includes the dataset context plus all columns could consume 2,000-5,000 tokens. If 200 datasets are B+ grade (plausible -- the current audit shows strong grade distribution), that is 400K-1M input tokens plus output tokens for 200 x 30 column descriptions. At Haiku pricing, that is $3-8 per batch. At Sonnet pricing, $15-40. And unlike dataset-level enrichment (which produces ~6 fields), field-level enrichment produces N descriptions per dataset, making output tokens proportional to column count.

**Why it happens:**
Dataset-level enrichment has a fixed output size (~500 tokens per dataset). Field-level enrichment output scales with the number of columns. A dataset with 60 columns needs 60 individual descriptions (each 1-2 sentences = 20-40 tokens), totaling 1,200-2,400 output tokens -- 2-5x more than dataset-level enrichment. Developers estimate costs based on dataset-level experience and are surprised.

**How to avoid:**
- Extend the existing `estimate_cost()` function to support field-level enrichment estimation separately. Show dataset-level and field-level costs as line items.
- Cap columns per enrichment call at 30 (the existing `build_dataset_prompt` already truncates at 30 columns for display, so apply the same cap for enrichment). For datasets with 30+ columns, batch into multiple calls.
- Store field enrichments in a new table (`column_enrichments`) or add an `ai_description` column to the existing `columns` table. Track which columns are already enriched for resume safety.
- Start with the top 20 B+ datasets by column count, review quality, then proceed with the rest. Field-level enrichment quality is harder to validate than dataset-level.

**Warning signs:**
- `--dry-run` for field enrichment shows costs 3-5x higher than expected based on dataset-level enrichment.
- Enrichment runs take significantly longer per dataset than before.
- Output token usage spikes without corresponding increase in datasets enriched.

**Phase to address:**
Phase 3 (Field-level enrichment). Must have cost estimation before first batch run.

---

### Pitfall 7: Field-Level AI Descriptions Hallucinate Column Semantics

**What goes wrong:**
LLMs can generate plausible but wrong descriptions for ambiguous column names. A column named `FLD_ZONE` in a Miami-Dade dataset could mean "Flood Zone" or "Field Zone" depending on context. A column named `STATUS` could mean permit status, equipment status, or inspection status. The AI generates a confident-sounding description that is factually wrong, and because it is displayed on the public encyclopedia site, it misleads residents and journalists.

**Why it happens:**
Column names in government datasets are often abbreviated, context-dependent, or use internal jargon. Unlike dataset-level enrichment (where the title and description provide strong context), column-level enrichment often has only the column name, data type, and an alias that may be equally cryptic. Research from academic studies confirms that adding more context does not always improve LLM accuracy for column classification tasks.

**How to avoid:**
- Include the dataset title, description, category, and AI-generated dataset description in the field enrichment prompt. The more context about what the dataset IS, the better the column descriptions.
- Include sample values if available (the ArcGIS REST API `query?where=1=1&outFields=*&resultRecordCount=5` endpoint can provide sample rows). Even 3-5 sample values dramatically improve column description accuracy.
- Add a visible disclaimer on the site: "Column descriptions are AI-generated and may contain errors. Verify with the source portal."
- Mark AI-generated column descriptions visually differently from portal-provided descriptions (the `columns.description` field already contains ArcGIS alias data -- do not overwrite it, add a separate `ai_description` field).
- Implement a confidence signal: if the column name is a common English word (e.g., "status", "name", "type"), flag the description as LOW confidence.

**Warning signs:**
- Column descriptions use generic language like "This field contains status information" without specifics.
- Multiple columns across different datasets get identical descriptions.
- Descriptions contradict the dataset's own description (e.g., describing a "flood zone" column in a "Parks and Recreation" dataset).

**Phase to address:**
Phase 3 (Field-level enrichment). Build the prompt with maximum context and add disclaimers before generating any descriptions.

---

### Pitfall 8: Schema Migration Breaks Existing Enrichments and Audit Scores

**What goes wrong:**
Adding multi-jurisdiction support requires changing the primary key of `datasets` from `id` to `(id, source_portal)` or a composite key. This cascading change affects all foreign key references: `enrichments.dataset_id`, `columns.dataset_id`, `audit_scores.dataset_id`, `changes.dataset_id`. If the migration is done incorrectly, existing enrichment and audit data is orphaned or lost. The V1-to-V2 migration pattern in the codebase uses `CREATE TABLE new; INSERT INTO new FROM old; DROP old; ALTER RENAME new`, which works but requires careful foreign key handling.

**Why it happens:**
SQLite does not support `ALTER TABLE ... ALTER COLUMN` or `ALTER TABLE ... ADD CONSTRAINT`. Changing a primary key requires recreating the table. If foreign keys are enabled (`PRAGMA foreign_keys=ON`, which this codebase uses), dropping or recreating the parent table while child tables reference it will fail or cascade-delete child rows.

**How to avoid:**
- Disable foreign keys during migration: `PRAGMA foreign_keys=OFF` at the start, re-enable after. The existing `init_db()` function enables foreign keys on every connection but does not disable them for migrations.
- Migrate in a specific order: create new parent table, migrate parent data, create new child tables, migrate child data, drop old tables, rename new tables. Never drop the parent table while child tables still reference it.
- For the ID change: if switching to composite key `(id, source_portal)`, update all child table `dataset_id` columns to store the composite value. If using a synthetic key, add a mapping table.
- The simplest approach: keep `id` as primary key but make it a synthetic composite like `"{source_portal}:{original_id}"`. This avoids multi-column foreign keys (which SQLite supports but makes queries verbose). All existing Miami-Dade data gets IDs prefixed with `arcgis_hub_mdc:`.
- Test the migration on a copy of the production database (`mdc_encyclopedia.db` is committed to the repo, so you have a real dataset to test against).

**Warning signs:**
- After migration, `SELECT COUNT(*) FROM enrichments` returns 0.
- `PRAGMA foreign_key_check` returns violations after migration.
- The site shows datasets with no enrichments or audit scores that previously had them.

**Phase to address:**
Phase 1 (Multi-jurisdiction DB schema). Migration must be tested against the real production database before merging.

---

### Pitfall 9: RSS Feed Grows Unboundedly and Becomes Useless

**What goes wrong:**
The `changes` table accumulates every change ever detected. If the RSS feed includes all historical changes, it grows indefinitely. After a year of weekly pulls, you could have hundreds or thousands of change entries in the feed. Feed readers typically show 20-50 items; a feed with 1,000 items wastes bandwidth and provides no value. Worse, if the feed file grows to hundreds of KB, it slows page loads for the site (even if no one subscribes to the feed, crawlers still fetch it).

**Why it happens:**
The `get_recent_changes()` function in `db.py` accepts a `limit` parameter but defaults to None (all changes). Developers wire this directly into the feed generator without adding a limit, because "more data is better." RSS best practice is 15-25 items maximum.

**How to avoid:**
- Limit the RSS feed to the most recent 25 change entries (or the most recent 2-3 pull batches). Use the existing `detected_at` grouping to include complete batches rather than cutting mid-batch.
- Add a permanent link to the full change history page (`/changes/`) from within the feed description, so users who want the full history can access it on the website.
- Set `<ttl>10080</ttl>` (7 days in minutes) in the RSS feed to match the weekly pull schedule. This tells feed readers not to poll more frequently than weekly.
- Consider generating the feed only for the most recent pull batch (what changed this week), not a cumulative history.

**Warning signs:**
- Feed XML file exceeds 50KB.
- Feed reader shows hundreds of items with no way to distinguish recent from old.
- GitHub Pages build time increases because the feed file is regenerated from scratch with growing data.

**Phase to address:**
Phase 2 (RSS Feed generation). Set the limit in the initial implementation, not as a later optimization.

---

### Pitfall 10: Enriched Catalog Export (JSON/CSV) Drifts Out of Sync with Site

**What goes wrong:**
The v1.1 plan adds downloadable JSON and CSV exports of the enriched catalog. If these files are generated at a different point in the pipeline than the HTML site, they can contain different data. For example: the export runs before enrichment completes (missing AI descriptions), or the export runs before audit scores are calculated (missing quality grades), or the export includes datasets that the site filters out. Users download a CSV expecting it to match what they see on the site, and it does not.

**Why it happens:**
The export is treated as a separate CLI command or a separate step in the pipeline. The `generate_site()` function in `generator.py` already reads all data from the DB and renders HTML. Adding a JSON/CSV export as a separate function that independently queries the DB creates a race condition in CI: if the pipeline is `pull -> enrich -> audit -> export_catalog -> export_site`, and enrichment or audit partially fails, the catalog export and site export see different DB states.

**How to avoid:**
- Generate the JSON/CSV export inside the existing `generate_site()` function, using the same `site_data` dict that drives the HTML pages. This guarantees the export and the site see identical data.
- Write the JSON/CSV files to the same `site/` output directory so they are deployed together with the HTML.
- Include a `generated_at` timestamp in the export files that matches the site's `generated_at`. Users can verify synchronization.
- Add the export file URLs to the site navigation (e.g., a "Download" section on the About page) so users know where to find them.

**Warning signs:**
- JSON export has a different dataset count than the site homepage shows.
- CSV export is missing AI descriptions that appear on the site.
- Export timestamp does not match site generation timestamp.

**Phase to address:**
Phase 2 (Catalog export). Generate exports alongside the site, not as a separate pipeline step.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Prefixing existing IDs with jurisdiction slug (`arcgis_hub_mdc:abc123`) instead of composite primary key | Avoids multi-column foreign keys, simpler queries | Parsing the prefix to extract original ID is fragile; downstream code needs to handle both old and new ID formats during migration | Acceptable for v1.1 -- synthetic key is simpler than composite PK for SQLite |
| Generating RSS by hand-crafting XML strings instead of using feedgen | No new dependency | Easy to produce invalid XML, miss required elements, or get date formats wrong; feedgen handles all RSS/Atom spec compliance | Never -- feedgen is 1 dependency vs. hours of debugging XML |
| Adding `ai_description` to the existing `columns` table instead of a new `column_enrichments` table | Simpler schema, one table to query | Cannot track enrichment metadata (prompt version, model, timestamp, cost) per column description; makes selective re-enrichment harder | Acceptable for v1.1 if you add `ai_description_version` and `ai_description_at` columns alongside |
| Hardcoding jurisdiction list in Python code instead of a config file | Faster implementation | Adding a new jurisdiction requires code changes instead of config changes; harder for non-developers to contribute | Acceptable for v1.1 with 3 jurisdictions -- extract to config before v1.2 |
| Skipping feed validation in CI | Faster pipeline | Broken feeds ship to production undetected; feed reader subscribers see errors silently | Never -- add a simple `xmllint --noout feed.xml` step to the GitHub Actions pipeline |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Broward County ArcGIS Hub (`geohub-bcgis.opendata.arcgis.com`) | Assuming the Search API endpoint path is identical to Miami-Dade's | Verified: both use `/api/search/v1/collections/dataset/items` with the same response format. But verify `numberMatched` and pagination behavior independently for each portal -- different ArcGIS Hub versions may paginate differently. |
| City of Miami ArcGIS Hub (`datahub-miamigis.opendata.arcgis.com`) | Assuming this covers all City of Miami open data | City of Miami ALSO operates `data.miamigov.com` (Socrata). The ArcGIS Hub contains GIS-specific datasets only. Document this gap explicitly. |
| python-feedgen | Passing string dates instead of `datetime` objects | feedgen expects Python `datetime` objects. Passing ISO 8601 strings will either error or produce wrong output. Parse `detected_at` from SQLite into `datetime` objects before passing to feedgen. |
| python-feedgen | Omitting the feed `id` (Atom) or `link` (RSS) | Atom feeds require a unique `id` (typically the feed URL). RSS feeds require a `link` element. feedgen will produce invalid XML if these are missing. Set `feed.id(site_url + '/feed.xml')` and `feed.link(href=site_url)`. |
| CSV export | Using Python's `csv.writer` without UTF-8 BOM | Excel on Windows will not recognize UTF-8 encoding without a BOM (byte order mark). Dataset descriptions contain accented characters (Miami-Dade has Spanish-language dataset names). Write the BOM (`\ufeff`) as the first character of the CSV file. |
| JSON export | Serializing SQLite Row objects directly | `sqlite3.Row` objects are not JSON-serializable. The existing codebase converts to dicts via `dict(row)`, but if you add new fields that contain `datetime` objects or `set` types, `json.dumps()` will crash. Use a custom JSON encoder or serialize all fields explicitly. |
| GitHub Pages | Serving `.xml` files with wrong Content-Type | GitHub Pages serves `.xml` files as `application/xml`, which is acceptable for RSS. But some feed readers prefer `application/rss+xml`. You cannot control Content-Type on GitHub Pages. This is a non-issue in practice but worth knowing. |
| Slug generation across jurisdictions | Two jurisdictions having datasets with the same title producing the same slug | The existing slug collision detection in `context.py` appends the first 8 chars of the dataset ID. With multi-jurisdiction, also append the jurisdiction slug to disambiguate: `/dataset/{jurisdiction}/{slug}/`. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Pulling all jurisdictions sequentially in a single CLI invocation | `pull` command takes 3x as long (3 portals x 570+ datasets x 1 req/sec rate limit = 30+ minutes for catalog + fields) | Pull jurisdictions in parallel (separate threads or async) since rate limits are per-portal, not global. Or accept the longer pull time for weekly CI. | Adding 3rd+ jurisdiction |
| Field-level enrichment on all B+ datasets in one batch | Enrichment run takes 2+ hours and costs $10+; API rate limits kick in; partial failures leave inconsistent state | Batch field enrichment: enrich 20 datasets per CI run. Track progress in DB. Resume across runs. | 100+ B+ datasets |
| RSS feed regenerated from full change history query | Feed generation scans entire `changes` table (unbounded growth) even though only 25 items appear in feed | Add `LIMIT` and `ORDER BY detected_at DESC` to the feed query. Index `changes.detected_at` if not already indexed. | 1,000+ change records after 6+ months |
| JSON/CSV export includes all enrichment and audit data per dataset | Export file grows to multi-MB for 1,500+ datasets across 3 jurisdictions | Offer two export levels: "compact" (core metadata only) and "full" (with enrichments). Compress with gzip for download. | 1,000+ datasets with full enrichment |
| Search index includes datasets from all jurisdictions without filtering | Index grows 3x; search results mix jurisdictions confusingly | Add jurisdiction as a searchable/filterable field in the index. Consider jurisdiction-scoped search or a jurisdiction filter toggle. | 1,500+ total datasets |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Including `ANTHROPIC_API_KEY` in exported JSON/CSV catalog | API key leaked in public downloadable file | The export should only include enrichment results, never the API key or any processing metadata. Review export fields explicitly. |
| RSS feed entries containing unescaped HTML from AI descriptions | Feed readers may execute embedded HTML/JS; XSS via feed injection | Use feedgen's content methods which handle CDATA wrapping automatically. Never insert raw AI text into XML elements without escaping. |
| Column AI descriptions exposing PII from sample data | If sample values are used for enrichment context, the AI might echo back PII (names, addresses, SSNs) in the description | Never include sample values from columns that contain names, addresses, or ID numbers. Filter columns by type: only include sample values for coded/categorical columns, not free-text or PII-risk columns. |
| Multi-jurisdiction pull credentials stored per-portal | If each portal requires different auth, multiple secrets in `.env` increases exposure surface | ArcGIS Hub public APIs do not require authentication for public datasets. Do not add credentials unless a specific portal requires them. Verify each new jurisdiction is publicly accessible before adding auth infrastructure. |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| RSS feed shows only dataset IDs, not human-readable descriptions | Subscribers see "Dataset abc123 added" with no context | Include dataset title, AI description (first sentence), and a direct link to the dataset page in each feed entry. |
| Mixing jurisdictions in browse/search without clear labels | User searches for "parks" and sees Miami-Dade Parks, Broward Parks, and City of Miami Parks intermixed without knowing which is which | Add jurisdiction badges/chips on every dataset card. Add a jurisdiction filter dropdown to browse and search pages. |
| Column descriptions look identical to portal-provided descriptions | User cannot tell which descriptions are AI-generated vs. official | Visually distinguish AI-generated column descriptions (e.g., italic text, a small "AI" badge). Keep portal-provided aliases in a separate row. |
| Download links (JSON/CSV) are hidden or require hunting | Power users who want the export cannot find it | Add prominent download buttons on the About page and homepage. Include format and file size in the link text. |
| RSS feed has no human-readable landing page | User navigates to `/feed.xml` in a browser and sees raw XML | Add an XSL stylesheet to the RSS feed that renders a human-readable page in browsers. Or redirect browsers to `/changes/` and serve XML only to feed readers (complex -- simpler to just add the stylesheet). |

## "Looks Done But Isn't" Checklist

- [ ] **Multi-jurisdiction pull:** Pull from all 3 portals, then verify dataset count equals the sum of individual portal counts (minus any confirmed duplicates). Check `source_portal` column has distinct values per jurisdiction.
- [ ] **Feed validation:** Run the generated `feed.xml` through `https://validator.w3.org/feed/`. Zero errors, zero warnings. Test in at least 2 feed readers (Feedly + a desktop client like Thunderbird).
- [ ] **Feed link resolution:** Click every link in the RSS feed from within a feed reader. All links must resolve to the correct dataset page on the live site, not a 404 or wrong domain.
- [ ] **Export-site consistency:** Download the JSON export, count datasets, compare to the site homepage count. They must match. Check that every dataset in the JSON has enrichment data if the site shows enrichment data.
- [ ] **CSV encoding:** Open the exported CSV in Excel on Windows (not just Python or a text editor). Verify accented characters display correctly. Verify column headers are correct.
- [ ] **Field enrichment resume:** Start field enrichment, kill it after 5 datasets, restart. Verify it resumes without re-enriching completed columns or skipping the interrupted dataset.
- [ ] **Schema migration on real DB:** Run the V3 migration on a copy of the committed `mdc_encyclopedia.db`. Verify enrichment count, audit score count, and change count are identical before and after migration. Run `PRAGMA foreign_key_check` -- zero violations.
- [ ] **Jurisdiction filter on site:** Select "Broward County" filter. Verify only Broward datasets appear. Verify search results respect the filter. Verify category counts update.
- [ ] **Slug uniqueness across jurisdictions:** Find two datasets with similar titles from different jurisdictions. Verify they get distinct slugs and distinct URLs.
- [ ] **Feed TTL and freshness:** Verify the feed includes `<ttl>` (RSS) or `<updated>` (Atom) that matches the weekly pull schedule. Verify the feed timestamp updates on each site rebuild.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Dataset ID collision across jurisdictions | MEDIUM | Export all enrichments and audit scores to JSON. Drop and recreate tables with new schema. Re-import data with jurisdiction-prefixed IDs. Re-import enrichments with updated IDs. |
| RSS feed with broken relative URLs | LOW | Fix the URL construction in the feed generator. Rebuild feed. Redeploy. Feed readers will pick up corrected links on next poll. |
| Field enrichment hallucinated descriptions | LOW per dataset | Add a `--re-enrich-columns` flag to target specific datasets. Update the prompt with better context. Re-enrich affected datasets. Cost: proportional to number of corrections. |
| Schema migration lost enrichments | HIGH | If you have a backup of the pre-migration DB (the committed `mdc_encyclopedia.db`), restore it and re-run the migration correctly. If no backup exists, re-enrich all datasets ($5-25 depending on model). This is why you test migration on a copy first. |
| Export JSON/CSV out of sync with site | LOW | Move export generation into `generate_site()` using the same `site_data` dict. Rebuild and redeploy. |
| City of Miami Socrata datasets missing | MEDIUM | Document the gap. If coverage is needed, build a `SocrataClient` in a future milestone. The architecture supports it via the jurisdiction config abstraction. |
| Feed grows too large | LOW | Add `LIMIT 25` to the feed query. Rebuild feed. Old entries naturally age out of feed reader caches. |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Dataset ID collision (multi-jurisdiction) | Phase 1: Multi-jurisdiction DB schema | Composite key or synthetic key in place; `PRAGMA foreign_key_check` passes; no data loss on migration |
| Hardcoded portal URLs | Phase 1: Multi-jurisdiction client refactor | `JurisdictionConfig` registry exists; `pull --jurisdiction broward` works; no Miami-Dade URLs in Broward output |
| City of Miami Socrata gap | Phase 1: Multi-jurisdiction scoping | Decision documented in config; ArcGIS-only scope explicit; dataset count compared against Socrata portal |
| RSS relative URLs | Phase 2: RSS feed generation | All feed `<link>` elements are absolute URLs; W3C validator passes |
| RSS date format | Phase 2: RSS feed generation | feedgen handles dates; RSS pubDate is RFC 822; Atom updated is ISO 8601 |
| RSS unbounded growth | Phase 2: RSS feed generation | Feed contains max 25 items; feed file under 50KB |
| Export-site sync | Phase 2: Catalog export | JSON/CSV generated inside `generate_site()`; timestamps match |
| Field enrichment cost | Phase 3: Field-level enrichment | `--dry-run` shows field-level cost separately; cost under budget before batch run |
| Field enrichment hallucination | Phase 3: Field-level enrichment | Prompt includes dataset context; disclaimers on site; no PII in descriptions |
| Schema migration data loss | Phase 1: Multi-jurisdiction DB schema | Migration tested on copy of production DB; enrichment/audit counts unchanged |
| Search index bloat (3x jurisdictions) | Phase 4: Site generation updates | Index under 1MB with all jurisdictions; jurisdiction filter works |
| Slug collision across jurisdictions | Phase 4: Site generation updates | URL scheme includes jurisdiction; no 404s for same-titled datasets from different portals |

## Sources

- Broward County GeoHub portal verified: [geohub-bcgis.opendata.arcgis.com](https://geohub-bcgis.opendata.arcgis.com/) (HIGH confidence -- live API response verified)
- City of Miami ArcGIS Hub portal verified: [datahub-miamigis.opendata.arcgis.com](https://datahub-miamigis.opendata.arcgis.com/) (HIGH confidence -- live API response verified)
- City of Miami Socrata portal confirmed active: [data.miamigov.com](https://data.miamigov.com/) (HIGH confidence -- browsable public site)
- ArcGIS Hub Search API format consistency: verified via live `?limit=1` requests to all 3 portals (HIGH confidence)
- RSS/Atom feed validation requirements: [W3C Feed Validation Service](https://validator.w3.org/feed/) (HIGH confidence -- official W3C)
- RSS feed common errors: [RSS Validator - Common Errors](https://rssvalidator.app/rss-feed-errors) (MEDIUM confidence -- practical reference)
- RSS content type requirements: [W3C Feed Docs - Content Type](https://validator.w3.org/feed/docs/warning/UnexpectedContentType.html) (HIGH confidence -- official W3C)
- python-feedgen library: [feedgen documentation](https://feedgen.kiesow.be/) and [GitHub](https://github.com/lkiesow/python-feedgen) (HIGH confidence -- official docs)
- LLM field enrichment hallucination risks: [arXiv - Using LLMs to Enrich Documentation](https://arxiv.org/html/2404.15320v1) (MEDIUM confidence -- peer-reviewed)
- LLM column classification accuracy: [arXiv - Zero-Shot Topic Classification of Column Headers](https://arxiv.org/abs/2403.00884) (MEDIUM confidence -- peer-reviewed)
- AI data dictionary generation: [Generative AI and Data Dictionary Descriptions](https://medium.com/@fedenolasco/generative-ai-and-data-dictionary-descriptions-a2ba8c832afb) (LOW confidence -- single practitioner report)
- ArcGIS Hub catalog federation: [Esri - Hub Catalog Feeds](https://www.esri.com/arcgis-blog/products/arcgis-hub/data-management/arcgis-hub-catalog-feeds-support-dcat-rss-ogc) (HIGH confidence -- official Esri)
- ArcGIS UUID global uniqueness: [Esri - Global IDs](https://support.esri.com/en-us/gis-dictionary/globalid) (HIGH confidence -- official Esri)
- Existing codebase analysis: `db.py`, `hub_client.py`, `normalizer.py`, `generator.py`, `context.py`, `detector.py`, `cli.py`, `enrichment/client.py` (HIGH confidence -- direct code review)

---
*Pitfalls research for: Miami-Dade County Open Data Encyclopedia v1.1 features*
*Researched: 2026-02-26*
