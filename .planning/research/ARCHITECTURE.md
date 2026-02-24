# Architecture Research

**Domain:** Open data catalog / encyclopedia with AI enrichment (static site output)
**Researched:** 2026-02-24
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLI Layer (Click)                           │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌───────┐ │
│  │  pull  │ │ enrich │ │ audit  │ │  diff  │ │ export │ │ serve │ │
│  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬───┘ │
│      │          │          │          │          │          │      │
├──────┴──────────┴──────────┴──────────┴──────────┴──────────┴──────┤
│                      Service / Logic Layer                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │ API Clients  │ │  Enrichment  │ │  Site Builder │               │
│  │ (Socrata,    │ │  Engine      │ │  (Jinja2 +   │               │
│  │  ArcGIS Hub) │ │  (Claude)    │ │   Lunr.js)   │               │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘               │
│         │                │                │                        │
├─────────┴────────────────┴────────────────┴────────────────────────┤
│                      Storage Layer (SQLite)                        │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ datasets │  │ columns      │  │ enriched │  │ audit_log    │   │
│  └──────────┘  └──────────────┘  └──────────┘  └──────────────┘   │
├────────────────────────────────────────────────────────────────────┤
│                      Output Layer (Static Files)                   │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │ HTML     │  │ search.json  │  │ CSS/JS       │                 │
│  │ pages    │  │ (Lunr index) │  │ assets       │                 │
│  └──────────┘  └──────────────┘  └──────────────┘                 │
└────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| CLI Layer | User-facing commands, argument parsing, progress display | Click + Rich for terminal output |
| Socrata Client | Enumerate all datasets from Discovery API, fetch column metadata per dataset | `httpx` or `requests` with pagination loop; 1 req/sec rate limit |
| ArcGIS Hub Client | Enumerate all datasets from Hub API v3, normalize to common schema | `httpx` or `requests` with page/per_page pagination |
| Storage Layer | Persist all metadata, enrichments, and audit results; support diffing | SQLite via `sqlite-utils` (single file, no server) |
| Enrichment Engine | Generate plain-English descriptions, use cases, keywords via Claude | Anthropic Python SDK; batch-aware with resume/dry-run |
| Audit Engine | Score datasets for staleness, emptiness, missing descriptions | Pure Python logic reading from SQLite |
| Diff Engine | Compare current pull to previous pull, detect new/removed/changed | SQL queries against versioned snapshots in SQLite |
| Site Builder | Render HTML from SQLite data using Jinja2 templates, build search index | Jinja2 templates + Node.js Lunr.js index builder (or Python lunr) |
| Static Output | Deployable artifact: HTML pages, JSON search index, CSS/JS | Flat directory served by GitHub Pages |

## Recommended Project Structure

```
mdc-encyclopedia/
├── pyproject.toml              # Package config, entry points, dependencies
├── src/
│   └── mdc_encyclopedia/
│       ├── __init__.py
│       ├── cli.py              # Click command group (pull, enrich, audit, diff, export, serve)
│       ├── clients/
│       │   ├── __init__.py
│       │   ├── socrata.py      # Socrata Discovery API + per-dataset metadata
│       │   └── arcgis.py       # ArcGIS Hub API v3 client
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── db.py           # sqlite-utils DB initialization, schema, migrations
│       │   └── models.py       # Data classes / typed dicts for dataset, column, enrichment
│       ├── enrichment/
│       │   ├── __init__.py
│       │   ├── engine.py       # Orchestration: which datasets need enrichment, resume logic
│       │   ├── prompts.py      # Claude prompt templates (system + user)
│       │   └── cost.py         # Token estimation and cost preview
│       ├── audit/
│       │   ├── __init__.py
│       │   └── quality.py      # Staleness checks, completeness scoring, empty detection
│       ├── diff/
│       │   ├── __init__.py
│       │   └── changes.py      # Snapshot comparison: new, removed, schema changes
│       └── export/
│           ├── __init__.py
│           ├── builder.py      # Jinja2 rendering orchestration
│           ├── search.py       # Lunr.js JSON index generation
│           └── templates/      # Jinja2 HTML templates
│               ├── base.html
│               ├── index.html
│               ├── dataset.html
│               ├── category.html
│               ├── changes.html
│               └── quality.html
├── static/                     # CSS, JS, images (copied to output)
│   ├── style.css
│   ├── search.js              # Client-side Lunr.js search UI
│   └── favicon.ico
├── tests/
│   ├── test_clients.py
│   ├── test_storage.py
│   ├── test_enrichment.py
│   └── test_export.py
├── .github/
│   └── workflows/
│       └── weekly-refresh.yml  # GitHub Actions: pull + export (+ optional enrich)
└── data/                       # .gitignored — local SQLite DB lives here
    └── mdc_encyclopedia.db
```

