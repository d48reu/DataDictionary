# Phase 2: Data Ingestion - Research

**Researched:** 2026-02-24
**Domain:** HTTP API ingestion, ArcGIS Hub Search API, SQLite upsert, CLI progress display
**Confidence:** HIGH

## Summary

Miami-Dade County's open data catalog lives exclusively on ArcGIS Hub at `opendata.miamidade.gov` (custom domain for `gis-mdc.opendata.arcgis.com`). **There is no Socrata portal.** Live API testing confirmed that the Socrata Discovery API returns "Domain not found" for `opendata.miamidade.gov` and zero Miami-Dade County datasets exist on any Socrata domain. The county migrated entirely to ArcGIS Hub.

The Hub exposes a well-documented OGC-compliant search API at `/api/search/v1/collections/dataset/items` that returns paginated GeoJSON FeatureCollection responses. The catalog contains **576 datasets** (571 Feature Services + 5 File Geodatabases). Pagination uses `limit` (max 100) and `startindex` (1-based) parameters with `rel=next` links in the response. Column/field metadata is NOT included in the search API responses -- it requires a separate call to each dataset's ArcGIS REST endpoint (`{serviceUrl}/{layerId}?f=json`), which returns field names, types, aliases, and nullability.

**Primary recommendation:** Implement a single ArcGIS Hub ingestion client using `httpx` for HTTP requests, `tenacity` for retry logic, and `time.sleep(1)` for rate limiting. The original two-portal architecture (Socrata + ArcGIS) collapses to one portal, which simplifies the design significantly but requires updating the project's requirements and deduplication strategy (no cross-portal deduplication needed).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Match datasets across portals using **normalized title matching** (lowercase, strip whitespace)
- **Exact match only** -- no fuzzy matching. Safer: avoids merging distinct datasets like "Building Permits" and "Building Permits - Active"
- When a dataset appears on both portals, **Socrata is the canonical record** (richer column metadata). ArcGIS URL stored as secondary source link. One row in datasets table, both links preserved.
- Dedup reporting: **summary count by default**, detailed per-pair list with `--verbose` flag
- Rate limit: 1 request/second as specified in requirements
- On API failure: **retry with exponential backoff** (3 retries: 2s, 4s, 8s). After 3 failures, skip that dataset and continue. Report skipped datasets at the end.
- Re-pull behavior: **full refresh** every time (upsert). No incremental/skip-if-recent logic. Designed for a weekly refresh workflow.
- **Two-stage Rich progress bar**: show portal name + bar for each stage ("Socrata [....] 142/350 datasets" then "ArcGIS Hub [....] 89/200 datasets")
- After completion: **Rich summary table** showing total datasets, per-portal counts, deduplicated count, new vs updated, skipped/failed (if any), elapsed time

### Claude's Discretion
- HTTP client choice (requests, httpx, etc.)
- Exact normalization logic for title matching
- Pagination implementation details per API
- How to structure the ingestion module internally

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

### CRITICAL: Portal Reality vs. Original Assumptions

The original project assumed two portals:
1. **Socrata** at `opendata.miamidade.gov` -- Discovery API
2. **ArcGIS Hub** at `gis-mdc.opendata.arcgis.com` -- Hub API

**Verified reality (live API testing 2026-02-24):**
- `opendata.miamidade.gov` IS ArcGIS Hub (confirmed by `window.__SITE` config, Hub admin links, and `/api/search/v1` endpoint)
- `gis-mdc.opendata.arcgis.com` returns the same 576 datasets -- it is an alias for the same site
- Socrata Discovery API returns `{"error":"Domain not found: opendata.miamidade.gov"}`
- Searching Socrata for `"miami-dade county"` finds only 2 datasets on unrelated federal domains (Utah, Transportation)
- Miami-Dade County has **zero datasets** on any Socrata portal

