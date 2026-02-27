# Stack Research: v1.1 Additions

**Domain:** Open data catalog/encyclopedia -- new feature stack for v1.1
**Project:** Miami-Dade County Open Data Encyclopedia
**Researched:** 2026-02-26
**Confidence:** HIGH

## Scope

This document covers ONLY the stack additions and changes needed for v1.1 features:
1. RSS/Atom feed generation for catalog changes
2. JSON/CSV enriched catalog export
3. AI-generated field-level descriptions (B+ datasets)
4. Multi-jurisdiction ArcGIS Hub support (Broward County, City of Miami)

The validated v1.0 stack (Python 3.12+, SQLite, Click, Jinja2, Anthropic SDK, httpx, lunr.py, python-slugify, Rich) is NOT re-researched here.

## Recommended Stack Additions

### New Dependencies: NONE

Every v1.1 feature can be implemented with Python stdlib modules plus existing dependencies. No new pip packages are needed.

**Rationale:** The project already has the heavy lifting covered. Adding dependencies for simple tasks (feed XML, CSV export) would increase the attack surface and maintenance burden for minimal benefit.

### Stdlib Modules to Leverage

| Module | Purpose | Feature | Why Sufficient |
|--------|---------|---------|----------------|
| `xml.etree.ElementTree` | Atom feed generation | FEED-01/02/03 | Atom 1.0 (RFC 4287) is a straightforward XML format. ~80 lines of code to generate a valid feed from the existing `changes` table. No namespace complexity issues since Atom uses a single namespace. |
| `csv` (csv.DictWriter) | CSV catalog export | EXPORT-02 | SQLite rows are already dict-like (`sqlite3.Row`). DictWriter maps directly. Zero transformation needed. |
| `json` (already used) | JSON catalog export | EXPORT-01 | Already imported in 10+ modules. `json.dumps()` on the enriched dataset list is trivial. |
| `datetime` (already used) | Feed timestamps | FEED-01 | RFC 3339 timestamps for Atom `<updated>` elements. Already used throughout the codebase. |

### Existing Dependencies That Extend Naturally

| Existing Dep | v1.1 Feature | How It Extends |
|-------------|-------------|----------------|
| httpx | Multi-jurisdiction | Change `HUB_BASE_URL` from hardcoded constant to configurable per-jurisdiction. Same `create_client()` pattern, same rate limiting, same retry logic. All three portals use identical OGC API Records endpoints. |
| Jinja2 | Feed template (optional) | Could render Atom XML via Jinja2 template instead of ElementTree. Simpler if feed structure is complex, but for this use case ElementTree is cleaner because XML namespace handling in Jinja2 requires `autoescape=False`. |
| Anthropic SDK | Field descriptions | Extend `EnrichmentResult` Pydantic model with field-level descriptions. Same `messages.parse()` call, same structured output pattern. New prompt version (v2.0) for field enrichment. |
| SQLite | Schema v3 | Add `field_enrichments` table or `ai_description` column to `columns` table. Same PRAGMA user_version migration pattern used for v1 to v2. |
| Click | New CLI commands | `mdc-encyclopedia feed` and `mdc-encyclopedia catalog` commands follow the existing `@cli.command()` pattern. |

## Feature-by-Feature Stack Analysis

### 1. RSS/Atom Feed (FEED-01/02/03)

**Recommendation: Use `xml.etree.ElementTree` (stdlib), NOT feedgen.**

| Option | Verdict | Reason |
|--------|---------|--------|
| xml.etree.ElementTree | USE THIS | Zero dependencies. Atom 1.0 is simple XML. ~80 lines of Python. No C extensions to compile. |
| feedgen (python-feedgen) | AVOID | Requires `lxml` (C extension, ~30MB, compilation issues on some platforms) and `python-dateutil`. Last release Dec 2023, maintenance status inactive. Massive overkill for a feed with 3 entry types (added/removed/schema_changed). |
| Jinja2 Atom template | POSSIBLE BUT WORSE | Would need `autoescape=False` for XML output, losing Jinja2's XSS protection globally or requiring a separate Environment. ElementTree is purpose-built for XML generation. |

