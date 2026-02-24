# Pitfalls Research

**Domain:** Open data catalog/encyclopedia (Socrata + ArcGIS Hub APIs, AI enrichment, static site generation, SQLite storage)
**Researched:** 2026-02-24
**Confidence:** HIGH (verified against official docs and community reports)

## Critical Pitfalls

### Pitfall 1: Socrata Discovery API Returns Fewer Datasets Than Exist

**What goes wrong:**
The Socrata Discovery API (`/api/catalog/v1`) silently filters out certain asset types (charts, filtered views, maps, stories, calendars) unless you explicitly request them. The browser-facing catalog shows all assets, but the API defaults to a narrower set. For Austin, TX, one developer reported the browser showing 3,686 results while the API returned only 2,289. You will think your pull is complete when it is missing potentially hundreds of datasets.

**Why it happens:**
The Discovery API's `only` parameter defaults to `dataset` type. Other asset types (maps, charts, filtered views, data lenses, stories) are excluded unless you pass `only=datasets,maps,charts,filters,datalenses` or omit the filter entirely. The API documentation does not make this default obvious.

**How to avoid:**
- On your first pull, make two requests: one with no `only` filter and one with `only=dataset`. Compare `resultSetSize` values. Log the difference.
- Decide explicitly which asset types to include in the encyclopedia. Document the decision in config, not buried in code.
- Store the `resultSetSize` from the API response header and compare it to the count of records actually paginated through. Assert they match.

**Warning signs:**
- `resultSetSize` in the API response does not match the count displayed on `opendata.miamidade.gov` browsing interface.
- You find references to datasets in column metadata cross-links that don't exist in your local DB.

**Phase to address:**
Phase 1 (Data Ingestion). Must be resolved before any downstream enrichment or site generation.

---

### Pitfall 2: SODA3 Migration Breaking Existing Socrata Integrations

**What goes wrong:**
Socrata is actively deploying SODA3 (as of October 2025, the platform defaults to SODA3). SODA3 changes API endpoints from `/resource/IDENTIFIER.json` to `/api/v3/IDENTIFIER/query.json` and requires a valid application token for query requests, preferably via POST instead of URL query parameters. Code written against SODA2 endpoints today may break without warning as Miami-Dade's portal transitions.

**Why it happens:**
Socrata states SODA2.1 is "still fully supported" but the platform default has changed. New datasets may only expose SODA3 endpoints. Developers build against current docs without accounting for the migration timeline.

**How to avoid:**
- Register a Socrata app token immediately. SODA3 requires it; SODA2 strongly recommends it. Without a token, you get aggressively throttled (and SODA3 will reject you).
- Isolate all Socrata API calls behind a thin client abstraction (`SocrataClient` class). When SODA3 becomes mandatory, you change one module, not every call site.
- For the Discovery API (catalog metadata), verify which version Miami-Dade is currently serving. The Discovery API endpoint may differ from the per-dataset SODA endpoints.
- Pin your code to specific endpoint patterns and add integration tests that hit the live API with a known dataset ID to detect breakage early.

**Warning signs:**
- HTTP 401 or 403 errors on previously working endpoints.
- New datasets on the portal not appearing via your existing API calls.
- Socrata's developer docs referencing SODA3 URLs exclusively.

**Phase to address:**
Phase 1 (Data Ingestion). Build the abstraction layer from day one.

---

### Pitfall 3: AI Enrichment Cost Blowout on Full Catalog Run

**What goes wrong:**
Running Claude enrichment across hundreds or thousands of datasets without cost controls leads to unexpectedly large API bills. A single enrichment prompt with dataset metadata, column descriptions, and all the requested outputs (plain-English description, use cases, department, frequency, keywords, civic relevance) can easily consume 1,000-2,000+ tokens per dataset. At scale (say 800 datasets), that is 800K-1.6M tokens in one run -- potentially $10-25+ depending on model tier. Re-running enrichment unnecessarily (e.g., because of a bug in storage or a schema change that wipes enrichments) multiplies this.

**Why it happens:**
Developers test with 5-10 datasets, see low costs, then run the full catalog without doing the math. Or a bug causes enrichments to not persist correctly, so the "resume" logic re-enriches everything. Or the prompt is over-engineered with verbose system instructions that inflate token counts on every call.