**Impact on locked decisions:**
- Deduplication strategy (cross-portal matching) is moot -- there is only one portal
- "Socrata is canonical record" is inapplicable
- Two-stage progress bar simplifies to one stage
- INGEST-01 (Socrata Discovery API) cannot be implemented as specified -- there is no Socrata data
- INGEST-03 (Socrata Views API for columns) must be replaced with ArcGIS REST field metadata

**Recommendation:** The planner should adapt the locked decisions to the single-portal reality. Deduplication logic should handle duplicate items *within* the ArcGIS Hub catalog (e.g., a Feature Service and its child layers appearing as separate items). The progress bar becomes a single stage. Requirements INGEST-01 and INGEST-03 should be reinterpreted to use the ArcGIS Hub API equivalents.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INGEST-01 | CLI can pull full catalog metadata from Socrata Discovery API with pagination (100 results/request) | **REINTERPRET**: No Socrata portal exists. Use ArcGIS Hub Search API (`/api/search/v1/collections/dataset/items`) with `limit=100` and `startindex` pagination. Verified: returns all 576 datasets across 6 pages. |
| INGEST-02 | CLI can pull full catalog metadata from ArcGIS Hub API (`/api/v3/datasets`) | **REINTERPRET**: The v3 API is undocumented and returned empty responses in testing. Use the OGC-compliant Hub Search API at `/api/search/v1/collections/dataset/items` instead. Verified working with full pagination. |
| INGEST-03 | CLI fetches column/field metadata per dataset from Socrata Views API (`/api/views/{id}.json`) | **REINTERPRET**: No Socrata. Fetch field metadata from ArcGIS REST endpoints: `{serviceUrl}/{layerId}?f=json` returns `fields` array with name, type, alias, nullable. Works for 571/576 datasets (Feature Services). 5 File Geodatabases lack REST endpoints. |
| INGEST-05 | All API calls rate-limited to 1 request/second | Use `time.sleep(1.0)` between requests. httpx Client with synchronous calls makes this straightforward. Tenacity retry waits (2s, 4s, 8s) naturally exceed the rate limit. |
| INGEST-06 | Datasets appearing on both portals are detected and deduplicated | **REINTERPRET**: Only one portal exists. Within-catalog deduplication may still be needed: a Feature Service with 3 layers appears as 1 item in Hub search, but the ArcGIS REST endpoint reveals 3 sub-layers. Decision needed on whether to store each layer as a separate dataset or collapse multi-layer services. |
| CLI-03 | `pull` command fetches metadata from both portals | **REINTERPRET**: `pull` fetches from ArcGIS Hub Search API. Single portal, single stage. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.x | HTTP client for API calls | Modern, supports timeouts, connection pooling, sync mode; already used by anthropic SDK in this project |
| tenacity | 9.x | Retry with exponential backoff | De facto Python retry library; decorator-based, configurable stop/wait strategies |
| rich | 14.x | Progress bars, tables, console output | Already a project dependency; Progress class supports multi-task bars with custom columns |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| time (stdlib) | -- | Rate limiting via `time.sleep(1)` | Every API call; simplest correct approach for 1 req/s |
| sqlite3 (stdlib) | -- | Database operations | Already used in Phase 1 `db.py`; upserts via `INSERT OR REPLACE` |
| json (stdlib) | -- | Parse API responses | httpx returns `.json()` natively but needed for metadata_json field |
| html (stdlib) | -- | Strip HTML from descriptions | ArcGIS Hub returns HTML-wrapped descriptions (`<span style=...>`) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx | requests | requests is simpler but lacks built-in timeout configuration; httpx already a transitive dependency |
| tenacity | hand-rolled retry | tenacity handles edge cases (max attempts, wait strategies, exception filtering) that hand-rolled code misses |
| time.sleep | asyncio rate limiting | Sync is simpler, predictable, and sufficient for ~600 requests at 1/sec (~10 min total) |

**Installation:**
```bash
pip install httpx tenacity
```
(rich and rich-click already in pyproject.toml dependencies)

