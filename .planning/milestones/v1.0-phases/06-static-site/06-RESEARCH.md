# Phase 6: Static Site - Research

**Researched:** 2026-02-26
**Domain:** Static site generation from SQLite data using Python + Jinja2 templates with client-side search
**Confidence:** HIGH

## Summary

Phase 6 transforms the enriched SQLite catalog into a fully static HTML encyclopedia. The architecture is straightforward: Python reads from SQLite, renders Jinja2 templates to HTML files, and generates a JSON search index at build time. The browser loads pre-built HTML pages with a lightweight client-side search library for instant discovery.

The core stack is well-established: Jinja2 for templating (the standard in Python), lunr.py for generating a Lunr.js-compatible search index at build time, and python-slugify for URL-safe dataset identifiers. The site is pure static files -- no JavaScript framework, no build toolchain, no server-side runtime. Python's built-in `http.server` module handles local preview with zero dependencies.

**Primary recommendation:** Use Jinja2 template inheritance for a base layout, lunr.py to pre-build a Lunr.js search index during export, and vanilla JS for the search dropdown UI. Keep the generator as a Python module (`site/` subpackage) following the existing project pattern.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Search-first homepage: large search bar front and center with tagline above ("Every county dataset, explained in plain English")
- Instant dropdown search results as user types (like Spotlight/Algolia), top 5-8 matches
- Each search result shows: dataset title, 1-line AI description snippet, department tag
- Below search: 3 stat cards (total datasets, % described, new this week) plus a row of top category/department browse links
- No pagination on search dropdown -- click result to go to dataset page, or browse categories
- Modern civic tech aesthetic: clean, accessible, confident with generous whitespace and clear hierarchy
- Not government-institutional stuffy, not editorial/magazine -- professional startup feel applied to civic data
- MDC palette: #003366 (primary blue), white, amber for accents/highlights
- Compact list rows on browse pages: one dataset per row with title, 1-line description, department chip, quality dot
- Dense and scannable for 450+ datasets -- similar density to GitHub repo lists
- Not cards -- too much vertical space for this volume of data
- Letter grade badges: A, B, C, D, F with color coding (green through red) on both listing rows and detail pages
- Relative time label ("Updated 3 days ago") plus colored dot (green/yellow/red) for freshness
- Color based on staleness relative to expected update frequency from audit data