**How to avoid:**
- Implement `--dry-run` and `--cost-estimate` before any enrichment run. Calculate: (number of unenriched datasets) x (avg tokens per prompt + avg tokens per response) x (price per token). Display this to the user and require confirmation.
- Store enrichment results with a content hash of the input metadata. Only re-enrich when the input metadata actually changed, not just because the enrichment schema changed.
- Set a hard budget cap in the CLI: `--max-cost 5.00` that aborts after spending exceeds the threshold.
- Use `--resume` backed by a persistent "enrichment status" column in SQLite (pending/complete/failed/skipped). Never re-enrich a "complete" record unless `--force` is passed.
- Log every API call's token usage to a separate audit table for post-run analysis.

**Warning signs:**
- No `--dry-run` flag exists when you start enrichment work.
- Enrichment runs take suspiciously long but you haven't checked how many datasets are being processed.
- Token usage audit table is empty or not implemented.

**Phase to address:**
Phase 2 (AI Enrichment). Cost controls must ship before the first full-catalog enrichment run.

---

### Pitfall 4: Client-Side Search Index Too Large for Browser

**What goes wrong:**
Lunr.js and Fuse.js build in-memory search indexes in the browser. For a catalog of 500-2,000 datasets with AI-generated descriptions, column names, keywords, and use cases, the serialized JSON search index can grow to several megabytes. Lunr.js works well up to about 2,000 large documents but the pre-built index JSON can be 2-5MB+. Fuse.js performs poorly on large datasets (10+ second search times reported on semi-long queries). Mobile devices with limited memory may crash or freeze when loading a multi-megabyte index.

**Why it happens:**
Developers index everything (full descriptions, all column names, all keywords, all use cases) into the search index without considering what actually needs to be searchable. The index file grows linearly with indexed content.

**How to avoid:**
- Index only essential fields: dataset title, AI-generated keywords (short), department, category. Do NOT index full descriptions or column names in the primary search index.
- Pre-build the Lunr.js index at export time (not in the browser). Ship the serialized index, not raw data that gets indexed on page load.
- Measure the index JSON file size after your first full export. Set a budget: under 500KB for the search index file. If it exceeds this, trim indexed fields.
- Consider FlexSearch or MiniSearch as alternatives if Lunr.js index size becomes problematic -- they offer better compression and memory efficiency.
- Implement lazy loading: load the search index only when the user activates the search box, not on page load.

**Warning signs:**
- Search index JSON file exceeds 1MB after full catalog export.
- Search page takes more than 2 seconds to become interactive on mobile.
- Users report browser tab crashes on the search page.

**Phase to address:**
Phase 4 (Static Site Generation). Must be tested with realistic catalog size, not just a handful of datasets.

---

### Pitfall 5: Socrata Pagination Off-by-One and Silent Truncation

**What goes wrong:**
The Socrata Discovery API paginates at 100 results per page by default. The `offset` parameter is zero-based. Developers commonly introduce off-by-one errors (starting at offset=1, or incrementing by 99 instead of 100) that cause either duplicate records or skipped records. Worse, the API does not return an error when `offset` exceeds the total result count -- it simply returns an empty `results` array. If your pagination loop has a bug, you may silently stop early and think you have all datasets.

**Why it happens:**
The API returns `resultSetSize` in the response body but the actual result array may be shorter on the last page. Developers check `len(results) == 0` to stop but don't verify against `resultSetSize`. Or they use `limit` and `offset` with SODA query parameters (which use `$limit` and `$offset` with dollar signs) and confuse Discovery API parameters (no dollar sign) with SODA query parameters.

**How to avoid:**
- Use `resultSetSize` from the first response as the expected total. After pagination completes, assert `len(all_results) == resultSetSize`. If they differ, raise an error, don't silently continue.
- Use `offset` starting at 0, incrementing by your `limit` value (100). Test with a domain that has exactly 100, 101, 200, and 201 datasets if possible.
- Add an integration test that pulls from a known small domain and verifies the count matches.
- Never use dollar-sign prefixed parameters (`$limit`, `$offset`) with the Discovery API -- those are for the SODA query API on individual datasets.

