# Phase 9: Atom Feed - Research

**Researched:** 2026-02-27
**Domain:** Atom 1.0 feed generation (RFC 4287), static site integration
**Confidence:** HIGH

## Summary

Phase 9 adds an Atom 1.0 feed to the static site export so users can subscribe to catalog changes (new, removed, schema-changed datasets) via any standard feed reader. The implementation hooks into the existing `export` CLI command and `generate_site()` pipeline, adding a `--site-url` parameter for absolute URL construction and writing `atom.xml` to the site root during build.

The standard Python library for this task is `feedgen` (v1.0.0), which handles RFC 4287 compliance, XML namespace management, and RFC 3339 date formatting out of the box. The project's `changes` table already stores categorized change records (added, removed, schema_changed) with timestamps and dataset titles -- this data feeds directly into Atom entries with no new database queries needed. Feed autodiscovery is a single `<link>` tag in the HTML `<head>`.

**Primary recommendation:** Use `feedgen==1.0.0` for Atom XML generation; wire it into `generate_site()` after `build_site_data()` returns; gate feed generation on the presence of `--site-url` with a warning when omitted.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Title uses prefix tag format: `[New] Building Permits`, `[Removed] Old Zoning Map`, `[Schema Change] Code Violations`
- Entry body is a 1-2 sentence summary -- not full dataset detail, not title-only
- Jurisdiction is mentioned in the summary body (e.g. "A new dataset from Broward County...")
- Each entry links to the encyclopedia's own dataset detail page, not the source portal
- atom.xml is generated as part of the existing site export command -- not a separate CLI command
- When `--site-url` is omitted: skip feed generation with a warning, build the rest of the site normally. Feed is optional, not a hard requirement for build success
- atom.xml placed at site root (`/atom.xml`) -- standard convention for autodiscovery
- No `--no-feed` flag needed -- presence of `--site-url` is the implicit trigger for feed generation

### Claude's Discretion
- Feed metadata (title, subtitle, author fields)
- Number of entries to include in the feed
- How to detect and categorize changes (new vs removed vs schema change)
- Autodiscovery `<link>` tag placement and attributes in HTML head
- Atom XML library or template approach

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope. (Per-jurisdiction feeds and RSS 2.0 dual format already tracked as FEED-04/FEED-06 in v1.2 requirements.)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FEED-01 | Atom 1.0 feed generated during site build with recent catalog changes (new, removed, schema changes) | feedgen library generates RFC 4287 compliant Atom XML; `site_data["changes"]` already contains categorized change records from the DB; feed generation hooks into `generate_site()` |
| FEED-02 | Feed autodiscovery `<link>` in HTML `<head>` | Standard `<link rel="alternate" type="application/atom+xml">` tag in base.html's `{% block head %}`; conditional on `site_url` being available in Jinja2 globals |
| FEED-03 | `--site-url` parameter on export command for absolute URLs in feed entries | New Click option on `export_site()` CLI command; passed through to `generate_site()` and used to construct absolute `<link href>` values in feed entries and the feed self-link |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| feedgen | 1.0.0 | Atom XML generation | Purpose-built for Atom/RSS; handles RFC 4287 compliance, XML namespaces, date formatting; 12+ code examples in Context7; PyPI high-reputation package |

### Supporting (already in project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Jinja2 | >=3.1 | HTML template rendering | Already used by generator.py; add autodiscovery `<link>` tag to base.html template |
| click | >=8.0 | CLI option parsing | Already used; add `--site-url` option to `export_site()` command |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| feedgen | Jinja2 XML template | Would need manual RFC 3339 date formatting, XML escaping, and namespace handling -- all things feedgen does automatically |
| feedgen | xml.etree.ElementTree (stdlib) | No new dependency but ugly `ns0:` namespace prefixes, verbose API, manual date formatting; not worth the complexity |
| feedgen | lxml directly | feedgen uses lxml internally and provides a higher-level API; no reason to go lower |

**Installation:**
```bash
pip install feedgen==1.0.0
```

Add to `pyproject.toml` dependencies:
```toml
"feedgen>=1.0,<2.0",
```