### Structure Rationale

- **src/ layout:** Standard Python packaging convention. `mdc_encyclopedia` is the importable package; `cli.py` is the entry point registered via `pyproject.toml` console_scripts.
- **clients/:** Each API source is its own module because Socrata and ArcGIS have fundamentally different pagination, auth, and metadata schemas. Both normalize into the same storage models.
- **storage/:** Centralizes all database access. Every other component reads/writes through `db.py`, never directly constructing SQL. `sqlite-utils` handles schema creation and upserts.
- **enrichment/:** Isolated from clients and storage so it can be run independently (`enrich` command), supports resume (tracks enrichment status in DB), and can be skipped entirely in CI.
- **export/templates/:** Jinja2 templates live inside the package so they ship with `pip install`. The builder reads from SQLite, passes context to templates, writes HTML to an output directory.
- **data/:** Gitignored. The SQLite file is a local artifact, not committed. CI creates it fresh each run.

## Architectural Patterns

### Pattern 1: Pipeline-of-Commands (ETL Stages as CLI Subcommands)

**What:** Each CLI command (`pull`, `enrich`, `audit`, `diff`, `export`) represents one stage of an ETL pipeline. They are independently runnable but designed to execute in sequence.
**When to use:** Always. This is the core architecture.
**Trade-offs:** (+) Each stage is testable in isolation, debuggable independently, skippable in CI. (-) Requires SQLite as the shared state between stages -- but that is a feature, not a bug, because SQLite is the single source of truth.

**Example:**
```python
@click.group()
def cli():
    """MDC Open Data Encyclopedia CLI."""
    pass

@cli.command()
@click.option("--db", default="data/mdc_encyclopedia.db")
def pull(db):
    """Pull metadata from Socrata + ArcGIS Hub."""
    database = sqlite_utils.Database(db)
    socrata_datasets = socrata_client.fetch_all()
    arcgis_datasets = arcgis_client.fetch_all()
    storage.upsert_datasets(database, socrata_datasets + arcgis_datasets)
    click.echo(f"Pulled {len(socrata_datasets) + len(arcgis_datasets)} datasets.")

@cli.command()
@click.option("--db", default="data/mdc_encyclopedia.db")
@click.option("--dry-run", is_flag=True)
@click.option("--resume", is_flag=True, default=True)
def enrich(db, dry_run, resume):
    """AI-enrich datasets with Claude."""
    # ...
```

### Pattern 2: Normalize-at-Ingestion (Common Schema from Heterogeneous Sources)

**What:** Socrata and ArcGIS return different JSON shapes. Each client normalizes its response into a common `DatasetRecord` dataclass before storage. The rest of the system never knows or cares which portal a dataset came from.
**When to use:** Whenever ingesting from multiple API sources with different schemas.
**Trade-offs:** (+) Downstream code (enrichment, audit, export) only deals with one schema. (-) Normalization logic must be maintained per source.

**Example:**
```python
@dataclass
class DatasetRecord:
    id: str                     # Unique across both portals
    source: str                 # "socrata" or "arcgis"
    name: str
    description: str | None
    category: str | None
    tags: list[str]
    owner_department: str | None
    created_at: str
    updated_at: str
    record_count: int | None
    columns: list[ColumnRecord]
    portal_url: str             # Direct link back to source portal
```