## Architecture Patterns

### Recommended Project Structure
```
src/mdc_encyclopedia/
├── cli.py               # Existing -- add pull command implementation
├── db.py                # Existing -- add upsert functions
├── ingestion/
│   ├── __init__.py
│   ├── hub_client.py    # ArcGIS Hub Search API client
│   ├── field_fetcher.py # ArcGIS REST field metadata fetcher
│   └── normalizer.py    # Data normalization (HTML stripping, field mapping)
```

### Pattern 1: Paginated API Client with Generator
**What:** Generator function that yields pages from the Hub Search API, following `rel=next` links
**When to use:** Any paginated API where total count is known upfront

```python
# Source: Verified against live API responses 2026-02-24
import time
import httpx

def fetch_all_datasets(base_url: str, client: httpx.Client) -> Iterator[dict]:
    """Yield all dataset items from Hub Search API, paginating automatically."""
    url = f"{base_url}/api/search/v1/collections/dataset/items"
    params = {"limit": 100, "startindex": 1}

    while True:
        time.sleep(1.0)  # Rate limit: 1 req/sec
        response = client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        for feature in data.get("features", []):
            yield feature

        # Follow rel=next link
        next_link = None
        for link in data.get("links", []):
            if link.get("rel") == "next":
                next_link = link["href"]
                break

        if not next_link or not data.get("features"):
            break

        # Parse startindex from next link
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(next_link)
        qs = parse_qs(parsed.query)
        params["startindex"] = int(qs.get("startindex", [None])[0])
```

### Pattern 2: Field Metadata Fetcher with Retry
**What:** Fetch field/column metadata from ArcGIS REST endpoint with tenacity retry
**When to use:** Per-dataset calls that may fail individually

```python
# Source: Verified against live ArcGIS REST responses 2026-02-24
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    reraise=True,
)
def fetch_fields(client: httpx.Client, service_url: str) -> list[dict]:
    """Fetch field metadata from ArcGIS REST endpoint.

    For Feature Services, the service_url may point to the service root
    (e.g., .../FeatureServer). We need to query each layer endpoint
    (e.g., .../FeatureServer/0) to get fields.
    """
    time.sleep(1.0)  # Rate limit

    # First get the service info to find layers
    resp = client.get(service_url, params={"f": "json"})
    resp.raise_for_status()
    service_info = resp.json()

    layers = service_info.get("layers", [])
    if not layers:
        # URL might already point to a specific layer
        fields = service_info.get("fields", [])
        return [normalize_field(f) for f in fields]

    # Fetch fields for each layer
    all_fields = []
    for layer in layers:
        time.sleep(1.0)
        layer_url = f"{service_url}/{layer['id']}"
        resp = client.get(layer_url, params={"f": "json"})
        resp.raise_for_status()
        layer_info = resp.json()
        for f in layer_info.get("fields", []):
            all_fields.append(normalize_field(f, layer_name=layer["name"]))

    return all_fields
```

### Pattern 3: SQLite Upsert for Full Refresh
**What:** Use `INSERT OR REPLACE` to implement full-refresh upsert semantics
**When to use:** The pull command always does a full refresh (per locked decision)

```python
def upsert_dataset(conn: sqlite3.Connection, dataset: dict) -> str:
    """Insert or update a dataset record. Returns 'new' or 'updated'."""
    # Check if exists
    existing = conn.execute(
        "SELECT id FROM datasets WHERE id = ?", (dataset["id"],)
    ).fetchone()

    conn.execute("""
        INSERT OR REPLACE INTO datasets
        (id, source_portal, source_url, title, description, category,
         publisher, format, created_at, updated_at, row_count, tags,
         license, api_endpoint, bbox, metadata_json, pulled_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        dataset["id"], dataset["source_portal"], dataset["source_url"],
        dataset["title"], dataset["description"], dataset["category"],
        dataset["publisher"], dataset["format"], dataset["created_at"],
        dataset["updated_at"], dataset["row_count"], dataset["tags"],
        dataset["license"], dataset["api_endpoint"], dataset["bbox"],
        dataset["metadata_json"],
    ))

    return "updated" if existing else "new"
```