**Note:** feedgen depends on `lxml` and `python-dateutil`. Both are well-maintained, widely-used packages. lxml is a compiled C extension -- it may add build time in CI but is a standard dependency in the Python ecosystem.

## Architecture Patterns

### Integration Points in Existing Codebase

```
src/mdc_encyclopedia/
  cli.py              # Add --site-url option to export_site() command
  site/
    generator.py       # Add _generate_atom_feed() function, call from generate_site()
    context.py         # No changes needed -- build_site_data() already returns changes
    feed.py            # NEW: Atom feed generation logic (feedgen wrapper)
    templates/
      base.html        # Add conditional <link rel="alternate"> autodiscovery tag
```

### Pattern 1: Feed Generation as Post-Build Step

**What:** Generate atom.xml after all HTML pages are rendered, using the same `site_data` dict.
**When to use:** When the feed draws from data already computed for HTML pages.
**Why:** The `changes` list and `datasets` list (with slugs) are already in `site_data`. No additional DB queries needed.

```python
# In generator.py generate_site():
def generate_site(db_path, output_dir="site", base_url="", site_url=None):
    conn = get_connection(db_path)
    site_data = build_site_data(conn)
    conn.close()

    # ... existing page rendering ...

    # Feed generation (gated on site_url)
    if site_url:
        from mdc_encyclopedia.site.feed import generate_atom_feed
        feed_stats = generate_atom_feed(site_data, output_dir, site_url)
        stats["feed_entries"] = feed_stats["entry_count"]
    # else: caller already warned about missing --site-url

    return stats
```

### Pattern 2: Change Record to Feed Entry Mapping

**What:** Map each `changes` record to an Atom feed entry with typed title prefix and jurisdiction-aware summary.
**When to use:** For every change record in the feed window.

```python
# In feed.py:
from feedgen.feed import FeedGenerator

def generate_atom_feed(site_data, output_dir, site_url):
    fg = FeedGenerator()
    fg.id(f"{site_url}/atom.xml")
    fg.title("MDC Data Encyclopedia - Catalog Changes")
    fg.subtitle("New, removed, and changed datasets across South Florida open data portals")
    fg.author({"name": "MDC Data Encyclopedia"})
    fg.link(href=site_url, rel="alternate")
    fg.link(href=f"{site_url}/atom.xml", rel="self")
    fg.language("en")

    # Build slug lookup for dataset detail page URLs
    slug_lookup = {ds["id"]: ds["slug"] for ds in site_data["datasets"]}

    # Map change_type to title prefix
    PREFIX_MAP = {
        "added": "[New]",
        "removed": "[Removed]",
        "schema_changed": "[Schema Change]",
    }

    changes = site_data["changes"][:50]  # Most recent 50 entries
    for change in changes:
        fe = fg.add_entry()
        # ... populate entry ...

    fg.atom_file(os.path.join(output_dir, "atom.xml"), pretty=True)
```

### Pattern 3: Conditional Autodiscovery Tag

**What:** Add `<link>` tag to HTML `<head>` only when site_url is available.
**When to use:** In base.html template.

```html
{# In base.html, inside <head> #}
{% if site_url %}
<link rel="alternate" type="application/atom+xml"
      title="MDC Data Encyclopedia - Catalog Changes"
      href="{{ site_url }}/atom.xml">
{% endif %}
```

### Anti-Patterns to Avoid
- **Hand-rolling XML with string concatenation:** Never build XML by string formatting. feedgen handles escaping, namespaces, and encoding declaration properly.
- **Using relative URLs in feed entries:** Feed readers fetch entries from outside the site context. All `<link href>` values MUST be absolute URLs (e.g., `https://example.com/dataset/building-permits/`).
- **Generating a separate feed per build without deduplication:** The `changes` table already handles deduplication -- each change is recorded once. Just query and format.
- **Making feed generation a separate CLI command:** The user explicitly decided it should be part of the existing `export` command.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atom XML generation | String templates or ElementTree with manual namespace management | feedgen 1.0.0 | RFC 4287 has many required elements, ordering rules, and date format requirements; feedgen handles all of this |
| RFC 3339 date formatting | `strftime()` with manual timezone offsets | feedgen's `updated()` / `published()` which accept Python datetime objects | feedgen automatically serializes datetime objects to RFC 3339 format with proper timezone handling |
| XML namespace declaration | Manual `xmlns` attribute handling | feedgen (uses lxml internally) | Atom namespace `http://www.w3.org/2005/Atom` must be declared properly; feedgen handles this |

