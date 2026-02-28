# Phase 10: Enriched Catalog Export - Research

**Researched:** 2026-02-27
**Domain:** Data serialization (JSON/CSV), DCAT-US v1.1 metadata standard, static file generation
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **DCAT-US field mapping:** Practical subset alignment -- map the DCAT-US v1.1 fields we can actually populate from our data, skip fields we can't. JSON structure follows the federal data.json convention: root object with `conformsTo` and `dataset` array. Use standard DCAT-US property names (title, description, publisher, keyword, modified, distribution, etc.). Omit unpopulated fields entirely -- no nulls or placeholders for fields like contactPoint or accessLevel.
- **Export content scope:** Include AI enrichment data (summaries, quality grades) as extra fields beyond standard DCAT -- this is the unique value-add. Single combined file across all jurisdictions, with a jurisdiction field on each record. Current snapshot only -- no change history (Atom feed covers change tracking). Multi-value fields in CSV (tags, themes) use semicolon separation within a single column.

### Claude's Discretion
- About page download link styling and placement
- CSV column ordering
- CSV column header naming (DCAT names vs human-friendly -- can differ from JSON)
- File naming convention for generated exports
- Whether to include a dataset count or generation timestamp in the JSON metadata

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EXPORT-01 | Downloadable enriched catalog as JSON with DCAT-US v1.1 field alignment and jurisdiction field | DCAT-US v1.1 field mapping documented below; JSON generation uses Python stdlib `json` module; `conformsTo` URI and root structure confirmed from federal spec |
| EXPORT-02 | Downloadable enriched catalog as CSV with UTF-8 BOM for Excel | Python `utf-8-sig` encoding verified to produce correct BOM bytes; `csv` stdlib module handles all serialization; semicolon separator for multi-value fields per user decision |
| EXPORT-03 | Download links on About page with format and file size | `os.path.getsize()` after generation provides byte count; about.html template and `_render_about_page` in generator.py already have access to site_data and stats; pattern mirrors feed stats wiring from Phase 9 |
</phase_requirements>

## Summary

Phase 10 adds two downloadable catalog files (JSON and CSV) generated during the existing `mdc-encyclopedia export` command's site build, plus download links on the About page. This is a straightforward serialization task with zero new dependencies -- Python's stdlib `json` and `csv` modules handle everything. The only domain complexity is mapping our internal database fields to DCAT-US v1.1 property names in JSON.

The DCAT-US v1.1 specification (formally "Project Open Data Metadata Schema v1.1") defines the federal standard for data.json catalog files. The root structure uses `conformsTo: "https://project-open-data.cio.gov/v1.1/schema"` with a `dataset` array. Required dataset fields include `title`, `description`, `keyword`, `modified`, `publisher`, `identifier`. Our database can populate most of these. Fields we cannot populate (like `contactPoint`, `accessLevel`, `bureauCode`, `programCode`) are federal-specific and should be omitted per the user decision to do practical subset alignment.

The CSV export requires UTF-8 BOM (byte order mark: `\xef\xbb\xbf`) for Excel on Windows to correctly detect UTF-8 encoding. Python's `utf-8-sig` codec handles this automatically -- `open(path, 'w', encoding='utf-8-sig')` writes the BOM prefix. This was verified in the current Python 3.12 environment.

**Primary recommendation:** Create a single new module `src/mdc_encyclopedia/site/catalog_export.py` with two functions (`generate_catalog_json`, `generate_catalog_csv`) that accept `site_data` from `build_site_data()` and write files to the output directory. Wire into `generator.py` unconditionally (no gating flag needed -- unlike the Atom feed, catalog export has no external URL dependency). Pass file sizes to the About page template via stats dict.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `json` (stdlib) | Python 3.10+ | JSON serialization with `indent=2`, `ensure_ascii=False` | Built-in, no dependencies; handles Unicode natively |
| `csv` (stdlib) | Python 3.10+ | CSV writing with `csv.DictWriter` for named columns | Built-in; paired with `utf-8-sig` encoding for Excel BOM |
| `os` (stdlib) | Python 3.10+ | File size measurement via `os.path.getsize()` | Standard file operations |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| None required | -- | -- | All functionality covered by stdlib |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib `json` | `orjson` | Faster but adds a compiled dependency for no real benefit at ~500 datasets |
| stdlib `csv` | `pandas.to_csv()` | Massive dependency for a trivial operation; pandas is not in the project |
| Manual BOM bytes | `codecs.BOM_UTF8` prefix | `utf-8-sig` encoding does this automatically; manual approach is error-prone |