### Pattern 4: Rich Progress with Portal Stage
**What:** Single-stage Rich progress bar for ArcGIS Hub ingestion
**When to use:** The `pull` command

```python
# Source: Rich docs at rich.readthedocs.io/en/stable/progress.html
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TaskProgressColumn(),
    TextColumn("datasets"),
    TimeElapsedColumn(),
) as progress:
    # total is known from first API response (numberMatched)
    task = progress.add_task("ArcGIS Hub", total=576)
    for dataset in fetch_all_datasets(...):
        process_dataset(dataset)
        progress.update(task, advance=1)
```

### Anti-Patterns to Avoid
- **Async for sequential rate-limited requests:** At 1 req/sec, async adds complexity with zero benefit. Use synchronous httpx.Client.
- **Storing raw API responses:** Normalize during ingestion; don't dump the full Hub response into metadata_json. Map to the schema fields.
- **Fetching field metadata in the pagination loop:** Separate the catalog fetch (fast, 6 requests) from the field fetch (slow, 571+ requests). Two phases within one `pull` command.
- **Hardcoding pagination math:** Follow the `rel=next` link from the response instead of computing `startindex` manually.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry with backoff | Custom while-loop with sleep | tenacity `@retry` decorator | Handles attempt counting, wait strategies, exception filtering, logging |
| HTTP client with timeouts | raw urllib/requests | httpx.Client with Timeout config | Connection pooling, configurable per-operation timeouts, raise_for_status() |
| Progress display | print() statements | rich.progress.Progress | Live-updating bar, accurate ETA, elapsed time, task management |
| HTML tag stripping | regex `re.sub(r'<.*?>', '', text)` | `html.parser` or `re.sub` with `html.unescape` | ArcGIS descriptions contain HTML entities; need both tag removal and entity decoding |

**Key insight:** The ingestion pipeline is straightforward HTTP GET -> parse JSON -> upsert SQLite. The complexity is in error handling (retries, skipped datasets), progress display, and field normalization -- all of which have battle-tested library solutions.

## Common Pitfalls

### Pitfall 1: ArcGIS Hub Timestamps are Unix Milliseconds
**What goes wrong:** Dates stored as garbage strings or wrong values
**Why it happens:** Hub Search API returns `created` and `modified` as Unix timestamps in **milliseconds** (e.g., `1614732032000`), not seconds
**How to avoid:** Divide by 1000 before converting: `datetime.fromtimestamp(ts / 1000).isoformat()`
**Warning signs:** Dates in year 50000+

### Pitfall 2: Multi-Layer Feature Services
**What goes wrong:** Missing field metadata or overcounting datasets
**Why it happens:** A single Hub search result (e.g., "PCB Report") can be a Feature Service with 3 layers (SRRR, UFC, OIS), each with different fields. The service URL points to the root (`/FeatureServer`), not a specific layer.
**How to avoid:** When fetching field metadata, query the service root first to discover layers, then query each layer endpoint for fields. Decide whether to store one dataset record per Hub item or one per layer.
**Warning signs:** Field metadata returns empty or returns only the service-level metadata without fields

### Pitfall 3: HTML in Description Fields
**What goes wrong:** Descriptions stored with `<span style='font-family:...'>` wrapping
**Why it happens:** ArcGIS Hub stores descriptions as HTML, not plain text
**How to avoid:** Strip HTML tags and decode entities during normalization. Use a simple regex or `html.parser` to clean.
**Warning signs:** Descriptions starting with `<span` or containing `&quot;`