### Claude's Discretion
- Typography and font choices
- Exact spacing and card/row component sizing
- Search index library choice (Lunr.js vs Fuse.js)
- Dataset detail page section ordering and layout
- Navigation structure (top nav, sidebar, breadcrumbs)
- Category/browse page filtering UX
- "What Changed" page layout
- Data quality report page layout
- About/disclaimer page content structure
- Mobile responsive breakpoints and layout adjustments
- Empty state designs
- Error state handling

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SITE-01 | Full-text search via Lunr.js or Fuse.js with JSON index built at export time | lunr.py generates Lunr.js-compatible index at build time; Fuse.js alternative via JSON data file. Recommendation: Lunr.js for instant-as-you-type dropdown (faster per-search after indexing) |
| SITE-02 | Category/theme browse pages with dataset listings | Jinja2 template renders one HTML page per category; datasets grouped by category field from DB |
| SITE-03 | Individual dataset pages showing metadata, AI enrichment, columns, quality score, source link | Jinja2 template consuming joined dataset+enrichment+audit+columns data from SQLite |
| SITE-04 | Related datasets shown on each dataset page (tag/category overlap) | Pre-computed at export time by matching category + keywords; stored as list in template context |
| SITE-05 | Freshness indicators on dataset listings and detail pages | Relative time computed at export, staleness color derived from audit staleness score |
| SITE-06 | Filtering by format, publisher, and tag on browse pages | Client-side JS filtering on data attributes already in the HTML rows; no server needed |
| SITE-07 | "What Changed" page showing diff results between pulls | Jinja2 template rendering changes table data from SQLite changes table |
| SITE-08 | Data quality report page with aggregate stats | Jinja2 template rendering aggregate queries from audit_scores table |
| SITE-09 | About/disclaimer page with methodology | Static Jinja2 template with hardcoded content |
| SITE-10 | Footer disclaimer on every page | Jinja2 base template includes footer block inherited by all pages |
| SITE-11 | MDC blue (#003366), white, amber color scheme | CSS custom properties in a single stylesheet |
| SITE-12 | Responsive layout that works on mobile | CSS media queries with mobile-first breakpoints |
| SITE-13 | Pure static files -- works without a server | All output is .html, .css, .js, .json files; no server-side logic |
| CLI-08 | `export` command generates static site in site/ directory | New Click command in cli.py calling site generator module |
| CLI-09 | `serve` command starts local preview server | Python stdlib `http.server` serving the site/ directory |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Jinja2 | 3.1.6 | HTML template engine | The standard Python templating library; used by Flask, MkDocs, Pelican, Ansible; template inheritance, autoescape, filters |
| lunr.py | 0.8.0 | Build Lunr.js-compatible search index in Python | Generates serialized JSON index consumable by Lunr.js in the browser; no Node.js build step needed |
| python-slugify | 8.0.4 | URL-safe slug generation from dataset titles | Handles Unicode, special chars, dedup; standard for Python URL generation |
| Lunr.js | 2.3.9 (CDN) | Client-side full-text search | Pre-built index loads instantly; supports stemming, scoring, field boosting |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| MarkupSafe | (Jinja2 dep) | HTML escaping | Auto-installed with Jinja2; handles autoescape |
| http.server | stdlib | Local preview server | Built into Python; zero-dependency `serve` command |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Lunr.js + lunr.py | Fuse.js | Fuse.js: fuzzy matching, simpler setup, but slower per-search (3ms vs 1ms). For instant-as-you-type dropdown with 450+ docs, Lunr.js is faster after first query. Fuse.js requires shipping full document data to client (~larger payload). Lunr.js pre-built index is more compact. |
| Jinja2 | Mako, staticjinja | Jinja2 is already in the Flask ecosystem this developer knows; staticjinja adds unnecessary abstraction over what is a simple render loop |
| python-slugify | manual re.sub | python-slugify handles Unicode edge cases, max_length, word boundaries that manual regex misses |

**Installation:**
```bash
pip install Jinja2>=3.1 lunr>=0.8 python-slugify>=8.0
```

**CDN (in HTML templates):**
```html
<script src="https://cdn.jsdelivr.net/npm/lunr@2.3.9/lunr.min.js"></script>
```

## Architecture Patterns

### Recommended Project Structure
```
src/mdc_encyclopedia/
├── site/                    # NEW: static site generator module
│   ├── __init__.py
│   ├── generator.py         # Main export orchestrator (reads DB, renders templates, writes files)
│   ├── search_index.py      # lunr.py index builder (generates search-index.json + search-data.json)
│   ├── context.py           # Query helpers that build template context dicts from SQLite
│   └── templates/           # Jinja2 HTML templates
│       ├── base.html        # Base layout: head, nav, footer, CSS/JS includes
│       ├── index.html        # Homepage: search bar, stat cards, category links
│       ├── browse.html       # Category browse page: dataset list rows with filters
│       ├── dataset.html      # Individual dataset detail page
│       ├── changes.html      # "What Changed" page
│       ├── quality.html      # Data quality report page
│       └── about.html        # About/disclaimer page
├── site/static/             # Static assets copied verbatim to output
│   ├── style.css            # All site CSS (custom properties, responsive)
│   └── search.js            # Search dropdown logic (loads index, handles input)
└── ...existing modules...

site/                        # OUTPUT directory (generated, gitignored)
├── index.html
├── browse/
│   └── {category-slug}/
│       └── index.html
├── dataset/
│   └── {dataset-slug}/
│       └── index.html
├── changes/
│   └── index.html
├── quality/
│   └── index.html
├── about/
│   └── index.html
├── static/
│   ├── style.css
│   ├── search.js
│   └── lunr.min.js          # Vendored or CDN-referenced
├── search-index.json         # Pre-built Lunr.js index
└── search-data.json          # Document metadata for search result display
```

### Pattern 1: Generator Orchestrator
**What:** A single `generate_site()` function that reads all data from SQLite, builds template contexts, renders every page, and writes to disk.
**When to use:** For the `export` CLI command.
**Example:**
```python
# Source: Standard Jinja2 static site pattern
import os
import json
from jinja2 import Environment, FileSystemLoader, select_autoescape

def generate_site(db_path: str, output_dir: str = "site") -> dict:
    """Generate the complete static site from the catalog database.

    Returns dict with generation stats (page counts, index size, etc.).
    """
    conn = get_connection(db_path)

    # Set up Jinja2
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Build all template contexts from DB
    site_data = build_site_data(conn)

    # Render pages
    render_homepage(env, site_data, output_dir)
    render_browse_pages(env, site_data, output_dir)
    render_dataset_pages(env, site_data, output_dir)
    render_changes_page(env, site_data, output_dir)
    render_quality_page(env, site_data, output_dir)
    render_about_page(env, site_data, output_dir)

    # Build search index
    build_search_index(site_data["datasets"], output_dir)

    # Copy static assets
    copy_static_assets(output_dir)

    conn.close()
    return {"pages": ..., "datasets": ...}
```

### Pattern 2: Pre-built Search Index with Lunr.py
**What:** Build the Lunr.js search index in Python at export time, serialize to JSON, load in browser.
**When to use:** For SITE-01 full-text search.
**Example:**
```python
# Source: lunr.py official docs (lunr.readthedocs.io)
from lunr import lunr
import json

def build_search_index(datasets: list[dict], output_dir: str) -> None:
    """Build Lunr.js-compatible search index and document store."""
    # Documents for the search index
    documents = []
    search_data = {}  # Keyed by dataset slug for result display

    for ds in datasets:
        doc = {
            "id": ds["slug"],
            "title": ds["title"],
            "description": ds["ai_description"] or ds["description"] or "",
            "keywords": ds.get("keywords_text", ""),
            "department": ds.get("department", ""),
            "category": ds.get("category", ""),
        }
        documents.append(doc)
        search_data[ds["slug"]] = {
            "title": ds["title"],
            "snippet": (ds["ai_description"] or "")[:120],
            "department": ds.get("department", ""),
            "url": f"/dataset/{ds['slug']}/",
        }

    # Build the Lunr index
    idx = lunr(
        ref="id",
        fields=[
            {"field_name": "title", "boost": 10},
            {"field_name": "description", "boost": 5},
            {"field_name": "keywords", "boost": 8},
            {"field_name": "department", "boost": 3},
            {"field_name": "category", "boost": 3},
        ],
        documents=documents,
    )

    # Serialize index
    with open(os.path.join(output_dir, "search-index.json"), "w") as f:
        json.dump(idx.serialize(), f)

    # Serialize document metadata for search result display
    with open(os.path.join(output_dir, "search-data.json"), "w") as f:
        json.dump(search_data, f)
```

### Pattern 3: Client-Side Search Dropdown (Vanilla JS)
**What:** Load pre-built index, search on keyup, show dropdown with top results.
**When to use:** For the homepage instant search UX.
**Example:**
```javascript
// search.js — loaded on every page
let searchIndex = null;
let searchData = null;

async function initSearch() {
    const [indexResp, dataResp] = await Promise.all([
        fetch('/search-index.json'),
        fetch('/search-data.json'),
    ]);
    searchIndex = lunr.Index.load(await indexResp.json());
    searchData = await dataResp.json();
}

function onSearchInput(query) {
    if (!searchIndex || query.length < 2) {
        hideDropdown();
        return;
    }
    // Lunr search with wildcard suffix for as-you-type
    const results = searchIndex.search(query + '*').slice(0, 8);
    const items = results.map(r => searchData[r.ref]);
    renderDropdown(items);
}

document.addEventListener('DOMContentLoaded', initSearch);
```

### Pattern 4: Client-Side Filtering (No Framework)
**What:** Filter browse page rows using data attributes and vanilla JS.
**When to use:** For SITE-06 filtering by format, publisher, tag.
**Example:**
```html
<!-- Browse page row with data attributes for filtering -->
<tr class="dataset-row"
    data-format="geojson"
    data-publisher="ITD"
    data-tags="transportation,roads">
  <td>Road Centerlines</td>
  <td>GIS line data for all county roads...</td>
  <td><span class="chip">ITD</span></td>
  <td><span class="grade grade-b">B</span></td>
</tr>
```
```javascript
// Filter logic — toggles display:none based on active filters
function applyFilters() {
    const rows = document.querySelectorAll('.dataset-row');
    rows.forEach(row => {
        const matchFormat = !activeFormat || row.dataset.format === activeFormat;
        const matchPub = !activePublisher || row.dataset.publisher === activePublisher;
        row.style.display = (matchFormat && matchPub) ? '' : 'none';
    });
    updateResultCount();
}
```

### Pattern 5: Relative Time at Build Time
**What:** Compute "Updated 3 days ago" strings and staleness colors during export, not at runtime.
**When to use:** For SITE-05 freshness indicators.
**Example:**
```python
from datetime import datetime, timezone

def relative_time(dt_str: str | None) -> str:
    """Convert ISO datetime string to human-readable relative time."""
    if not dt_str:
        return "Unknown"
    dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - dt
    days = delta.days
    if days == 0:
        return "Today"
    elif days == 1:
        return "Yesterday"
    elif days < 30:
        return f"{days} days ago"
    elif days < 365:
        months = days // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    else:
        years = days // 365
        return f"{years} year{'s' if years > 1 else ''} ago"

def staleness_color(audit_staleness_score: float | None) -> str:
    """Map audit staleness score to green/yellow/red."""
    if audit_staleness_score is None:
        return "gray"
    if audit_staleness_score >= 0.8:
        return "green"
    elif audit_staleness_score >= 0.4:
        return "yellow"
    return "red"
```

### Anti-Patterns to Avoid
- **Server-side rendering at request time:** The entire point is static files. All data is baked in at export time. Do NOT use Flask to serve pages.
- **JavaScript-heavy SPA architecture:** No React/Vue/Svelte. Plain HTML + minimal vanilla JS. The site must work with JS disabled (except search).
- **Generating slugs at query time:** Pre-compute all slugs during export and store the mapping. Dataset slugs must be deterministic and collision-free.
- **Inlining all CSS per page:** Use a single shared stylesheet. Jinja2 base template includes it once.
- **Loading the full dataset JSON for search:** Lunr.js uses a compact inverted index. Only ship the index + a lightweight metadata store for display, not the full dataset records.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Search index generation | Custom inverted index builder | lunr.py + Lunr.js | Stemming, scoring, field boosting, serialization format are all solved problems |
| URL slug generation | `re.sub(r'[^a-z0-9]', '-', title.lower())` | python-slugify | Unicode handling, duplicate slug resolution, max_length, word boundaries |
| HTML escaping | Manual string replacement | Jinja2 autoescape | XSS prevention is built into the template engine; manual escaping misses edge cases |
| Relative time formatting | Custom timedelta formatter | Jinja2 custom filter | Centralize the logic once, reuse across templates |
| CSS color system | Hardcoded colors per element | CSS custom properties | One place to define --mdc-blue, --mdc-amber, --mdc-white; easy to maintain |
| Responsive layout | Custom JS resize handlers | CSS media queries + flexbox/grid | Pure CSS is faster, more reliable, and works without JS |

**Key insight:** The site generator is a data pipeline (SQLite -> dict -> Jinja2 -> HTML). Keep the Python side focused on data transformation and template rendering. All interactivity (search, filtering) is lightweight client-side JS operating on pre-baked data attributes and JSON files.

## Common Pitfalls

### Pitfall 1: Slug Collisions
**What goes wrong:** Two datasets with similar titles generate the same slug, causing one page to overwrite the other.
**Why it happens:** Naive slugification of "Parks and Recreation" and "Parks & Recreation" both become `parks-and-recreation`.
**How to avoid:** Use dataset ID as a fallback disambiguator. Check for collisions during export and append a suffix (e.g., `-2`) or use the dataset ID directly as the slug.
**Warning signs:** Fewer dataset pages generated than datasets in DB.

### Pitfall 2: Search Index Too Large
**What goes wrong:** The search-index.json file exceeds 500KB-1MB, causing slow page loads on mobile.
**Why it happens:** Indexing too many fields or including full descriptions/body text in the index.
**How to avoid:** Index only title, AI keywords, department, and category. Keep descriptions for the search-data.json (display only, not indexed heavily). Measure the index size after first build. Target under 500KB for the index JSON.
**Warning signs:** search-index.json over 500KB; search-data.json over 200KB.

### Pitfall 3: Broken Relative Links
**What goes wrong:** Links between pages break when served from different paths or when opened as local files.
**Why it happens:** Using relative paths like `../static/style.css` that break depending on directory depth.
**How to avoid:** Use absolute paths from site root (`/static/style.css`, `/dataset/slug/`). For local file:// browsing, provide the `serve` command as the supported way to preview.
**Warning signs:** CSS/JS not loading on some pages; links to dataset pages 404.

### Pitfall 4: Missing Data Handling
**What goes wrong:** Templates crash with `None`/empty values when datasets lack enrichment or audit data.
**Why it happens:** Not all datasets have been enriched or audited. Fields like `enrichment.description` may be None.
**How to avoid:** Use Jinja2's `default` filter and `{% if %}` guards in every template. Build context dicts with explicit None/fallback values. Test with a partially-enriched database.
**Warning signs:** Jinja2 `UndefinedError` during export.

### Pitfall 5: Template Performance with 450+ Pages
**What goes wrong:** Export takes minutes because each template is re-parsed.
**Why it happens:** Creating a new Environment per page or not using Jinja2's built-in caching.
**How to avoid:** Create the Environment once, reuse `env.get_template()` calls. Jinja2 caches compiled templates by default (cache_size=400). For 450+ datasets, this is fine.
**Warning signs:** Export time exceeding 30 seconds.

### Pitfall 6: Tags/Keywords Stored as JSON Strings
**What goes wrong:** Template renders `["keyword1", "keyword2"]` as a literal string instead of individual tags.
**Why it happens:** The `keywords` and `use_cases` fields in enrichments are stored as JSON strings. The `tags` field in datasets is sometimes a JSON array, sometimes a plain string.
**How to avoid:** Parse JSON fields in the context-building layer (context.py), not in templates. Normalize all list-type fields to Python lists before passing to Jinja2.
**Warning signs:** Bracketed strings appearing in the HTML output.

## Code Examples

### Jinja2 Base Template with Inheritance
```html
{# base.html - Source: Jinja2 official template inheritance docs #}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}MDC Open Data Encyclopedia{% endblock %}</title>
    <link rel="stylesheet" href="/static/style.css">
    {% block head %}{% endblock %}
</head>
<body>
    <nav class="site-nav">
        <a href="/" class="nav-brand">MDC Data Encyclopedia</a>
        <div class="nav-links">
            <a href="/browse/">Browse</a>
            <a href="/changes/">What Changed</a>
            <a href="/quality/">Data Quality</a>
            <a href="/about/">About</a>
        </div>
    </nav>

    <main class="content">
        {% block content %}{% endblock %}
    </main>

    <footer class="site-footer">
        <p>Not an official Miami-Dade County product. Built by Abreu Data Works LLC.</p>
        <p>Data sourced from <a href="https://gis-mdc.opendata.arcgis.com/">Miami-Dade County Open Data</a>.</p>
        <p>Generated {{ generated_at }}</p>
    </footer>

    <script src="/static/lunr.min.js"></script>
    <script src="/static/search.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

### Letter Grade Badge CSS
```css
/* Grade badges with familiar A-F color coding */
.grade {
    display: inline-block;
    width: 28px;
    height: 28px;
    line-height: 28px;
    text-align: center;
    border-radius: 4px;
    font-weight: 700;
    font-size: 0.85rem;
    color: white;
}
.grade-a { background-color: #2e7d32; }
.grade-b { background-color: #558b2f; }
.grade-c { background-color: #f9a825; color: #333; }
.grade-d { background-color: #e65100; }
.grade-f { background-color: #c62828; }
```

### CLI Export Command Pattern
```python
# Following existing CLI patterns from cli.py
@cli.command()
@click.option("--output", "-o", default="site", show_default=True,
              help="Output directory for the generated site.")
@click.pass_context
def export(ctx, output):
    """Generate static HTML site from the catalog database."""
    from mdc_encyclopedia.site.generator import generate_site

    db_path = ctx.obj["db_path"]

    with Progress(...) as progress:
        task = progress.add_task("Generating site", total=None)
        stats = generate_site(db_path, output)
        progress.update(task, completed=True)

    # Summary table (following project pattern)
    table = Table(title="Export Summary")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_row("Dataset pages", str(stats["dataset_pages"]))
    table.add_row("Category pages", str(stats["category_pages"]))
    table.add_row("Search index size", stats["index_size"])
    table.add_row("Output directory", os.path.abspath(output))
    console.print(table)
```

### CLI Serve Command Pattern
```python
@cli.command()
@click.option("--port", "-p", default=8000, show_default=True,
              help="Port for the preview server.")
@click.option("--directory", "-d", default="site", show_default=True,
              help="Directory to serve.")
@click.pass_context
def serve(ctx, port, directory):
    """Start a local preview server for the static site."""
    import http.server
    import functools

    if not os.path.isdir(directory):
        console.print(f"[red]Directory '{directory}' not found. Run `export` first.[/red]")
        raise click.Abort()

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)
    server = http.server.HTTPServer(("", port), handler)
    console.print(f"[green]Serving {directory}/ at http://localhost:{port}[/green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped.[/yellow]")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Build Lunr.js index in Node.js | Use lunr.py to build in Python | lunr.py 0.8.0 (Mar 2025) | No Node.js dependency needed; Python-native build |
| Ship full document data for Fuse.js search | Pre-built inverted index with Lunr.js | Standard since 2020 | Much smaller payload; faster per-search |
| Manual slug generation with regex | python-slugify with Unicode support | Stable since 2020 | Handles edge cases, collisions, international characters |
| Server-side search (Elasticsearch, etc.) | Client-side search for small catalogs (<5000 docs) | Common pattern since 2018 | Zero infrastructure; works on static hosts |

**Deprecated/outdated:**
- SQLSite (sqlsite): No longer maintained. Was a server-side approach; we want pure static output.
- Pelican/Hugo for this use case: Overkill. We have structured SQLite data, not markdown blog posts. A custom generator is simpler and more maintainable.

## Discretion Recommendations

These are areas marked as "Claude's Discretion" in CONTEXT.md:

### Search Library: Lunr.js (via lunr.py)
**Recommendation:** Use Lunr.js with lunr.py for index generation.
**Rationale:** The user wants instant dropdown results as the user types. Lunr.js is faster per-search (1ms vs 3ms for Fuse.js) which matters for keyup-driven search. lunr.py eliminates any Node.js build dependency. The pre-built inverted index is more compact than Fuse.js's full-document approach. For 450+ datasets, the index should be well under 500KB.

### Typography
**Recommendation:** System font stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`).
**Rationale:** Zero additional HTTP requests, fast rendering, native look on every platform. Consistent with "professional startup" aesthetic without the weight of web fonts.

### Navigation
**Recommendation:** Fixed top nav bar with: logo/brand link, Browse, What Changed, Data Quality, About. Search bar integrated into the nav on non-homepage pages.
**Rationale:** Simple, predictable, works on mobile with a hamburger menu. Breadcrumbs on detail pages only (Home > Browse > Category > Dataset).

### Dataset Detail Page Ordering
**Recommendation:** Title + grade badge > AI description > Use cases > Key metadata table (publisher, format, updated, source link) > Column table > Related datasets > Quality breakdown.
**Rationale:** Lead with what a resident cares about (what is this, why does it matter), then technical details, then related content.

### Mobile Breakpoints
**Recommendation:** Two breakpoints: 768px (tablet) and 480px (phone). Desktop-first with progressive reduction.
**Rationale:** The primary audience likely browses on desktop (civic researchers, journalists), but mobile must work. At 768px, nav collapses to hamburger. At 480px, list rows stack vertically.

### Filtering UX
**Recommendation:** Inline filter bar above the dataset list with dropdowns for format, publisher, and tag. Active filters shown as removable chips. "X results" counter updates live.
**Rationale:** Matches the "dense and scannable" locked decision. Filters should feel like refinements, not navigation. All client-side via data attributes.

## Open Questions

1. **Search index size with real data**
   - What we know: 450+ datasets, indexing title + AI keywords + department + category. Lunr.js indexes are compact but size depends on vocabulary.
   - What's unclear: Exact byte size until we build with real data.
   - Recommendation: Build index with real data in first implementation task, measure size. If over 500KB, reduce indexed fields or use gzip.

2. **Related datasets algorithm**
   - What we know: SITE-04 requires "tag/category overlap" for related datasets.
   - What's unclear: How many related datasets to show, minimum overlap threshold.
   - Recommendation: Show top 5 related datasets. Score by: same category (3 points) + each shared keyword (1 point). Pre-compute during export. If no matches, show "No related datasets found."

3. **Dataset slug uniqueness**
   - What we know: python-slugify handles most cases, but 450+ datasets may have title collisions.
   - What's unclear: How many actual collisions exist in the MDC catalog.
   - Recommendation: Generate slug from title, check for collisions, append dataset ID suffix if collision detected. Log collisions during export for awareness.

## Sources

### Primary (HIGH confidence)
- Jinja2 official docs (jinja.palletsprojects.com) - Template inheritance, Environment API, FileSystemLoader, autoescape
- lunr.py official docs (lunr.readthedocs.io) - Index creation, serialization, Lunr.js interoperability
- lunr.py PyPI (pypi.org/project/lunr) - Version 0.8.0, March 2025, Python 3.9-3.13
- Fuse.js official docs (fusejs.io) - Installation, indexing API, weighted search, CDN
- python-slugify PyPI (pypi.org/project/python-slugify) - Version 8.0.4, Feb 2024
- Jinja2 PyPI (pypi.org/project/Jinja2) - Version 3.1.6, March 2025
- Python stdlib http.server docs (docs.python.org/3) - SimpleHTTPRequestHandler, directory serving

### Secondary (MEDIUM confidence)
- Lunr.js vs Fuse.js comparison (npm-compare.com, wiki.gpii.net) - Performance benchmarks (1ms vs 3ms per search, 376ms vs 2721ms indexing)
- Lunr.js prebuilding guide (lunrjs.com/guides/index_prebuilding.html) - Serialization and loading patterns
- Static site generation patterns (fullstackpython.com, multiple GitHub repos) - Jinja2 + custom generator patterns

### Tertiary (LOW confidence)
- Search index size estimates (various blog posts) - "Target under 500KB" heuristic; actual size depends on data. Needs validation with real catalog data.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified via official docs and PyPI; versions confirmed current
- Architecture: HIGH - Pattern is well-established (Jinja2 static generation); existing codebase patterns (module per feature, Rich CLI output) are clear
- Pitfalls: HIGH - Common issues well-documented across static site generator community; JSON field parsing verified in existing codebase code
- Search library choice: MEDIUM - Performance claims from comparison sites, not benchmarked against this specific dataset; lunr.py interop verified via official docs

**Research date:** 2026-02-26
**Valid until:** 2026-03-26 (stable domain; libraries are mature)