**Installation:**
```bash
# No new packages needed -- all stdlib
```

## Architecture Patterns

### Recommended Project Structure
```
src/mdc_encyclopedia/site/
    catalog_export.py   # NEW: generate_catalog_json(), generate_catalog_csv()
    generator.py        # MODIFIED: call catalog export, pass stats to about template
    context.py          # UNCHANGED: build_site_data() already provides all needed data
    templates/
        about.html      # MODIFIED: add download links section
```

### Pattern 1: Parallel to Feed Generation (Phase 9 Pattern)
**What:** New module with export functions called from `generate_site()` in generator.py, returning stats that feed into the export summary.
**When to use:** Always -- this is the established pattern for adding generated artifacts to the build pipeline.
**Example:**
```python
# In generator.py generate_site(), after _copy_static_assets():

# Catalog export (always generated -- no gating flag needed)
from mdc_encyclopedia.site.catalog_export import generate_catalog_json, generate_catalog_csv

json_stats = generate_catalog_json(site_data, output_dir)
csv_stats = generate_catalog_csv(site_data, output_dir)
stats["catalog_json_size"] = json_stats["file_size"]
stats["catalog_csv_size"] = csv_stats["file_size"]
stats["catalog_dataset_count"] = json_stats["dataset_count"]
```

### Pattern 2: DCAT-US v1.1 Field Mapping via Transform Function
**What:** A pure function that maps a single dataset dict (from `build_site_data()`) to a DCAT-US v1.1 dataset object. Keeps mapping logic isolated and testable.
**When to use:** For the JSON export where field names must match the DCAT-US spec.
**Example:**
```python
# Source: DCAT-US v1.1 spec (resources.data.gov/resources/dcat-us/)
def _dataset_to_dcat(ds: dict) -> dict:
    """Map internal dataset dict to DCAT-US v1.1 JSON object."""
    entry = {
        "@type": "dcat:Dataset",
        "identifier": ds["id"],
        "title": ds.get("title", ""),
        "description": ds.get("ai_description") or ds.get("description", ""),
        "keyword": ds.get("keywords_list") or ds.get("tags_list", []),
        "modified": ds.get("updated_at", ""),
        "publisher": {"@type": "org:Organization", "name": ds.get("publisher", "")},
        "jurisdiction": ds.get("jurisdiction", ""),  # Extension field
    }
    # Conditionally add optional DCAT fields
    if ds.get("category"):
        entry["theme"] = [ds["category"]]
    if ds.get("license"):
        entry["license"] = ds["license"]
    if ds.get("created_at"):
        entry["issued"] = ds["created_at"]
    if ds.get("source_url"):
        entry["landingPage"] = ds["source_url"]
    if ds.get("download_url") or ds.get("api_endpoint"):
        entry["distribution"] = []
        if ds.get("download_url"):
            entry["distribution"].append({
                "@type": "dcat:Distribution",
                "downloadURL": ds["download_url"],
                "mediaType": "text/csv",
                "format": "CSV",
            })
        if ds.get("api_endpoint"):
            entry["distribution"].append({
                "@type": "dcat:Distribution",
                "accessURL": ds["api_endpoint"],
                "format": "API",
            })
    if ds.get("bbox"):
        entry["spatial"] = ds["bbox"]
    if ds.get("update_freq"):
        entry["accrualPeriodicity"] = ds["update_freq"]
    # AI enrichment extensions (beyond DCAT standard)
    if ds.get("ai_description"):
        entry["ext_aiDescription"] = ds["ai_description"]
    if ds.get("civic_relevance"):
        entry["ext_civicRelevance"] = ds["civic_relevance"]
    if ds.get("department"):
        entry["ext_department"] = ds["department"]
    if ds.get("use_cases_list"):
        entry["ext_useCases"] = ds["use_cases_list"]
    if ds.get("letter_grade"):
        entry["ext_qualityGrade"] = ds["letter_grade"]
    if ds.get("composite_score") is not None:
        entry["ext_qualityScore"] = ds["composite_score"]
    return entry
```