### Pitfall 4: File Geodatabase Datasets Have No Service URL
**What goes wrong:** NoneType errors when trying to fetch field metadata
**Why it happens:** 5 out of 576 datasets are File Geodatabases with `url: null`. These have no REST endpoint for field metadata.
**How to avoid:** Check `props.get("url")` before attempting field fetch. Store these datasets without column metadata.
**Warning signs:** Null service URLs, type="File Geodatabase"

### Pitfall 5: Rate Limit Must Include Retry Waits
**What goes wrong:** Burst of retried requests exceeding 1 req/s
**Why it happens:** Tenacity retries with 2s/4s/8s backoff naturally exceed the rate limit, but if the retry itself succeeds quickly after the wait, the next normal request might fire too soon.
**How to avoid:** Place `time.sleep(1.0)` inside every function that makes an HTTP call, before the call. This ensures rate limiting regardless of retry state.
**Warning signs:** API returning 429 errors

### Pitfall 6: startindex is 1-Based
**What goes wrong:** First dataset duplicated or skipped
**Why it happens:** The Hub Search API uses `startindex` starting at 1, not 0. The `rel=next` link in the response provides the correct next startindex.
**How to avoid:** Always follow the `rel=next` link rather than computing offsets manually.
**Warning signs:** First or last dataset missing/duplicated, off-by-one in total count

## Code Examples

### Hub Search API Response Structure
```json
// Source: Live API response from https://opendata.miamidade.gov/api/search/v1/collections/dataset/items?limit=2
// Verified: 2026-02-24
{
  "type": "FeatureCollection",
  "numberReturned": 2,
  "numberMatched": 576,
  "features": [
    {
      "id": "d260bfad798a4f868d277990511620cc",
      "type": "Feature",
      "geometry": { "type": "Polygon", "coordinates": [[...]] },
      "properties": {
        "title": "MDPD PCB Reporting Data - Feature Layer",
        "description": "<span style='...'>...</span>",
        "snippet": "A feature layer of Miami-Dade Sheriff's Office...",
        "type": "Feature Service",
        "url": "https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/PCB_Report/FeatureServer",
        "owner": "e76180@miamidade.gov_MDC",
        "source": "Miami-Dade County, Florida",
        "tags": ["SRRR", "Production", "Police"],
        "categories": ["/Categories/Production Content", "/Categories/Source Department/Police"],
        "created": 1614732032000,
        "modified": 1745288342000,
        "numViews": 20455,
        "access": "public",
        "orgId": "8Pc9XBTAsYuxx9Ny",
        "accessInformation": "Miami-Dade County Information Technology Department",
        "license": "custom",
        "licenseInfo": "<span>...</span>",
        "size": 999424,
        "scoreCompleteness": 100
      },
      "links": [
        {"rel": "self", "href": "https://opendata.miamidade.gov/api/search/v1/collections/dataset/items/d260bfad798a4f868d277990511620cc"},
        {"rel": "collection", "href": "https://opendata.miamidade.gov/api/search/v1/collections/dataset"}
      ]
    }
  ],
  "links": [
    {"rel": "self", "href": "https://opendata.miamidade.gov/api/search/v1/collections/dataset/items"},
    {"rel": "next", "href": "https://opendata.miamidade.gov/api/search/v1/collections/dataset/items?limit=2&startindex=3"},
    {"rel": "collection", "href": "https://opendata.miamidade.gov/api/search/v1/collections/dataset"}
  ]
}
```

### ArcGIS REST Field Metadata Response
```json
// Source: Live API response from .../PCB_Report/FeatureServer/0?f=json
// Verified: 2026-02-24
{
  "name": "SRRR",
  "type": "Feature Layer",
  "geometryType": "esriGeometryPoint",
  "description": "Supervisor's Report of Response to Resistance...",
  "fields": [
    {
      "name": "OBJECTID",
      "type": "esriFieldTypeOID",
      "alias": "OBJECTID",
      "sqlType": "sqlTypeOther",
      "nullable": false,
      "editable": false,
      "domain": null,
      "defaultValue": null
    },
    {
      "name": "District",
      "type": "esriFieldTypeString",
      "alias": "District",
      "sqlType": "sqlTypeOther",
      "nullable": true,
      "editable": true,
      "domain": null,
      "defaultValue": null,
      "length": 30
    }
  ]
}
```