**Implementation approach:**
```python
# src/mdc_encyclopedia/feed/generator.py
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ATOM_NS = "http://www.w3.org/2005/Atom"

def generate_atom_feed(changes: list[dict], site_url: str, jurisdiction: str) -> str:
    """Generate Atom 1.0 feed XML from change records."""
    ET.register_namespace("", ATOM_NS)
    feed = ET.Element(f"{{{ATOM_NS}}}feed")
    # ... title, id, updated, entries from changes table
    return ET.tostring(feed, encoding="unicode", xml_declaration=True)
```

**Feed output location:** `site/feed.xml` (Atom 1.0), linked from HTML `<head>` with `<link rel="alternate" type="application/atom+xml">`.

**Why Atom over RSS 2.0:** Atom is a proper IETF standard (RFC 4287) with unambiguous semantics. RSS 2.0 has conflicting interpretations of fields like `pubDate` vs `dc:date`. All modern feed readers support both. Atom's `<updated>` and `<id>` semantics map cleanly to our change detection timestamps and dataset IDs.

### 2. JSON/CSV Enriched Export (EXPORT-01/02)

**Recommendation: Use `json` (stdlib) and `csv.DictWriter` (stdlib). No new deps.**

**JSON export:**
```python
# Already have build_site_data() returning enriched dataset list
# Export is: json.dumps(datasets, indent=2, ensure_ascii=False)
```

**CSV export:**
```python
import csv

EXPORT_FIELDS = [
    "id", "title", "description", "ai_description", "category",
    "publisher", "department", "format", "updated_at", "created_at",
    "letter_grade", "composite_score", "civic_relevance",
    "use_cases", "keywords", "source_url", "download_url",
    "jurisdiction",  # NEW for v1.1
]
```

**Output locations:** `site/catalog.json` and `site/catalog.csv`, linked from homepage and about page.

**Design decision:** Export the fully enriched view (datasets + enrichments + audit scores joined), not raw tables. Users downloading the catalog want the value-added data, not the raw metadata.

### 3. AI Field-Level Descriptions (FIELD-01/02)

**Recommendation: Extend existing Anthropic SDK usage. No new deps.**

**What changes:**
- New Pydantic model `FieldEnrichmentResult` in `enrichment/models.py`
- New prompt in `enrichment/prompts.py` (bump to PROMPT_VERSION v2.0)
- New DB column `columns.ai_description` or new table `field_enrichments`
- Filter to B+ datasets only (composite_score >= 0.8 in audit_scores)

**Schema approach -- add column (preferred over new table):**
```sql
-- Schema V3 upgrade
ALTER TABLE columns ADD COLUMN ai_description TEXT;
```
Using `ALTER TABLE ADD COLUMN` is simpler than a new table and avoids JOINs. SQLite supports this cleanly. The `columns` table already stores field metadata -- an AI description is just another attribute of a column.

**Cost model:** Field enrichment sends column names + types + dataset context to Claude. Estimated ~200 input tokens per dataset (column list is compact), ~50 output tokens per field. For B+ datasets (~100-150 datasets with 10-30 fields each), total cost estimate: $0.50-$2.00 with Haiku 4.5.

**Structured output pattern (same as v1.0):**
```python
class FieldDescription(pydantic.BaseModel):
    column_name: str
    description: str  # Plain-English, 1 sentence

class FieldEnrichmentResult(pydantic.BaseModel):
    fields: list[FieldDescription]
```

### 4. Multi-Jurisdiction ArcGIS Hub (MULTI-01/02/03)

**Recommendation: Parameterize the existing hub_client.py. No new deps.**

**Verified portal endpoints (all use identical OGC API Records):**

| Jurisdiction | Hub URL | API Endpoint | Datasets | Confidence |
|-------------|---------|-------------|----------|------------|
| Miami-Dade County | `https://opendata.miamidade.gov` | `/api/search/v1/collections/dataset/items` | 575 | HIGH (live verified) |
| Broward County | `https://geohub-bcgis.opendata.arcgis.com` | `/api/search/v1/collections/dataset/items` | 83 | HIGH (live verified) |
| City of Miami | `https://datahub-miamigis.opendata.arcgis.com` | `/api/search/v1/collections/dataset/items` | 83 | HIGH (live verified) |

