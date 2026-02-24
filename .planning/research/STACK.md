# Stack Research

**Domain:** Open data catalog/encyclopedia (Python CLI + static site generator)
**Project:** Miami-Dade County Open Data Encyclopedia
**Researched:** 2026-02-24
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Python | 3.12+ | Runtime | Project constraint. 3.12 is widely deployed, stable, and supported through 2028. Avoid 3.13+ unless needed -- 3.12 has the best library compat today. | HIGH (official docs) |
| Click | 8.3.1 | CLI framework | The standard for Python CLIs. Groups/subcommands map directly to `mdc-encyclopedia pull`, `enrich`, `audit`, etc. Used by sqlite-utils itself, so it's a natural fit. Decorator-based API keeps command definitions readable. | HIGH (Context7 + PyPI) |
| sqlite-utils | 3.39 | Database layer | Simon Willison's library wraps SQLite with a Pythonic API: auto-schema from dicts, built-in FTS5 support, upsert, and CLI companion. Eliminates raw SQL for 90% of operations. This is THE library for "SQLite as application database" in Python. | HIGH (Context7 + PyPI) |
| Jinja2 | 3.1.6 | HTML templating | Pallets ecosystem (same as Click). Battle-tested for static site generation. Template inheritance handles layout/page hierarchy cleanly. No competing option worth considering. | HIGH (PyPI verified) |
| Anthropic SDK | >=0.83.0 | AI enrichment | Official Python SDK with sync/async clients, streaming, and Message Batches API. Batches API is critical: enrich hundreds of datasets at 50% cost discount with async batch processing. Pin to `>=0.83` for latest model support. | HIGH (Context7 + PyPI) |
| httpx | 0.28.1 | HTTP client | Replaces `requests` as the modern Python HTTP client. Sync and async with the same API, HTTP/2 support, and connection pooling. For this project, use **sync mode** -- async is unnecessary for sequential paginated API calls with rate limiting. Drop-in `requests` compatibility means familiar API. | HIGH (PyPI verified) |
| Rich | 14.3.3 | Terminal output | Progress bars for catalog pulls, formatted tables for `stats`, colored output for `audit` results. Project constraint -- already specified. Best-in-class terminal formatting. | HIGH (PyPI verified) |
| lunr.py | 0.8.0 | Search index generation | Python implementation of Lunr.js. Build the search index at export time in Python, serialize to JSON, load client-side with Lunr.js. Avoids Node.js dependency in the build pipeline. ~1000 dataset limit is fine for county-level catalog. | MEDIUM (PyPI + GitHub) |

### Client-Side Technologies (Static Site)

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Lunr.js | 2.3.9 | Client-side search | Pre-built index from lunr.py loads instantly in browser. BM25 ranking, stemming, field boosting. Better real-time search performance than Fuse.js (faster per-query after index loads). Perfect for "type and filter" UX. | MEDIUM (web research) |
| Vanilla JS | ES6+ | Interactivity | No framework needed. Search, filtering, and category browsing are simple DOM operations. Zero build step, zero bundle size concerns. Project constraint -- already specified. | HIGH (project decision) |
| Vanilla CSS | CSS3 | Styling | Custom properties for MDC branding (#003366, white, amber). CSS Grid for layout. No build step. Tailwind/Bootstrap are overkill for a catalog site with consistent page templates. | HIGH (project decision) |

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| python-slugify | 8.0.4 | URL-safe slugs | Generate clean filenames for dataset pages (`/datasets/miami-dade-property-data/index.html`). Handles unicode in dataset names. | HIGH (PyPI) |
| python-dotenv | 1.0.1 | Environment variables | Load `.env` file for `ANTHROPIC_API_KEY` during local development. Not needed in CI (GitHub Secrets). | HIGH (standard practice) |
| pytest | 9.0.2 | Testing | Unit tests for API parsing, enrichment prompt construction, SQLite operations. Required Python >=3.10 aligns with project. | HIGH (PyPI) |
| pytest-httpx | 0.35.0 | HTTP mocking | Mock Socrata and ArcGIS API responses in tests without hitting real endpoints. Integrates cleanly with httpx. | MEDIUM (PyPI) |

### Development Tools

| Tool | Purpose | Notes | Confidence |
|------|---------|-------|------------|
| Hatchling | 1.29.0 | Build backend | Modern, fast Python build backend. Used by uv, recommended by Python Packaging Authority. Handles `pyproject.toml` entry points for `mdc-encyclopedia` CLI command. | HIGH (PyPI + packaging docs) |
| Ruff | Latest | Linter + formatter | Replaces flake8, isort, and black in one tool. Sub-second execution. Industry standard in 2025+. | HIGH (ecosystem consensus) |
| uv | Latest | Package manager | 10-100x faster than pip. Handles venv creation, dependency resolution, and lockfiles. Use for local dev. Falls back to pip in CI if needed. | MEDIUM (ecosystem trend) |

## Installation

```bash
# Create project with pyproject.toml, then install in dev mode:
pip install -e ".[dev]"

# Or with uv (recommended for local dev):
uv pip install -e ".[dev]"
```

### pyproject.toml dependency groups

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mdc-encyclopedia"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "click>=8.3.1",
    "sqlite-utils>=3.39",
    "httpx>=0.28.1",
    "jinja2>=3.1.6",
    "anthropic>=0.83.0",
    "rich>=14.0",
    "lunr>=0.8.0",
    "python-slugify>=8.0",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=9.0",
    "pytest-httpx>=0.35",
    "ruff>=0.9",
]