**Warning signs:**
- Total datasets in your DB is a suspiciously round number (exactly 100, 200, 300).
- `resultSetSize` from the API doesn't match your local count.
- Some datasets referenced in portal links are missing from your catalog.

**Phase to address:**
Phase 1 (Data Ingestion). The pagination logic is foundational -- get it wrong and everything downstream is incomplete.

---

### Pitfall 6: ArcGIS Hub API v3 Undocumented Behavior and Instability

**What goes wrong:**
The ArcGIS Hub API v3 (`/api/v3/datasets`) has minimal official documentation. The most complete reference is an unofficial GitHub Gist from 2019. The API's pagination uses `page[size]` (max 100) and `page[number]` parameters, but edge cases around filtering, sorting, and total counts are poorly documented. Some Hub sites return different datasets depending on whether you query the central `hub.arcgis.com` endpoint or the site-specific subdomain. The API can also return different results over time as datasets are republished or their sharing settings change.

**Why it happens:**
ArcGIS Hub's API is primarily designed for Esri's own front-end applications, not as a stable public API for third-party consumers. Documentation is sparse because Esri doesn't prioritize it as a developer-facing product.

**How to avoid:**
- Start by querying the site-specific endpoint (`gis-mdc.opendata.arcgis.com/api/v3/datasets`) rather than the central hub endpoint. This scopes results to Miami-Dade specifically.
- Record the full API response structure from your first successful pull and use it as a schema reference. When the structure changes, fail loudly.
- Implement response validation: check that expected fields (`id`, `attributes.name`, `attributes.description`) exist in every record. Log and skip malformed records rather than crashing.
- Cache raw API responses to disk (JSON files) before parsing. This gives you a recovery point if parsing fails and lets you debug without re-hitting the API.

**Warning signs:**
- Fields you relied on (like `attributes.structuredLicense` or `attributes.metadata`) are `null` or missing on some records.
- Dataset counts fluctuate between pulls without corresponding portal changes.
- 500 errors from the Hub API during pagination (mid-page failures).

**Phase to address:**
Phase 1 (Data Ingestion). Build defensively from the start; treat this API as unstable.

---

### Pitfall 7: Enrichment Prompt Drift Invalidating Existing Enrichments

**What goes wrong:**
You enrich 500 datasets with Prompt v1. Later, you improve the prompt (better use cases, different output format, additional fields). Now you have a catalog with inconsistent enrichment quality -- some datasets have v1 enrichments, new ones have v2. The "What Changed" page shows no changes because the metadata didn't change, but the enrichment quality is visibly inconsistent across the site.

**Why it happens:**
Developers iterate on the enrichment prompt during development but don't version it or track which prompt version produced which enrichments. The "enrich only new datasets" strategy (designed to save costs) means old enrichments never get updated.

**How to avoid:**
- Store a `prompt_version` field alongside every enrichment record. When the prompt changes, increment the version.
- Add a CLI command: `mdc-encyclopedia enrich --upgrade-from-version 1` that re-enriches only datasets with enrichments from an older prompt version. This gives you targeted re-enrichment without a full re-run.
- Freeze the prompt before the first full-catalog enrichment. Do all prompt iteration on a small test set (10-20 datasets) before committing to a full run.
- Store the actual prompt hash (not just a version number) so you can detect even minor prompt changes.

**Warning signs:**
- Dataset pages on the site have noticeably different description styles or detail levels.
- Enrichment records have no `prompt_version` or `prompt_hash` column.
- You've changed the enrichment prompt 3+ times without re-enriching old datasets.