### Pattern 3: CSV Flattening with Semicolon Multi-Value Fields
**What:** Flatten nested/list fields into single CSV columns with semicolons as internal delimiters.
**When to use:** For the CSV export where lists (keywords, tags, use cases) must fit in one column.
**Example:**
```python
def _flatten_for_csv(ds: dict) -> dict:
    """Flatten a dataset dict for CSV output with semicolon-delimited lists."""
    keywords = ds.get("keywords_list") or ds.get("tags_list", [])
    use_cases = ds.get("use_cases_list", [])
    return {
        "ID": ds["id"],
        "Title": ds.get("title", ""),
        "Description": ds.get("ai_description") or ds.get("description", ""),
        "Jurisdiction": ds.get("jurisdiction", ""),
        "Category": ds.get("category", ""),
        "Publisher": ds.get("publisher", ""),
        "Keywords": ";".join(keywords),
        # ... etc
    }
```

### Anti-Patterns to Avoid
- **Streaming JSON with manual string building:** Do NOT construct JSON by concatenating strings. Use `json.dumps()` which handles escaping, Unicode, and nested structures correctly.
- **Writing CSV with print/f-strings:** Do NOT manually write comma-separated values. Use `csv.DictWriter` which handles quoting, escaping, and newline conventions per RFC 4180.
- **Generating exports from raw SQL:** Do NOT write a separate DB query for exports. Reuse `site_data` from `build_site_data()` which already has the master JOIN and all parsed fields. This ensures export data matches what's displayed on the site.
- **Adding pandas as a dependency:** The project has no pandas dependency and adding 50MB+ for `to_csv()` is absurd when `csv.DictWriter` does the same in 5 lines.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| UTF-8 BOM for Excel | Manual `\xef\xbb\xbf` byte prefix | `open(path, 'w', encoding='utf-8-sig')` | Python's codec handles BOM insertion and any edge cases automatically |
| JSON serialization | String concatenation | `json.dumps(data, indent=2, ensure_ascii=False)` | Handles escaping, Unicode, nested objects, and formatting |
| CSV quoting/escaping | Manual comma-joining | `csv.DictWriter` with `quoting=csv.QUOTE_MINIMAL` | Handles embedded commas, quotes, newlines per RFC 4180 |
| File size formatting | Manual byte arithmetic | Simple `size_bytes / 1024` with rounding | KB is sufficient precision for catalog files |
| DCAT field validation | Custom schema checker | Just omit fields we can't populate (user decision) | No need for validation -- we control both producer and consumer |

**Key insight:** This phase has zero deceptively complex problems. JSON and CSV serialization are solved problems in Python's stdlib. The only intellectual work is the DCAT-US field mapping, which is a one-time translation table.

## Common Pitfalls

### Pitfall 1: Excel Garbled Characters Without BOM
**What goes wrong:** CSV opens in Excel on Windows with garbled characters (mojibake) for any non-ASCII text like Spanish dataset names or special characters.
**Why it happens:** Excel on Windows defaults to the system ANSI codepage (usually Windows-1252) when opening CSV files. Without a UTF-8 BOM, Excel has no signal to use UTF-8.
**How to avoid:** Use `encoding='utf-8-sig'` when opening the output file. This writes the 3-byte BOM (`EF BB BF`) at the start. Verified working in Python 3.12.
**Warning signs:** Test by checking `raw_bytes[:3] == b'\xef\xbb\xbf'` on the output file.

### Pitfall 2: JSON Lists Stored as Strings in DB
**What goes wrong:** Fields like `tags`, `keywords`, `use_cases` are stored as JSON strings in SQLite (e.g., `'["tag1", "tag2"]'`). If you serialize these directly, you get double-encoded JSON: `"keywords": "[\"tag1\", \"tag2\"]"`.
**Why it happens:** `build_site_data()` already parses these into Python lists (`tags_list`, `keywords_list`, `use_cases_list`), but the raw `tags` field is still a JSON string.
**How to avoid:** Always use the parsed `_list` variants from `build_site_data()` output, not the raw DB fields. The `_build_dataset_context()` function in context.py handles this parsing.
**Warning signs:** Search for `json.loads` calls inside the export module -- if you're parsing JSON, you're using the wrong source data.