**Key insight:** Atom feeds look simple but have many compliance requirements (required elements, date formats, namespace handling, content type attributes). feedgen abstracts all of these into a clean Python API.

## Common Pitfalls

### Pitfall 1: Relative URLs in Feed Entries
**What goes wrong:** Feed entries use relative paths like `/dataset/building-permits/` instead of absolute URLs. Feed readers cannot resolve these because they don't know the site's base URL.
**Why it happens:** The site generator currently uses `base_url` (a path prefix like `/DataDictionary`) not a full URL. Developers confuse the two.
**How to avoid:** Always construct entry links as `{site_url}/dataset/{slug}/`. The `site_url` parameter is a full URL like `https://example.github.io/DataDictionary`.
**Warning signs:** Links in feed reader show as broken or redirect to the feed reader's own domain.

### Pitfall 2: Missing or Invalid Feed ID
**What goes wrong:** The feed `<id>` element must be a permanently unique URI per RFC 4287. Using a URL that might change (like a dev server) creates invalid feeds.
**Why it happens:** Developers use the site URL as the feed ID without thinking about permanence.
**How to avoid:** Use `{site_url}/atom.xml` as the feed ID -- it is the canonical location of the feed itself and is stable.
**Warning signs:** Feed validators report "id is not a permanent URI."

### Pitfall 3: Entry IDs Not Unique Across Rebuilds
**What goes wrong:** If entry IDs change between builds, feed readers show duplicate entries or lose read state.
**Why it happens:** Using auto-incrementing DB row IDs or timestamps as entry IDs.
**How to avoid:** Use the combination of dataset_id + change_type + detected_at as a stable, deterministic entry ID. Format as a tag URI: `tag:site,{date}:{dataset_id}/{change_type}`.
**Warning signs:** Feed reader shows the same entries repeatedly after each site rebuild.

### Pitfall 4: Timezone-Naive Datetimes
**What goes wrong:** feedgen requires timezone-aware datetime objects. Passing naive datetimes raises an error or produces invalid XML.
**Why it happens:** The `changes.detected_at` column stores timestamps as strings without explicit timezone info.
**How to avoid:** When parsing `detected_at` strings, always attach UTC timezone: `datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)`.
**Warning signs:** feedgen raises `ValueError` about timezone, or feed validator reports invalid date format.

### Pitfall 5: Empty Feed When No Changes Exist
**What goes wrong:** If the changes table is empty (first pull only, no second pull yet), the feed has zero entries.
**Why it happens:** Changes are only recorded starting from the second pull.
**How to avoid:** Generate the feed even with zero entries -- an empty Atom feed is valid per RFC 4287. The feed's `<updated>` element should use the site generation timestamp as fallback.
**Warning signs:** Feed readers report "no new items" indefinitely.

### Pitfall 6: Forgetting to Pass site_url to Templates
**What goes wrong:** The autodiscovery `<link>` tag in base.html needs the full `site_url` to construct the feed href, but only `base_url` (path prefix) is currently passed to templates.
**Why it happens:** `base_url` and `site_url` serve different purposes and both need to be in the Jinja2 globals.
**How to avoid:** Add `site_url` to `env.globals` alongside existing `base_url` in generator.py.
**Warning signs:** Autodiscovery tag has an empty or relative href.

## Code Examples

### Complete Feed Generation Function