[project.scripts]
mdc-encyclopedia = "mdc_encyclopedia.cli:cli"
```

## Alternatives Considered

| Category | Recommended | Alternative | Why Not Alternative |
|----------|-------------|-------------|---------------------|
| HTTP client | httpx | requests | requests lacks async option if needed later, no HTTP/2, no connection pooling by default. httpx has 99% API compatibility with requests but is strictly more capable. |
| HTTP client | httpx | sodapy | sodapy wraps the SODA *Consumer* API (for querying dataset rows). We need the *Discovery* API (catalog metadata) and *Views* API (column metadata), which sodapy does not cover. Raw HTTP calls to the Discovery API are simpler than wrapping sodapy. |
| HTTP client | httpx | aiohttp | aiohttp is async-only. This project is sync-first (sequential API calls with rate limiting). httpx gives sync now, async later if needed. |
| Database | sqlite-utils | SQLAlchemy | SQLAlchemy is an ORM for relational databases at scale. Massive overkill for a single-file SQLite catalog. sqlite-utils is purpose-built for this exact use case (dict-in, table-out, FTS built-in). |
| Database | sqlite-utils | raw sqlite3 | sqlite3 stdlib works but requires manual schema management, manual FTS setup, no upsert helpers. sqlite-utils eliminates hundreds of lines of boilerplate. |
| CLI | Click | Typer | Typer builds on Click with type hints. Adds a dependency for marginal benefit. Click is more mature, better documented, and sqlite-utils already uses it (consistent ecosystem). |
| CLI | Click | argparse | argparse is stdlib but verbose for multi-command CLIs. Click's decorator model is cleaner for `pull`, `enrich`, `audit`, `diff`, `export`, `serve`, `stats` subcommands. |
| Search | Lunr.js | Fuse.js | Fuse.js is fuzzy-search focused -- slower per-query, no pre-built index from Python. Lunr.js has lunr.py for Python-side index building, BM25 ranking, and faster real-time filtering. Fuse.js better for small unstructured data; Lunr.js better for structured catalog search. |
| Search | Lunr.js | Algolia/Typesense | External search services require a backend or API key exposed client-side. Violates static-site constraint. |
| Templating | Jinja2 | Mako | Mako is faster but less readable. Jinja2's template inheritance model is better for page layouts. Click ecosystem alignment (Pallets). |
| Build backend | Hatchling | setuptools | setuptools works but requires more configuration. Hatchling is zero-config for pure Python projects, faster, and the modern default. |
| Build backend | Hatchling | Poetry | Poetry couples build backend with dependency manager. Hatchling is decoupled -- works with pip, uv, or any PEP 517 frontend. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| sodapy | Only covers SODA Consumer API (querying rows). Does NOT support the Discovery API (`/api/catalog/v1`) needed for catalog metadata, nor the Views API (`/api/views/{id}.json`) for column metadata. Using it would still require raw HTTP for the core functionality. | httpx directly against Discovery API and Views API |
| SQLAlchemy | ORM overhead for a single-file SQLite database with ~5 tables. Migration system, session management, and model definitions are unnecessary complexity. | sqlite-utils (dict-based, schema-inferred, FTS built-in) |
| Flask/FastAPI | No web server needed. This is a CLI tool that generates static files. Adding a web framework violates the static-site constraint. | Click CLI + `python -m http.server` for local preview |
| Node.js build pipeline | Adding Node as a build dependency for Lunr.js index generation is unnecessary. lunr.py generates compatible indexes in pure Python. | lunr.py (Python-native index building) |
| Pandas | Tempting for data manipulation, but unnecessary. sqlite-utils handles data insertion/querying. Adding a 30MB dependency for what amounts to list-of-dict operations is wasteful. | sqlite-utils + stdlib collections |
| CKAN/Datasette | Full data catalog platforms. CKAN requires Postgres + Solr + Redis. Datasette requires a running server. Both violate the static-site, zero-server constraint. | Custom static site generation with Jinja2 |
| Pelican/Hugo/Jekyll | Static site generators with their own conventions, themes, and plugin ecosystems. The catalog's page structure is unique (dataset pages, category pages, quality reports) and doesn't map to blog-post models. Custom Jinja2 templates are simpler. | Jinja2 templates + custom Python export script |

## Stack Patterns

**For API rate limiting (Socrata/ArcGIS 1 req/sec):**
- Use `time.sleep(1)` between requests in sync httpx. Simple and correct.
- Do NOT use async + semaphore. The bottleneck is the rate limit, not concurrency. Async adds complexity with zero throughput benefit at 1 req/sec.

**For AI enrichment (hundreds of datasets):**
- Use the Anthropic **Message Batches API** for bulk enrichment. Submit all unenriched datasets as a batch, poll for completion, process results. 50% cost reduction vs. individual calls.
- For `--dry-run` and `--resume`, query the SQLite database for unenriched datasets, show count and cost estimate, then submit only those.
- Use `claude-sonnet-4-5-20250929` (not Opus) for enrichment. Sufficient quality for descriptions/keywords at ~10x lower cost.

**For static site search index:**
- Build index in Python at export time using lunr.py. Serialize to `search-index.json`.
- Load pre-built index in browser with `lunr.Index.load()`. No client-side indexing needed.
- Include dataset title, AI-generated description, keywords, department, and category in index fields. Boost title 10x, keywords 5x.

**For GitHub Actions weekly refresh:**
- `pip install .` in CI (not `pip install -e .`). Installs the package properly.
- Run `mdc-encyclopedia pull && mdc-encyclopedia audit && mdc-encyclopedia export` as the CI pipeline.
- Conditionally run `mdc-encyclopedia enrich --new-only` only if `ANTHROPIC_API_KEY` secret is set.

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| Click 8.3.1 | Python >=3.10 | Project requires 3.12+, so no issue |
| sqlite-utils 3.39 | Python >=3.8 | Broad compat, no issues |
| httpx 0.28.1 | Python >=3.8 | Broad compat, no issues |
| Jinja2 3.1.6 | Python >=3.7 | Broad compat, no issues |
| anthropic >=0.83.0 | Python >=3.9 | Requires >=3.9, project targets 3.12+ |
| Rich 14.3.3 | Python >=3.8 | Broad compat, no issues |
| lunr 0.8.0 | Python >=3.7 | Broad compat, no issues |
| pytest 9.0.2 | Python >=3.10 | Project requires 3.12+, so no issue |
| hatchling 1.29.0 | Python >=3.10 | Project requires 3.12+, so no issue |

**No known cross-package conflicts.** All packages use standard dependencies. The sqlite-utils + Click pairing is well-tested (sqlite-utils itself uses Click).

## Sources

- [sqlite-utils Context7 docs](/simonw/sqlite-utils) -- FTS5 API, insert_all, enable_fts verified. HIGH confidence.
- [Click Context7 docs](/pallets/click) -- Group/command pattern, options/arguments verified. HIGH confidence.
- [Anthropic SDK Context7 docs](/anthropics/anthropic-sdk-python) -- Message Batches API, streaming verified. HIGH confidence.
- [PyPI: sqlite-utils](https://pypi.org/project/sqlite-utils/) -- Version 3.39, Nov 2025. HIGH confidence.
- [PyPI: click](https://pypi.org/project/click/) -- Version 8.3.1, Nov 2025. HIGH confidence.
- [PyPI: anthropic](https://pypi.org/project/anthropic/) -- Version 0.83.0, Feb 2026. HIGH confidence.
- [PyPI: httpx](https://pypi.org/project/httpx/) -- Version 0.28.1, Dec 2024. HIGH confidence.
- [PyPI: Jinja2](https://pypi.org/project/Jinja2/) -- Version 3.1.6, Mar 2025. HIGH confidence.
- [PyPI: Rich](https://pypi.org/project/rich/) -- Version 14.3.3, Feb 2026. HIGH confidence.
- [PyPI: lunr](https://pypi.org/project/lunr/) -- Version 0.8.0, Mar 2025. HIGH confidence.
- [PyPI: pytest](https://pypi.org/project/pytest/) -- Version 9.0.2, Dec 2025. HIGH confidence.
- [PyPI: hatchling](https://pypi.org/project/hatchling/) -- Version 1.29.0, Feb 2026. HIGH confidence.
- [PyPI: python-slugify](https://pypi.org/project/python-slugify/) -- Version 8.0.4, Feb 2024. HIGH confidence.
- [Socrata Discovery API docs](https://dev.socrata.com/docs/other/discovery) -- Catalog endpoint, pagination. MEDIUM confidence (docs may lag API).
- [Lunr.js pre-building guide](https://lunrjs.com/guides/index_prebuilding.html) -- Index serialization confirmed. MEDIUM confidence.
- [Fuse.js vs Lunr.js comparisons](https://wiki.gpii.net/w/Technology_Evaluation_-_Static_Site_Search) -- Performance tradeoffs. MEDIUM confidence (community sources).
- [Python build backends 2025](https://medium.com/@dynamicy/python-build-backends-in-2025-what-to-use-and-why-uv-build-vs-hatchling-vs-poetry-core-94dd6b92248f) -- Hatchling recommendation. MEDIUM confidence (blog post).
- [Socrata sodapy](https://github.com/afeld/sodapy) -- Confirmed covers Consumer API only, not Discovery API. MEDIUM confidence.

---
*Stack research for: Miami-Dade County Open Data Encyclopedia*
*Researched: 2026-02-24*