### Pitfall 3: Inconsistent Data Between Site and Export
**What goes wrong:** Export files show different data than what appears on the website, confusing users who cross-reference.
**Why it happens:** Writing a separate DB query for exports instead of reusing `site_data`.
**How to avoid:** Both exports must consume `site_data["datasets"]` from `build_site_data()`. This is the same data pipeline that feeds all site pages.
**Warning signs:** Any `conn.execute()` call inside the export module is a red flag.

### Pitfall 4: Null/None Values in JSON Output
**What goes wrong:** JSON output contains `null` for every unpopulated field, creating noisy files where most fields are null.
**Why it happens:** Iterating all possible DCAT fields and defaulting to None.
**How to avoid:** User decision: "Omit unpopulated fields entirely -- no nulls or placeholders." Use conditional `if value:` checks before adding each field to the DCAT dict.
**Warning signs:** `null` appearing in output JSON for fields like `contactPoint` or `accessLevel`.

### Pitfall 5: CSV Column Order Inconsistency
**What goes wrong:** CSV columns appear in random/dict-key order, making the file hard to read.
**Why it happens:** Python dicts are insertion-ordered since 3.7, but if you build the dict dynamically, order can vary.
**How to avoid:** Define the column order explicitly as a `fieldnames` list for `csv.DictWriter`. Put the most useful columns first: ID, Title, Description, Jurisdiction, Category, etc.
**Warning signs:** Opening the CSV and seeing `api_endpoint` as the first column.

### Pitfall 6: File Size Computed Before File is Fully Written
**What goes wrong:** File size shows 0 or incorrect value on the About page.
**Why it happens:** Calling `os.path.getsize()` before the file handle is flushed and closed.
**How to avoid:** Compute file size AFTER the `with open(...)` block exits (which flushes and closes). Return size in the stats dict.
**Warning signs:** File size of 0 in the export summary.

## Code Examples

### Generating DCAT-US v1.1 JSON Catalog
```python
# Source: DCAT-US v1.1 spec, federal data.json convention
import json
import os
from datetime import datetime, timezone

def generate_catalog_json(site_data, output_dir):
    """Generate DCAT-US v1.1 aligned JSON catalog file."""
    datasets = site_data["datasets"]

    catalog = {
        "conformsTo": "https://project-open-data.cio.gov/v1.1/schema",
        "@type": "dcat:Catalog",
        "dataset": [_dataset_to_dcat(ds) for ds in datasets],
    }

    output_path = os.path.join(output_dir, "catalog.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    file_size = os.path.getsize(output_path)
    return {"dataset_count": len(datasets), "file_size": file_size}
```

### Generating UTF-8 BOM CSV for Excel
```python
# Source: Python docs (csv module), utf-8-sig codec
import csv
import os

CSV_COLUMNS = [
    "ID", "Title", "Description", "Jurisdiction", "Category",
    "Publisher", "Keywords", "Modified", "Quality Grade",
    "Quality Score", "AI Description", "Civic Relevance",
    "Department", "Use Cases", "Source URL", "Download URL",
    "Format", "License",
]

def generate_catalog_csv(site_data, output_dir):
    """Generate UTF-8 BOM CSV catalog file for Excel compatibility."""
    datasets = site_data["datasets"]

    output_path = os.path.join(output_dir, "catalog.csv")
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for ds in datasets:
            writer.writerow(_flatten_for_csv(ds))

    file_size = os.path.getsize(output_path)
    return {"dataset_count": len(datasets), "file_size": file_size}
```

### Wiring Into Generator (Phase 9 Pattern)
```python
# In generator.py generate_site(), after _copy_static_assets():
from mdc_encyclopedia.site.catalog_export import generate_catalog_json, generate_catalog_csv

json_stats = generate_catalog_json(site_data, output_dir)
csv_stats = generate_catalog_csv(site_data, output_dir)
stats["catalog_json_size"] = json_stats["file_size"]
stats["catalog_csv_size"] = csv_stats["file_size"]
stats["catalog_dataset_count"] = json_stats["dataset_count"]
```