### Hub Properties to Schema Mapping
```python
# Mapping from Hub Search API feature properties to datasets table columns
def normalize_hub_dataset(feature: dict) -> dict:
    """Convert ArcGIS Hub search result to datasets table row."""
    props = feature.get("properties", {})

    # Parse categories: "/Categories/Source Department/Police" -> "Police"
    categories = props.get("categories", [])
    category = None
    for cat in categories:
        parts = cat.split("/")
        if len(parts) >= 3 and parts[1] == "Categories":
            # Use the most specific category
            category = parts[-1]
            break

    # Timestamps: milliseconds -> ISO string
    created = _ms_to_iso(props.get("created"))
    modified = _ms_to_iso(props.get("modified"))

    # Strip HTML from description
    description = strip_html(props.get("description", ""))

    # Tags: list -> JSON string for storage
    tags = json.dumps(props.get("tags", []))

    return {
        "id": feature.get("id"),
        "source_portal": "arcgis_hub",
        "source_url": f"https://opendata.miamidade.gov/datasets/{feature.get('id')}",
        "title": props.get("title"),
        "description": description,
        "category": category,
        "publisher": props.get("source", props.get("owner")),
        "format": props.get("type"),  # "Feature Service", "File Geodatabase"
        "created_at": created,
        "updated_at": modified,
        "row_count": None,  # Not available from search API
        "tags": tags,
        "license": props.get("licenseInfo", ""),
        "api_endpoint": props.get("url"),  # Service URL for REST queries
        "bbox": json.dumps(feature.get("geometry")) if feature.get("geometry") else None,
        "metadata_json": json.dumps(props),
    }


def _ms_to_iso(ms_timestamp: int | None) -> str | None:
    """Convert millisecond Unix timestamp to ISO 8601 string."""
    if ms_timestamp is None:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ms_timestamp / 1000, tz=timezone.utc).isoformat()
```