**Phase to address:**
Phase 2 (AI Enrichment). Design the versioning schema before writing the first enrichment prompt.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoding Miami-Dade domain strings | Faster to implement | Can't reuse for other counties or portals; domain changes break everything | MVP only -- extract to config before v1.0 |
| Skipping column metadata fetch (Socrata `/api/views/{id}.json`) | Faster pulls, fewer API calls | Datasets without column info have incomplete pages; search can't index column names | Never -- column metadata is core to the encyclopedia value proposition |
| Storing enrichments as a single JSON blob | Simpler schema, one column | Can't query individual enrichment fields (e.g., "show all datasets in Parks department"); harder to do partial re-enrichment | MVP only -- normalize before building category/department browsing |
| No migration strategy for SQLite schema | Fewer files, simpler project | Adding columns later requires manual ALTER TABLE or data loss; switching branches in development corrupts local DB | Never -- use sqlite-utils `transform` or a simple version table from day one |
| Generating HTML without content hashing | Simpler build | Every export regenerates all pages even if nothing changed; slow CI builds for large catalogs | MVP only -- add content hashing before weekly CI runs |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Socrata Discovery API | Using `$limit`/`$offset` (SoQL syntax) instead of `limit`/`offset` (plain params) | Discovery API uses plain `limit` and `offset` without dollar signs. SoQL parameters are only for per-dataset SODA queries. |
| Socrata `/api/views/{id}.json` | Assuming all datasets have the same column metadata structure | Some datasets are "blobby" (file-based) and lack column definitions. Check for `columns` key existence before parsing. |
| Socrata app tokens | Not registering a token because "unauthenticated works fine" | Without a token, you hit aggressive rate limits (~60 req/min). With a token, limits increase to ~1,000 req/min. SODA3 will require tokens. Register one now. |
| ArcGIS Hub API | Assuming `page[number]` is zero-indexed | It is 1-indexed. Starting at 0 may return the same page as 1, causing duplicate records. |
| ArcGIS Hub API | Using the central `hub.arcgis.com` endpoint expecting only Miami-Dade data | Use the site-specific subdomain endpoint or filter by `source` to scope results. |
| Anthropic Python SDK | Not handling `RateLimitError` separately from other API errors | The SDK auto-retries 2 times with exponential backoff for transient errors, but you need to handle `RateLimitError` explicitly with longer backoff for batch enrichment (add 30-60s delay, not just 1-2s). |
| Anthropic Python SDK | Ignoring the 10-minute timeout for non-streaming requests | For complex enrichment prompts on large datasets, responses may approach the timeout. Set an explicit timeout or use streaming for safety. |
| GitHub Pages deployment | Assuming unlimited site size | Published sites must be under 1GB. Deployments timeout after 10 minutes. For a catalog of hundreds of datasets with individual HTML pages, you're fine, but monitor if you add data previews or large assets later. |
| GitHub Actions (weekly CI) | Not setting `timeout-minutes` on the workflow job | Default timeout is 6 hours. A hung API call could burn through your free-tier minutes (2,000/month for free accounts). Set `timeout-minutes: 30` explicitly. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fetching column metadata sequentially (one HTTP call per dataset) | Pull takes 10+ minutes for 500 datasets at 1 req/sec rate limit | Use asyncio with rate-limited semaphore (1 req/sec). Queue all requests but respect the rate limit. Save intermediate results so crashed pulls can resume. | 200+ datasets on Socrata |
| Loading full search index on page load | Search page takes 3-5 seconds to become interactive; mobile browsers freeze | Lazy-load index on first search interaction. Pre-build index at export time. Keep index under 500KB. | Index exceeds 1MB |
| Re-enriching all datasets on every CI run | Weekly Actions run takes 30+ minutes and costs $5+ per run | Track enrichment status per dataset. Only enrich new/changed datasets. Skip enrichment entirely if `ANTHROPIC_API_KEY` is not set. | 100+ unenriched datasets |
| Generating all HTML pages on every export | Export takes minutes for large catalogs, even when only 2 datasets changed | Hash page content, skip unchanged pages. Or use incremental export that only regenerates pages for datasets modified since last export. | 500+ dataset pages |
| Storing raw API responses in SQLite without size limits | Database grows to hundreds of MB with full metadata blobs | Store only the fields you use. Archive raw responses as compressed JSON files for debugging, not in the primary DB. | 1,000+ datasets with full metadata |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Committing `ANTHROPIC_API_KEY` to the repository | API key exposed in public repo history; unauthorized usage charges | Use `.env` file locally (in `.gitignore`). Use GitHub Secrets for Actions. Never pass keys as CLI arguments (visible in process listings). |
| Not sanitizing AI-generated HTML in enrichment output | If Claude's response contains HTML/JS and you render it with `| safe` in Jinja2, XSS on the static site | Always escape enrichment output in templates. Use `| e` filter explicitly. Validate enrichment responses are plain text before storage. |
| Exposing Socrata app token in client-side JavaScript | Token leaked in browser dev tools; someone else uses your quota | App tokens are only needed server-side (in the Python CLI). Never ship them in the static site output. Verify no tokens appear in generated HTML/JS. |
| Using `pickle` or `eval` on cached API responses | Arbitrary code execution if cache files are tampered with | Use JSON serialization only. Never deserialize untrusted formats. |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing raw API field names (e.g., `updatedAt`, `viewCount`) | Non-technical users don't understand what they're looking at | Map every API field to a plain-English label. "Last Updated" not "updatedAt". "Times Viewed" not "viewCount". |
| Displaying quality scores as numbers (0.73) without context | Users don't know if 0.73 is good or bad | Use labels: "Good", "Needs Attention", "Poor". Show a colored bar or badge. Explain what goes into the score. |
| Linking to the raw API endpoint instead of the portal page | Users land on a JSON response and think the site is broken | Always link to the human-readable portal page (`opendata.miamidade.gov/d/{id}`). Keep API links in a collapsible "Developer" section. |
| No explanation of what "enriched by AI" means | Users may distrust AI descriptions or think they are official county descriptions | Add a visible disclaimer on every dataset page: "Description generated by AI based on dataset metadata. Not an official county description." |
| Empty search results with no guidance | User types a query, gets nothing, leaves | Show suggestions: "Try browsing by category" or "Did you mean...?" Show total dataset count so users know the scope. |