### Pattern 3: Baked Data (SQLite as Build Artifact)

**What:** Inspired by Simon Willison's Datasette ecosystem. The SQLite database is a portable, self-contained build artifact. The static site is "baked" from it. The DB can be inspected locally with any SQLite tool (DB Browser, `sqlite-utils`, `datasette`).
**When to use:** Any project where data is collected/processed offline and then published as static output.
**Trade-offs:** (+) Single file, works everywhere, no server needed, inspectable. (-) Not suitable for real-time writes (not needed here).

## Data Flow

### Primary Pipeline Flow

```
[Socrata Discovery API]     [ArcGIS Hub API v3]
    │ (paginate, 100/req)       │ (paginate, page/per_page)
    │ + per-dataset /views      │
    ▼                           ▼
┌─────────────────────────────────────┐
│  Normalize → DatasetRecord objects  │  ← clients/ layer
└──────────────────┬──────────────────┘
                   │ upsert
                   ▼
┌─────────────────────────────────────┐
│  SQLite DB (datasets, columns)      │  ← storage/ layer
└──────────────────┬──────────────────┘
                   │ read unenriched
                   ▼
┌─────────────────────────────────────┐
│  Claude API enrichment              │  ← enrichment/ layer
│  (descriptions, use cases, tags)    │
│  Write back → enrichments table     │
└──────────────────┬──────────────────┘
                   │ read all
                   ▼
┌─────────────────────────────────────┐
│  Audit engine                       │  ← audit/ layer
│  (staleness, completeness, quality) │
│  Write back → audit_scores table    │
└──────────────────┬──────────────────┘
                   │ read all
                   ▼
┌─────────────────────────────────────┐
│  Diff engine                        │  ← diff/ layer
│  (compare snapshots: new/removed/   │
│   schema changes)                   │
│  Write back → changes table         │
└──────────────────┬──────────────────┘
                   │ read all
                   ▼
┌─────────────────────────────────────┐
│  Static Site Builder                │  ← export/ layer
│  Jinja2 templates → HTML pages      │
│  Build Lunr.js JSON search index    │
│  Copy CSS/JS assets                 │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│  Output directory (docs/ or _site/) │
│  → GitHub Pages / any static host   │
└─────────────────────────────────────┘
```

### Key Data Flows

1. **Ingestion flow:** API responses (JSON) -> normalized DatasetRecord -> SQLite `datasets` and `columns` tables. Socrata requires two calls per dataset (Discovery API for catalog + `/api/views/{id}.json` for column metadata). ArcGIS returns columns (called `fields`) in the dataset response itself.

2. **Enrichment flow:** Read unenriched dataset rows from SQLite -> construct Claude prompt with dataset metadata -> call Anthropic API -> parse structured response -> write to `enrichments` table. Resume support: query for datasets where `enrichment_status IS NULL OR enrichment_status = 'pending'`.

3. **Export flow:** Read all tables (datasets + enrichments + audit_scores + changes) via SQL joins -> pass as context to Jinja2 templates -> render HTML files + build search JSON index -> write to output directory.

4. **CI/CD flow (GitHub Actions):** Checkout -> `mdc-encyclopedia pull` -> `mdc-encyclopedia audit` -> `mdc-encyclopedia diff` -> (optionally) `mdc-encyclopedia enrich` -> `mdc-encyclopedia export` -> deploy output directory to GitHub Pages.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-500 datasets | Current architecture handles this trivially. Sequential API calls, single-threaded enrichment, full-site rebuild on every export. |
| 500-2,000 datasets | May want concurrent API calls (asyncio + httpx) for pull speed. Enrichment benefits from Anthropic Batch API (50% cost reduction). Lunr.js index stays under 5MB -- fine for client-side. |
| 2,000-10,000 datasets | Search index may exceed comfortable download size. Consider Fuse.js (lighter index) or server-side search. Enrichment cost becomes material (~$5-20 per full run). Incremental export (only re-render changed pages) becomes worthwhile. |
| 10,000+ datasets | Unlikely for a single county. If reached, split search index by category, use service worker for caching, consider paginated HTML generation. |