### About Page Download Links (Jinja2)
```html
<div class="about-section">
    <h2>Download Catalog Data</h2>
    <p>Download the full enriched catalog for use in your own tools:</p>
    <ul class="download-links">
        {% if catalog_json_size %}
        <li>
            <a href="{{ base_url }}/catalog.json" download>
                JSON (DCAT-US v1.1)
            </a>
            <span class="file-meta">{{ catalog_json_size_kb }} KB</span>
        </li>
        {% endif %}
        {% if catalog_csv_size %}
        <li>
            <a href="{{ base_url }}/catalog.csv" download>
                CSV (Excel-compatible, UTF-8)
            </a>
            <span class="file-meta">{{ catalog_csv_size_kb }} KB</span>
        </li>
        {% endif %}
    </ul>
</div>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| DCAT-US v1.0 | DCAT-US v1.1 | 2014 | Added `identifier`, `accessLevel`, `license`, restructured publisher as org object |
| DCAT-US v1.1 | DCAT-US v3.0 (draft) | 2024-2025 | Aligns with W3C DCAT 3.0; adds `dcatap:` prefixes. NOT yet required, out of scope per REQUIREMENTS.md |
| `codecs.BOM_UTF8` prefix | `utf-8-sig` encoding | Python 3.x | Built into codec; no manual byte manipulation needed |

**Deprecated/outdated:**
- DCAT-US v3.0 is in draft status. Per project REQUIREMENTS.md out-of-scope section: "Draft spec, not yet required; use v1.1 field names and migrate when finalized."
- The `conformsTo` URI `https://project-open-data.cio.gov/v1.1/schema` is the canonical v1.1 identifier still in active use by federal agencies.

## DCAT-US v1.1 Field Mapping Reference

This mapping shows which DCAT-US v1.1 fields we can populate from our database. Fields marked "SKIP" are federal-specific or unpopulable.

| DCAT-US v1.1 Property | Required? | Our Source Field | Notes |
|------------------------|-----------|------------------|-------|
| `@type` | No | `"dcat:Dataset"` (constant) | Standard type annotation |
| `title` | Required | `ds["title"]` | Direct map |
| `description` | Required | `ds["ai_description"]` or `ds["description"]` | Prefer AI description when available |
| `keyword` | Required | `ds["keywords_list"]` or `ds["tags_list"]` | AI keywords preferred, fall back to portal tags |
| `modified` | Required | `ds["updated_at"]` | ISO 8601 from DB |
| `publisher` | Required | `{"@type": "org:Organization", "name": ds["publisher"]}` | Nested object per spec |
| `identifier` | Required | `ds["id"]` | Synthetic composite key |
| `contactPoint` | Required | **SKIP** | Not available from ArcGIS Hub metadata |
| `accessLevel` | Required | **SKIP** | Federal-specific; our data is all public |
| `bureauCode` | Required (Fed) | **SKIP** | Federal-specific |
| `programCode` | Required (Fed) | **SKIP** | Federal-specific |
| `license` | If-Applicable | `ds["license"]` | Available from portal |
| `spatial` | If-Applicable | `ds["bbox"]` | GeoJSON bounding box |
| `distribution` | If-Applicable | Build from `download_url` + `api_endpoint` | Array of distribution objects |
| `issued` | Expanded | `ds["created_at"]` | ISO 8601 from DB |
| `landingPage` | Expanded | `ds["source_url"]` | Link to portal page |
| `theme` | Expanded | `[ds["category"]]` | Wrapped in array per spec |
| `accrualPeriodicity` | Expanded | `ds["update_freq"]` | From AI enrichment |
| `jurisdiction` | **Extension** | `ds["jurisdiction"]` | Non-DCAT field, our extension |
| `ext_aiDescription` | **Extension** | `ds["ai_description"]` | AI-generated plain-English description |
| `ext_qualityGrade` | **Extension** | `ds["letter_grade"]` | Quality audit letter grade |
| `ext_qualityScore` | **Extension** | `ds["composite_score"]` | Quality audit composite score |
| `ext_civicRelevance` | **Extension** | `ds["civic_relevance"]` | AI civic relevance assessment |
| `ext_department` | **Extension** | `ds["department"]` | AI-assigned department |
| `ext_useCases` | **Extension** | `ds["use_cases_list"]` | AI-generated use cases |

## CSV Column Recommendation