## "Looks Done But Isn't" Checklist

- [ ] **Pagination:** Verify total datasets fetched matches `resultSetSize` for Socrata and total pages for ArcGIS Hub. Off-by-one errors are invisible until you compare.
- [ ] **Enrichment resume:** Kill the enrichment process mid-run and restart with `--resume`. Verify it picks up where it left off without re-enriching completed datasets or skipping the interrupted one.
- [ ] **Search on mobile:** Load the search page on a real phone (not just Chrome DevTools responsive mode). Check index load time and memory usage.
- [ ] **Diff detection:** Add a dataset on the portal, run pull + diff, verify it appears as "new." Remove one, verify it appears as "removed." Change a column, verify it appears as "schema changed."
- [ ] **Cost estimate accuracy:** Run `--dry-run` with cost estimate, then run actual enrichment. Compare estimated vs. actual cost. They should be within 20%.
- [ ] **Empty/blobby datasets:** Some Socrata datasets are file-based (PDFs, ZIPs) with no columns. Verify these render correctly on the site without crashing the template.
- [ ] **GitHub Actions weekly run:** Trigger the Action manually. Verify it completes within the timeout, handles missing `ANTHROPIC_API_KEY` gracefully, and deploys to Pages successfully.
- [ ] **Static site with no JavaScript:** Verify the site is still navigable (category pages, dataset pages) when JavaScript is disabled. Search won't work, but browsing should.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Discovery API returning incomplete datasets | LOW | Add missing asset type filters to the pull config. Re-run pull. Missing datasets appear as "new" in diff. |
| SODA3 breaking existing endpoint calls | MEDIUM | Update `SocrataClient` abstraction to use v3 endpoints. Register app token if not done. Re-run pull. No data loss -- just API client changes. |
| AI enrichment cost overrun | LOW | Stop the enrichment process. Completed enrichments are already saved. Review token usage audit. Adjust prompt to reduce token count. Resume with `--resume`. |
| Search index too large | MEDIUM | Reduce indexed fields in the export config. Rebuild index. Redeploy. May require evaluating alternative search libraries (FlexSearch/MiniSearch). |
| SQLite schema needs new columns with no migration strategy | HIGH | Write a migration script to ALTER TABLE. Risk of data loss if done wrong. For SQLite, adding columns is easy but renaming/removing requires table rebuild (sqlite-utils `transform` handles this). |
| Inconsistent enrichment quality (prompt drift) | MEDIUM-HIGH | Add `prompt_version` column retroactively. Identify datasets with old enrichments. Re-enrich selectively with `--upgrade-from-version`. Cost: proportional to number of datasets needing re-enrichment. |
| Corrupt SQLite database in CI | LOW | SQLite DB is regenerated from API pulls. Delete DB, re-run pull. Enrichments are lost if not backed up separately -- store enrichment exports as JSON artifacts in the repo or as GitHub Action artifacts. |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Discovery API incomplete results | Phase 1: Data Ingestion | Assert fetched count matches `resultSetSize`; compare against portal browse count |
| SODA3 migration breakage | Phase 1: Data Ingestion | Integration test hitting live API; SocrataClient abstraction in place |
| Pagination off-by-one | Phase 1: Data Ingestion | Unit test with mocked responses of varying sizes; integration test against live API |
| ArcGIS Hub API instability | Phase 1: Data Ingestion | Response validation on every record; raw response caching; defensive field access |
| AI enrichment cost blowout | Phase 2: AI Enrichment | `--dry-run` and `--cost-estimate` commands work before first full run |
| Enrichment prompt drift | Phase 2: AI Enrichment | `prompt_version` column exists; `--upgrade-from-version` command works |
| Enrichment resume after failure | Phase 2: AI Enrichment | Kill-and-resume test passes; no duplicate enrichments |
| Search index too large | Phase 4: Static Site Generation | Index file size measured and under budget (500KB) after full export |
| GitHub Pages deployment limits | Phase 5: Deployment (CI/CD) | Total site size measured; Actions timeout set; deployment completes in under 10 minutes |
| SQLite schema migration | Phase 1: Data Ingestion (schema design) | Schema version table exists; adding a column doesn't require manual intervention |
| Enrichment output not escaped | Phase 4: Static Site Generation | Template review confirms all enrichment output is escaped; no `| safe` on AI content |
| Socrata app token not registered | Phase 1: Data Ingestion | Token configured in `.env`; tested with authenticated request |