### Scaling Priorities

1. **First bottleneck:** API pull speed. Socrata requires N+1 calls (1 catalog page per 100 datasets + 1 per-dataset column call). At 500 datasets, that is ~505 requests at 1/sec = ~8 minutes. Mitigation: cache aggressively, only re-fetch changed datasets on subsequent runs.
2. **Second bottleneck:** Enrichment cost/time. At $0.003-0.01 per dataset (Haiku/Sonnet), 500 datasets costs $1.50-5.00. Use `--resume` to avoid re-enriching, and Batch API for bulk runs.

## Anti-Patterns

### Anti-Pattern 1: Coupling API Client Logic to Storage

**What people do:** Write Socrata API calls directly inside the CLI command handler, with `sqlite_utils.Database` imports in the client module.
**Why it's wrong:** Cannot test API parsing without a database. Cannot swap storage layer. Cannot add a new data source without touching storage code.
**Do this instead:** API clients return plain Python objects (dataclasses). Storage layer accepts those objects. CLI wires them together.

### Anti-Pattern 2: Building the Search Index in Python

**What people do:** Use a Python Lunr port to build the search index, avoiding Node.js entirely.
**Why it's wrong:** The Python `lunr` package exists but is less maintained than the canonical JS library. More importantly, the client-side search loads `lunr.js` anyway -- if the index was built with a different implementation, subtle incompatibilities can occur.
**Do this instead:** Build the search index with Node.js `lunr` at export time (a 10-line script). Or use the Python `lunr` library only if you verify version compatibility with the client-side `lunr.js` you ship. A pragmatic alternative: use Fuse.js, which takes raw JSON (no pre-built index needed), so the "build step" is just writing a JSON file from Python.

### Anti-Pattern 3: Storing Enrichments Inline with Dataset Metadata

**What people do:** Add AI-generated columns directly to the `datasets` table.
**Why it's wrong:** Enrichments are expensive to regenerate. If a `pull` overwrites the row, enrichments are lost. Enrichments have their own lifecycle (can be regenerated, versioned, reviewed).
**Do this instead:** Separate `enrichments` table with a foreign key to `datasets.id`. Pull can freely upsert `datasets` without touching enrichments. Enrichment status tracked independently.

### Anti-Pattern 4: Full Site Rebuild for One Dataset Change

**What people do:** Re-render every HTML page on every export, even if only 3 datasets changed.
**Why it's wrong:** At 500+ datasets, full rebuild takes noticeable time and generates unnecessary git churn in the Pages repo.
**Do this instead:** Track `last_modified` per dataset. On export, only re-render pages for datasets modified since last export. Always rebuild index pages (index, categories, changes, quality report) since they aggregate.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Socrata Discovery API | REST GET with pagination (`limit=100&offset=N`) | Rate limit: 1 req/sec. No auth required for public catalog. App token optional but recommended. |
| Socrata Views API | REST GET `/api/views/{id}.json` per dataset | Returns column metadata (name, type, description). Same rate limit. |
| ArcGIS Hub API v3 | REST GET with `page` and `per_page` params | Filter by domain: `?filter[source]=gis-mdc.opendata.arcgis.com`. Returns `fields` array with column metadata inline. |
| Anthropic Claude API | Python SDK `anthropic.Anthropic().messages.create()` | Use Haiku for cost efficiency (descriptions) or Sonnet for nuanced enrichment. Support Batch API for bulk. |
| GitHub Pages | Static file deployment via `gh-pages` branch or `/docs` folder | GitHub Actions pushes built site. No server-side logic. |
| GitHub Actions | Cron-triggered workflow (weekly) | `pull` -> `audit` -> `diff` -> `enrich` (optional) -> `export` -> deploy |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| CLI <-> Clients | Function calls returning dataclasses | CLI passes options (db path, rate limit); clients return `list[DatasetRecord]` |
| CLI <-> Storage | `sqlite-utils.Database` object passed as argument | All modules receive the DB handle from CLI; never create their own |
| CLI <-> Enrichment | Function calls with DB handle + options | Enrichment reads from DB, writes back to DB. CLI controls dry-run/resume flags |
| Storage <-> Export | Read-only SQL queries | Export never writes to DB. Reads joined views of datasets + enrichments + audits |
| Export <-> Static Output | File writes to output directory | Builder writes HTML/JSON/CSS. Serve command runs `python -m http.server` on output dir |