```python
# Source: feedgen 1.0.0 docs + RFC 4287 spec
import os
from datetime import datetime, timezone
from feedgen.feed import FeedGenerator


def generate_atom_feed(site_data, output_dir, site_url, max_entries=50):
    """Generate atom.xml from catalog change records.

    Args:
        site_data: Dict from build_site_data() with 'changes' and 'datasets'.
        output_dir: Root output directory for the static site.
        site_url: Full base URL (e.g., 'https://example.github.io/DataDictionary').
        max_entries: Maximum number of feed entries (default 50).

    Returns:
        Dict with entry_count.
    """
    site_url = site_url.rstrip("/")
    fg = FeedGenerator()
    fg.id(f"{site_url}/atom.xml")
    fg.title("MDC Data Encyclopedia - Catalog Changes")
    fg.subtitle("New, removed, and changed open datasets across South Florida")
    fg.author({"name": "MDC Data Encyclopedia"})
    fg.link(href=site_url, rel="alternate")
    fg.link(href=f"{site_url}/atom.xml", rel="self")
    fg.language("en")

    # Slug lookup for constructing dataset page URLs
    slug_lookup = {ds["id"]: ds["slug"] for ds in site_data["datasets"]}

    PREFIX_MAP = {
        "added": "[New]",
        "removed": "[Removed]",
        "schema_changed": "[Schema Change]",
    }

    changes = site_data["changes"][:max_entries]
    now = datetime.now(timezone.utc)

    # Feed updated = most recent change, or generation time if no changes
    if changes and changes[0].get("detected_at"):
        feed_updated = _parse_timestamp(changes[0]["detected_at"])
    else:
        feed_updated = now
    fg.updated(feed_updated)

    for change in changes:
        ds_id = change.get("dataset_id", "")
        change_type = change.get("change_type", "added")
        title = change.get("dataset_title") or change.get("title") or ds_id
        detected_at = change.get("detected_at", "")
        prefix = PREFIX_MAP.get(change_type, "[Changed]")

        fe = fg.add_entry()
        fe.id(f"tag:{site_url.split('//')[1]},{detected_at[:10]}:{ds_id}/{change_type}")
        fe.title(f"{prefix} {title}")

        # Absolute URL to dataset detail page
        slug = slug_lookup.get(ds_id)
        if slug:
            entry_url = f"{site_url}/dataset/{slug}/"
            fe.link(href=entry_url, rel="alternate")

        # 1-2 sentence summary mentioning jurisdiction
        summary = _build_summary(change, change_type)
        fe.summary(summary)

        # Timestamps
        entry_dt = _parse_timestamp(detected_at) if detected_at else now
        fe.updated(entry_dt)
        fe.published(entry_dt)

    fg.atom_file(os.path.join(output_dir, "atom.xml"), pretty=True)
    return {"entry_count": len(changes)}


def _parse_timestamp(ts_str):
    """Parse a timestamp string to timezone-aware datetime."""
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc)


def _build_summary(change, change_type):
    """Build a 1-2 sentence summary for a feed entry."""
    title = change.get("dataset_title") or change.get("title") or "a dataset"
    # Jurisdiction would come from dataset metadata if available
    jurisdiction = change.get("jurisdiction", "")

    if change_type == "added":
        if jurisdiction:
            return f"A new dataset '{title}' has been added from {jurisdiction}."
        return f"A new dataset '{title}' has been added to the catalog."
    elif change_type == "removed":
        if jurisdiction:
            return f"The dataset '{title}' from {jurisdiction} has been removed from the catalog."
        return f"The dataset '{title}' has been removed from the catalog."
    elif change_type == "schema_changed":
        if jurisdiction:
            return f"The schema for '{title}' from {jurisdiction} has changed. Columns may have been added or removed."
        return f"The schema for '{title}' has changed. Columns may have been added or removed."
    return f"A change was detected for '{title}'."
```

### Autodiscovery Link Tag in base.html

```html
<!-- Source: RFC 4287 + WHATWG feed autodiscovery spec -->
<!-- In base.html <head> section, inside {% block head %} -->
{% if site_url %}
<link rel="alternate" type="application/atom+xml"
      title="MDC Data Encyclopedia - Catalog Changes"
      href="{{ site_url }}/atom.xml">
{% endif %}
```

### CLI Integration in cli.py