## Sources

- Socrata Discovery API documentation: https://dev.socrata.com/docs/other/discovery (MEDIUM confidence -- documentation is outdated in places)
- SODA3 migration announcement: https://support.socrata.com/hc/en-us/articles/34730618169623-SODA3-API (HIGH confidence -- official Socrata)
- SODA3 endpoint changes: https://dev.socrata.com/docs/endpoints.html (HIGH confidence -- official Socrata)
- Socrata dataset count mismatch: https://stackoverflow.com/questions/58130323 (HIGH confidence -- independently reproducible)
- SODA3 deployment timeline: https://support.socrata.com/hc/en-us/articles/35710697739799-October-2025-Product-Release (HIGH confidence -- official)
- SODA3 token requirements: https://munozbravo.github.io/dotgov/guides/versions/ (MEDIUM confidence -- third-party but detailed)
- ArcGIS Hub API v3 reference: https://gist.github.com/jgravois/1b7ec5080e992a59f65cf7a2190e4365 (LOW confidence -- unofficial 2019 gist, best available)
- Lunr.js performance limits: https://www.previousnext.com.au/blog/fast-and-fuzzy-client-side-search-lunrjs-and-drupal (MEDIUM confidence -- practical testing)
- Fuse.js large dataset issues: https://stackoverflow.com/questions/70984437/fuse-js-takes-10-seconds-with-semi-long-queries (MEDIUM confidence -- reproducible community report)
- Client-side search comparison: https://npm-compare.com/elasticlunr,flexsearch,fuse.js,js-search,lunr,search-index (MEDIUM confidence)
- Anthropic Python SDK retry behavior: https://github.com/anthropics/anthropic-sdk-python (HIGH confidence -- official SDK)
- Anthropic batch processing docs: https://docs.claude.com/en/docs/build-with-claude/batch-processing (HIGH confidence -- official)
- GitHub Pages limits: https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits (HIGH confidence -- official GitHub)
- GitHub Actions limits: https://docs.github.com/en/actions/reference/limits (HIGH confidence -- official GitHub)
- SQLite schema migration patterns: https://david.rothlis.net/declarative-schema-migration-for-sqlite/ (MEDIUM confidence -- well-reasoned technical post)
- sqlite-utils transform documentation: referenced via Hacker News thread https://news.ycombinator.com/item?id=31249823 (HIGH confidence -- sqlite-utils is the chosen tool)

---
*Pitfalls research for: Miami-Dade County Open Data Encyclopedia*
*Researched: 2026-02-24*