**All three portals return identical GeoJSON FeatureCollection responses** with the same property keys (`title`, `description`, `categories`, `tags`, `created`, `modified`, `type`, `url`). The existing `normalizer.normalize_hub_dataset()` function will work without modification for Broward and City of Miami data.

**Key architecture change:** Replace the hardcoded `HUB_BASE_URL = "https://opendata.miamidade.gov"` in `hub_client.py` with a jurisdiction configuration:

```python
JURISDICTIONS = {
    "miami-dade": {
        "name": "Miami-Dade County",
        "hub_url": "https://opendata.miamidade.gov",
        "source_portal": "arcgis_hub_mdc",
    },
    "broward": {
        "name": "Broward County",
        "hub_url": "https://geohub-bcgis.opendata.arcgis.com",
        "source_portal": "arcgis_hub_broward",
    },
    "miami-city": {
        "name": "City of Miami",
        "hub_url": "https://datahub-miamigis.opendata.arcgis.com",
        "source_portal": "arcgis_hub_miami_city",
    },
}
```

**Important: City of Miami also has a Socrata portal** at `data.miamigov.com` (separate from the ArcGIS Hub). This is OUT OF SCOPE for v1.1. The ArcGIS Hub portal at `datahub-miamigis.opendata.arcgis.com` contains the GIS datasets. Adding Socrata support would require a completely different API client.

**DB impact:** The `datasets.source_portal` column already exists and differentiates data sources. The `source_url` will naturally differ per jurisdiction. No schema change needed for multi-jurisdiction storage -- just different `source_portal` values.

**CLI change:** Add `--jurisdiction` option to `pull` command:
```bash
mdc-encyclopedia pull                    # Miami-Dade only (default, backward compat)
mdc-encyclopedia pull --jurisdiction all  # All three
mdc-encyclopedia pull --jurisdiction broward  # Broward only
```

**Deduplication concern:** Datasets shared across jurisdictions (e.g., FEMA flood zones published by both Miami-Dade and Broward) will have DIFFERENT dataset IDs on each portal. They are separate records. Title-based dedup detection already exists (`detect_duplicate_titles`) and will flag cross-jurisdiction title collisions for human review. No code change needed.

## What NOT to Add

| Avoid | Why | Do Instead |
|-------|-----|------------|
| feedgen / python-feedgen | Pulls in lxml (heavy C dependency, ~30MB). Inactive maintenance. Atom XML generation is ~80 lines with stdlib. | `xml.etree.ElementTree` |
| lxml | C extension requiring compilation. Adds platform-specific build issues (Windows, ARM, Alpine Linux). Not needed for simple Atom feed generation. | `xml.etree.ElementTree` |
| pandas | Tempting for CSV/JSON export, but `csv.DictWriter` and `json.dumps` handle the export trivially. Pandas adds ~30MB for zero benefit here. | `csv` + `json` (stdlib) |
| sodapy | Only covers Socrata Consumer API. City of Miami's Socrata portal is out of scope for v1.1. | N/A -- not needed |
| python-dateutil | feedgen's dependency. Not needed since `datetime.fromisoformat()` (Python 3.7+) and `datetime.isoformat()` handle all our timestamp needs. Already used throughout codebase. | `datetime` (stdlib) |
| pydantic (new install) | Already available as a transitive dependency of `anthropic` SDK. No separate install needed for `FieldEnrichmentResult` model. | Import from existing anthropic dependency chain |
| aiohttp / async patterns | Three jurisdictions at 1 req/sec each = ~15 min total sequential pull time. Async would let us hit 3 portals in parallel (5 min) but adds complexity. Sequential is fine for weekly CI runs. Consider async only if pull time becomes a user complaint. | Sequential httpx with `time.sleep(1)` per portal |

## Schema Changes Required (v3)

```sql
-- SCHEMA_V3_UPGRADE (in db.py)

-- Add AI description column to existing columns table
ALTER TABLE columns ADD COLUMN ai_description TEXT;

-- Add jurisdiction column to datasets for filtering
-- (source_portal already serves this purpose, but a human-readable
-- jurisdiction name is useful for templates)
ALTER TABLE datasets ADD COLUMN jurisdiction TEXT DEFAULT 'Miami-Dade County';

-- Update PRAGMA
-- PRAGMA user_version=3;
```