Use human-friendly headers (Claude's discretion per CONTEXT.md). Order places most useful columns first:

| # | CSV Header | Source | Notes |
|---|-----------|--------|-------|
| 1 | ID | `ds["id"]` | Unique identifier |
| 2 | Title | `ds["title"]` | Dataset name |
| 3 | Description | `ds["ai_description"]` or `ds["description"]` | Prefer AI description |
| 4 | Jurisdiction | `ds["jurisdiction"]` | Jurisdiction slug |
| 5 | Category | `ds["category"]` | Portal category |
| 6 | Publisher | `ds["publisher"]` | Data publisher |
| 7 | Keywords | Semicolon-joined `keywords_list` or `tags_list` | Multi-value, semicolon separated |
| 8 | Last Modified | `ds["updated_at"]` | ISO 8601 date |
| 9 | Created | `ds["created_at"]` | ISO 8601 date |
| 10 | Quality Grade | `ds["letter_grade"]` | A through F |
| 11 | Quality Score | `ds["composite_score"]` | 0.0 to 1.0 |
| 12 | AI Description | `ds["ai_description"]` | Full AI-generated description |
| 13 | Civic Relevance | `ds["civic_relevance"]` | AI assessment |
| 14 | Department | `ds["department"]` | AI-assigned department |
| 15 | Use Cases | Semicolon-joined `use_cases_list` | Multi-value, semicolon separated |
| 16 | Format | `ds["format"]` | Data format type |
| 17 | Source URL | `ds["source_url"]` | Link to portal page |
| 18 | Download URL | `ds["download_url"]` | Direct download link |
| 19 | API Endpoint | `ds["api_endpoint"]` | REST API URL |
| 20 | License | `ds["license"]` | License text |

## File Naming Recommendation

Per Claude's discretion: use `catalog.json` and `catalog.csv`. Simple, discoverable, consistent with the federal `data.json` convention but named "catalog" to avoid confusion with the site's own data files.

## Open Questions

1. **Extension field prefix convention**
   - What we know: DCAT-US v1.1 has no official extension mechanism. The `ext_` prefix is a common convention used by local governments adding custom fields.
   - What's unclear: Whether `ext_` or another prefix (like `mdc_`) is more appropriate.
   - Recommendation: Use `ext_` prefix for all non-DCAT fields in JSON. This is recognizable to DCAT consumers as "extension." In CSV, use plain human-friendly names since CSV consumers don't care about DCAT namespacing.

2. **Description field: AI vs original**
   - What we know: The `description` DCAT field is required. We have both the original portal description and (for enriched datasets) an AI-generated description.
   - What's unclear: Which should go in the DCAT `description` field.
   - Recommendation: Use AI description when available (it's the value-add), original description as fallback. Include AI description separately in `ext_aiDescription` so consumers can distinguish. In CSV, put the best available description in "Description" column and the AI description in a separate "AI Description" column.

## Sources

### Primary (HIGH confidence)
- [DCAT-US v1.1 Schema Specification](https://resources.data.gov/resources/dcat-us/) - Full field definitions, required/optional classification, data types
- [DCAT-US v1.1 Field Mapping](https://resources.data.gov/resources/podm-field-mapping/) - Property name mapping across standards (POD v1.1, CKAN, DCAT, Schema.org)
- [Project Open Data v1.1 Example (GitHub Gist)](https://gist.github.com/philipashlock/21ff607527863fba200b) - Real data.json structure with `conformsTo` URI
- Python 3.12 stdlib verification - `json`, `csv`, `utf-8-sig` codec tested in project environment

### Secondary (MEDIUM confidence)
- [Unicode CSV files for Excel (tobywf)](https://tobywf.com/2017/08/unicode-csv-excel/) - UTF-8 BOM necessity for Excel on Windows
- [CSV Encoding Issues in Excel (madqna)](https://www.madqna.com/2025/11/fix-csv-encoding-issues-in-excel-detect.html) - Confirms BOM requirement for 2025 Excel versions

### Tertiary (LOW confidence)
- None. All findings verified against official specs or tested in environment.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Python stdlib only; no external dependencies; verified in project environment
- Architecture: HIGH - Follows exact same pattern as Phase 9 feed generation (proven working)
- Pitfalls: HIGH - BOM requirement verified empirically; DCAT mapping verified against official spec
- DCAT-US mapping: HIGH - Field names confirmed against resources.data.gov specification and real federal examples

**Research date:** 2026-02-27
**Valid until:** 2027-02-27 (DCAT-US v1.1 is a stable, 10+ year old standard; Python stdlib is stable)