## Build Order (Dependency Chain)

Based on the component boundaries and data flow above, the recommended build order is:

```
Phase 1: Storage Layer + Models
   │      (schema, DB init, dataclasses — everything else depends on this)
   ▼
Phase 2: API Clients (Socrata + ArcGIS)
   │      (depends on: storage models for normalization target)
   ▼
Phase 3: CLI Skeleton + Pull Command
   │      (depends on: clients + storage — first end-to-end working pipeline)
   ▼
Phase 4: Audit + Diff Engines
   │      (depends on: storage with data from pull — pure logic, no external APIs)
   ▼
Phase 5: AI Enrichment Engine
   │      (depends on: storage with data — adds Claude API dependency)
   ▼
Phase 6: Static Site Builder (Jinja2 + Search Index)
   │      (depends on: storage with enrichments + audits — reads everything, writes HTML)
   ▼
Phase 7: GitHub Actions CI/CD
          (depends on: all commands working — orchestrates the full pipeline)
```

**Build order rationale:**
- Storage first because every other component reads/writes through it.
- Clients second because you need real data to test everything downstream.
- CLI + Pull third to establish the end-to-end "pull data into DB" loop early.
- Audit/Diff before enrichment because they are pure logic (no API cost, fast to iterate).
- Enrichment after audit because you may want audit scores to inform enrichment prompts.
- Export last because it consumes everything upstream.
- CI/CD last because it orchestrates commands that must already exist.

## Sources

- [Datasette Architecture (Architecture Notes)](https://architecturenotes.co/p/datasette-simon-willison) -- Datasette's "baked data" pattern, SQLite as deployment artifact, plugin architecture -- HIGH confidence
- [sqlite-utils (Simon Willison)](https://github.com/simonw/sqlite-utils) -- Python CLI + library for SQLite manipulation, schema inference from dicts -- HIGH confidence
- [Socrata Discovery API](https://dev.socrata.com/docs/other/discovery) -- Catalog enumeration endpoint, pagination at 100 results -- MEDIUM confidence (official docs sparse)
- [ArcGIS Open Data API (unofficial docs)](https://gist.github.com/haoliangyu/0d0abcccfd3b25beb8b7597b4b2fc497) -- Hub API v3 endpoints, pagination, metadata fields -- MEDIUM confidence (unofficial gist)
- [Lunr.js Pre-building Indexes](https://lunrjs.com/guides/index_prebuilding.html) -- Build-time index generation pattern with Node.js -- HIGH confidence
- [JKAN (Static Data Portal)](https://github.com/timwis/jkan) -- Jekyll-based static data catalog for GitHub Pages, proof that static data catalogs work -- HIGH confidence
- [Anthropic Batch Processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing) -- Message Batches API for 50% cost reduction on bulk enrichment -- HIGH confidence
- [Socrata Discovery API docs](https://dev.socrata.com/docs/other/discovery) -- Rate limits, pagination structure -- MEDIUM confidence
- [ArcGIS Hub Python API](https://github.com/Esri/hub-py) -- Official Python interface (heavyweight; raw HTTP preferred for our use case) -- MEDIUM confidence

---
*Architecture research for: Miami-Dade County Open Data Encyclopedia*
*Researched: 2026-02-24*