**Migration strategy:** Same pattern as V1->V2. `ALTER TABLE ADD COLUMN` is non-destructive and preserves existing data. SQLite handles this atomically.

## pyproject.toml Changes

```toml
# NO changes to [project.dependencies] needed!
# All v1.1 features use stdlib + existing deps.

# The only change is version bump:
[project]
version = "1.1.0"
```

## Integration Points Summary

| New Feature | Touches These Existing Files | New Files |
|------------|------------------------------|-----------|
| Atom Feed | `db.py` (query changes), `site/generator.py` (render feed), CLI (`feed` command) | `feed/generator.py` |
| JSON/CSV Export | `site/context.py` (export data builder), `site/generator.py` (write files), CLI (`catalog` command) | None (extend existing) |
| Field Descriptions | `enrichment/models.py` (new model), `enrichment/prompts.py` (v2 prompt), `enrichment/client.py` (new function), `db.py` (schema v3 + queries), CLI (`enrich --fields` flag) | None (extend existing) |
| Multi-Jurisdiction | `ingestion/hub_client.py` (parameterize URL), `ingestion/normalizer.py` (jurisdiction in source_url), `db.py` (schema v3), CLI (`--jurisdiction` option), `site/context.py` (jurisdiction filter), templates (jurisdiction badge/filter) | `config/jurisdictions.py` or constants in hub_client.py |

## Version Compatibility

No new packages, so no new compatibility concerns. The existing stack (all verified in v1.0 research) remains valid.

The only consideration: `ALTER TABLE ADD COLUMN` is supported in all SQLite versions shipped with Python 3.10+ (SQLite 3.35+). Python 3.12 ships SQLite 3.41+. No issue.

## Sources

- [PyPI: feedgen](https://pypi.org/project/feedgen/) -- v1.0.0, Dec 2023. Requires lxml + python-dateutil. Maintenance inactive. HIGH confidence (verified).
- [GitHub: python-feedgen](https://github.com/lkiesow/python-feedgen) -- setup.py confirms `install_requires=['lxml', 'python-dateutil']`. HIGH confidence (source code verified).
- [Python xml.etree.ElementTree docs](https://docs.python.org/3/library/xml.etree.elementtree.html) -- XML generation API. HIGH confidence (official stdlib docs).
- [Python csv module docs](https://docs.python.org/3/library/csv.html) -- DictWriter API. HIGH confidence (official stdlib docs).
- [Broward County GeoHub](https://geohub-bcgis.opendata.arcgis.com/) -- ArcGIS Hub portal confirmed. HIGH confidence (live verified, 83 datasets).
- [City of Miami Open Data GIS](https://datahub-miamigis.opendata.arcgis.com/) -- ArcGIS Hub portal confirmed. HIGH confidence (live verified, 83 datasets).
- [Miami-Dade Open Data Hub](https://opendata.miamidade.gov/) -- Existing portal. HIGH confidence (live verified, 575 datasets).
- Broward API endpoint `https://geohub-bcgis.opendata.arcgis.com/api/search/v1/collections/dataset/items` -- returns GeoJSON FeatureCollection, numberMatched=83. HIGH confidence (live API call).
- City of Miami API endpoint `https://datahub-miamigis.opendata.arcgis.com/api/search/v1/collections/dataset/items` -- returns GeoJSON FeatureCollection, numberMatched=83. HIGH confidence (live API call).
- [City of Miami Socrata portal](https://data.miamigov.com/) -- Separate Socrata-based portal, NOT ArcGIS Hub. Out of scope for v1.1. MEDIUM confidence (DNS resolution failed during research but confirmed via Socrata dev docs).
- [Socrata Developer Portal](https://dev.socrata.com/foundry/data.miamigov.com/usdv-safk) -- Confirms data.miamigov.com is Socrata. MEDIUM confidence.

---
*Stack research for: MDC Open Data Encyclopedia v1.1*
*Researched: 2026-02-26*
*Key finding: Zero new dependencies needed. All four features build on stdlib + existing stack.*