```python
# Source: existing cli.py pattern
@cli.command(name="export")
@click.option("--output", "-o", default="site", help="Output directory for the generated site.")
@click.option("--base-url", default="", help="Base URL prefix for GitHub Pages (e.g. /DataDictionary).")
@click.option("--site-url", default=None, help="Full site URL for feed generation (e.g. https://example.github.io/DataDictionary). Required for Atom feed.")
@click.pass_context
def export_site(ctx, output, base_url, site_url):
    """Generate static HTML site from the catalog database."""
    from mdc_encyclopedia.site.generator import generate_site

    db_path = ctx.obj["db_path"]
    base_url = base_url.rstrip("/")

    if not site_url:
        console.print(
            "[yellow]Warning: --site-url not provided. "
            "Atom feed will not be generated. "
            "Pass --site-url to enable feed generation.[/yellow]"
        )

    # ... existing progress bar ...
    stats = generate_site(db_path, output, base_url=base_url, site_url=site_url)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PyRSS2Gen (RSS only) | feedgen (Atom + RSS) | 2014+ | feedgen supports both Atom and RSS from a single codebase; PyRSS2Gen is unmaintained |
| Django feedparser for generation | feedgen standalone | 2015+ | feedgen is framework-agnostic, works outside Django |
| Manual XML string building | feedgen / lxml | Always preferred | Eliminates XML injection risks, namespace issues, encoding problems |

**Deprecated/outdated:**
- `PyRSS2Gen`: Last release 2013, RSS-only, no Atom support
- `feedparser` is for *parsing* feeds, not generating them -- do not confuse with feedgen

## Open Questions

1. **Jurisdiction metadata in change records**
   - What we know: The `changes` table stores `dataset_id`, `change_type`, `details`, `detected_at`. There is no `jurisdiction` column in the changes table itself.
   - What's unclear: To mention jurisdiction in the feed entry summary (per user decision), we need to join changes with datasets to get the jurisdiction field.
   - Recommendation: The `site_data["changes"]` query in `context.py` already does a LEFT JOIN with datasets. Add `d.jurisdiction` to that JOIN query so it's available in each change record. For removed datasets (which may no longer exist in the datasets table), fall back to omitting jurisdiction from the summary.

2. **Feed entry count (Claude's Discretion)**
   - What we know: No user requirement on count. Typical feed readers handle 50-100 entries well.
   - Recommendation: Default to 50 entries. This covers several pull cycles of changes without making the XML file excessively large.

3. **Feed metadata (Claude's Discretion)**
   - Recommendation: Title: "MDC Data Encyclopedia - Catalog Changes". Subtitle: "New, removed, and changed open datasets across South Florida". Author: "MDC Data Encyclopedia" (project name, not a person). These are descriptive and match the project identity.

## Sources

### Primary (HIGH confidence)
- [feedgen 1.0.0 Context7 docs](/lkiesow/python-feedgen) - FeedGenerator, FeedEntry API, atom_file output
- [RFC 4287: The Atom Syndication Format](https://www.rfc-editor.org/rfc/rfc4287) - Required feed/entry elements (id, title, updated), date format requirements
- [W3C Atom Introduction](https://validator.w3.org/feed/docs/atom.html) - Complete Atom feed XML example with required/recommended elements
- [feedgen PyPI](https://pypi.org/project/feedgen/) - Version 1.0.0 confirmed current
- [feedgen entry API docs](https://feedgen.kiesow.be/api.entry.html) - FeedEntry methods: summary(), content(), updated(), published(), link()
- [Jinja2 Context7 docs](/websites/jinja_palletsprojects_en_stable) - select_autoescape for XML, template globals

### Secondary (MEDIUM confidence)
- [Feed Autodiscovery](https://blog.whatwg.org/feed-autodiscovery) - WHATWG spec for `<link rel="alternate">` autodiscovery pattern
- [Pete Freitag: RSS Autodiscovery](https://www.petefreitag.com/item/384.cfm) - Confirmed `<link>` tag attributes for feed detection

### Tertiary (LOW confidence)
- None -- all findings verified against primary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - feedgen is the established Python library for feed generation; confirmed via Context7 and PyPI
- Architecture: HIGH - Integration points are clear; existing `site_data["changes"]` and `generate_site()` pipeline are well understood from codebase reading
- Pitfalls: HIGH - Based on RFC 4287 spec requirements and direct examination of the project's data model (changes table, datetime handling, URL construction)

**Research date:** 2026-02-27
**Valid until:** 2026-03-27 (stable domain; feedgen 1.0.0 is a mature release)