### ArcGIS Field Type Mapping
```python
# Map ArcGIS field types to simpler type names for the columns table
ESRI_TYPE_MAP = {
    "esriFieldTypeOID": "integer",
    "esriFieldTypeInteger": "integer",
    "esriFieldTypeSmallInteger": "integer",
    "esriFieldTypeDouble": "number",
    "esriFieldTypeSingle": "number",
    "esriFieldTypeString": "text",
    "esriFieldTypeDate": "date",
    "esriFieldTypeGeometry": "geometry",
    "esriFieldTypeGlobalID": "text",
    "esriFieldTypeGUID": "text",
    "esriFieldTypeBlob": "binary",
    "esriFieldTypeXML": "text",
}

def normalize_field(field: dict, layer_name: str = "") -> dict:
    """Convert ArcGIS REST field to columns table row."""
    return {
        "name": field.get("name"),
        "data_type": ESRI_TYPE_MAP.get(field.get("type"), field.get("type")),
        "description": field.get("alias", ""),  # alias is the closest thing to a description
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ArcGIS Hub v3 API (`/api/v3/datasets`) | Hub Search API (`/api/search/v1`) | ~2023 | v3 is undocumented and returned empty responses in testing. Search API is OGC-compliant with OpenAPI spec. |
| Socrata + ArcGIS dual portals | ArcGIS Hub only | Unknown (pre-2024) | Miami-Dade migrated entirely to ArcGIS Hub. No Socrata datasets remain. |
| data.json bulk catalog endpoint | Hub Search API with pagination | Current | data.json exists but is 4MB+ and truncates; Search API is reliable and paginated |

**Deprecated/outdated:**
- **ArcGIS Hub v3 API** (`/api/v3/datasets`): Referenced in 2019 GitHub gist but returned empty responses when tested against `opendata.miamidade.gov` and `hub.arcgis.com`. Use `/api/search/v1` instead.
- **Socrata Discovery API for Miami-Dade**: Domain not found. No Socrata presence for Miami-Dade County.

## Open Questions

1. **Multi-layer Feature Service handling**
   - What we know: 571 Feature Services in the catalog. Some (like PCB Report) have multiple layers (3 layers). Each layer has different fields.
   - What's unclear: Should we store one dataset row per Hub item (with aggregated fields from all layers), or one row per layer (expanding 571 items to potentially more)?
   - Recommendation: Store one row per Hub item (matches the catalog's presentation). Store fields from all layers in the columns table, tagged with the layer name. This keeps the dataset count aligned with what users see on the portal.

2. **Within-catalog deduplication**
   - What we know: The Hub Search API returns 576 unique items. No obvious duplicates were observed in a full scan.
   - What's unclear: Whether the same underlying data sometimes appears as both a Feature Service and File Geodatabase, or whether different Hub items point to the same ArcGIS REST service.
   - Recommendation: During implementation, log any cases where multiple Hub items share the same `url` (service endpoint). This will reveal if within-catalog dedup is needed. For Phase 2, implement the detection but don't block on it.

3. **Schema migration for single-portal reality**
   - What we know: The `datasets.source_portal` column expects values like "socrata" or "arcgis_hub". With only one portal, all records will be "arcgis_hub".
   - What's unclear: Whether to keep the column (for future multi-jurisdiction expansion per v2 MULTI-01/02) or simplify.
   - Recommendation: Keep the column. It costs nothing and enables future expansion. Always set to "arcgis_hub" for now.

4. **Download URL field**
   - What we know: The datasets table has a `download_url` column. ArcGIS Hub provides download links through the `/api/download/v1/items/{id}/csv` pattern seen in `data.json`.
   - What's unclear: Whether to populate this field from the Hub Search API (which doesn't include download URLs directly) or construct it.
   - Recommendation: Construct it as `https://opendata.miamidade.gov/api/download/v1/items/{id}/csv?layers=0` for Feature Services. Leave null for File Geodatabases.

## Sources

### Primary (HIGH confidence)
- **Live API testing** (2026-02-24) - Verified all endpoints, response structures, pagination, and dataset counts against `opendata.miamidade.gov`
- **OpenAPI specification** at `https://opendata.miamidade.gov/api/search/definition/?f=json` - Full parameter documentation for Hub Search API
- **Context7 /encode/httpx** - httpx timeout configuration, transport retries
- **Context7 /websites/rich_readthedocs_io_en_stable** - Rich progress bar multi-task setup, custom columns
- **Context7 /websites/tenacity_readthedocs_io_en** - Retry decorators, exponential backoff configuration

### Secondary (MEDIUM confidence)
- **ArcGIS Hub v3 API gist** (2019) by jgravois - https://gist.github.com/jgravois/1b7ec5080e992a59f65cf7a2190e4365 - Provided initial v3 endpoint structure, but v3 did not work in practice
- **Esri Community posts** - Confirmed `page[size]` and `page[number]` parameters for v3 (which we're not using), and data.json endpoint existence

### Tertiary (LOW confidence)
- **SODA3 migration status** (munozbravo.github.io) - Mentioned SODA 3.0 deployment during 2025, but irrelevant since Miami-Dade has no Socrata presence

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - httpx/tenacity/rich are mature, well-documented, already available in project
- Architecture: HIGH - API endpoints verified with live requests, response structures captured, pagination tested end-to-end
- Pitfalls: HIGH - All pitfalls discovered through live API testing (timestamp formats, HTML descriptions, multi-layer services, null URLs)

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (API endpoints and response formats are stable; dataset count will change over time)
