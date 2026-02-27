"""Atom 1.0 feed generation for catalog changes."""

import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from feedgen.feed import FeedGenerator


PREFIX_MAP = {
    "added": "[New]",
    "removed": "[Removed]",
    "schema_changed": "[Schema Change]",
}


def generate_atom_feed(site_data, output_dir, site_url, max_entries=50):
    """Generate an Atom 1.0 feed of recent catalog changes.

    Args:
        site_data: Complete site data dict from build_site_data().
        output_dir: Root output directory for the generated site.
        site_url: Full site URL (e.g. https://example.github.io/DataDictionary).
        max_entries: Maximum number of change entries in the feed.

    Returns:
        Dict with entry_count.
    """
    # Strip trailing slash from site_url
    site_url = site_url.rstrip("/")

    fg = FeedGenerator()
    fg.id(f"{site_url}/atom.xml")
    fg.title("MDC Data Encyclopedia - Catalog Changes")
    fg.subtitle("New, removed, and changed open datasets across South Florida")
    fg.author({"name": "MDC Data Encyclopedia"})
    fg.link(href=site_url, rel="alternate")
    fg.link(href=f"{site_url}/atom.xml", rel="self")
    fg.language("en")

    # Build slug lookup for dataset detail page links
    slug_lookup = {ds["id"]: ds["slug"] for ds in site_data["datasets"]}

    # Extract domain from site_url for tag URIs
    parsed = urlparse(site_url)
    domain = parsed.netloc
    if parsed.path and parsed.path != "/":
        domain += parsed.path

    # Slice to most recent changes
    changes = site_data["changes"][:max_entries]

    # Set feed updated time
    if changes:
        most_recent_ts = changes[0].get("detected_at", "")
        fg.updated(_parse_timestamp(most_recent_ts))
    else:
        fg.updated(datetime.now(timezone.utc))

    for change in changes:
        change_type = change.get("change_type", "")
        dataset_id = change.get("dataset_id", "unknown")
        title = change.get("dataset_title") or change.get("title") or "a dataset"
        detected_at = change.get("detected_at", "")

        prefix = PREFIX_MAP.get(change_type, "")
        entry_title = f"{prefix} {title}" if prefix else title

        # Parse timestamp for date portion of tag URI
        ts = _parse_timestamp(detected_at)
        date_str = ts.strftime("%Y-%m-%d")

        fe = fg.add_entry()
        fe.id(f"tag:{domain},{date_str}:{dataset_id}/{change_type}")
        fe.title(entry_title)

        # Link to dataset detail page (only if slug exists)
        slug = slug_lookup.get(dataset_id)
        if slug:
            fe.link(href=f"{site_url}/dataset/{slug}/")

        fe.summary(_build_summary(change, change_type))
        fe.updated(ts)
        fe.published(ts)

    # Write atom.xml
    fg.atom_file(os.path.join(output_dir, "atom.xml"), pretty=True)

    return {"entry_count": len(changes)}


def _parse_timestamp(ts_str):
    """Parse an ISO timestamp string to a timezone-aware datetime.

    Args:
        ts_str: ISO-format datetime string.

    Returns:
        Timezone-aware datetime (UTC).
    """
    if not ts_str:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc)


def _build_summary(change, change_type):
    """Build a human-readable summary for a feed entry.

    Mentions jurisdiction when available. Uses title-cased slug
    for jurisdiction display name.

    Args:
        change: Change record dict.
        change_type: One of 'added', 'removed', 'schema_changed'.

    Returns:
        Summary string.
    """
    title = change.get("dataset_title") or change.get("title") or "a dataset"
    jurisdiction = change.get("jurisdiction", "") or ""

    # Convert jurisdiction slug to display name
    if jurisdiction:
        jurisdiction = jurisdiction.replace("-", " ").title()

    if change_type == "added":
        if jurisdiction:
            return f"A new dataset '{title}' has been added from {jurisdiction}."
        return f"A new dataset '{title}' has been added to the catalog."

    if change_type == "removed":
        if jurisdiction:
            return f"The dataset '{title}' from {jurisdiction} has been removed from the catalog."
        return f"The dataset '{title}' has been removed from the catalog."

    if change_type == "schema_changed":
        if jurisdiction:
            return f"The schema for '{title}' from {jurisdiction} has changed. Columns may have been added or removed."
        return f"The schema for '{title}' has changed. Columns may have been added or removed."

    return f"A change was detected for '{title}'."
