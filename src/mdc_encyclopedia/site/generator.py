"""Main export orchestrator: reads DB, renders templates, writes static files."""

import logging
import os
import shutil

from jinja2 import Environment, FileSystemLoader
from slugify import slugify as _slugify

from mdc_encyclopedia.db import get_connection
from mdc_encyclopedia.site.context import (
    _grade_class,
    _relative_time,
    _staleness_color,
    build_site_data,
)
from mdc_encyclopedia.site.search_index import build_search_index

logger = logging.getLogger(__name__)


def generate_site(db_path: str, output_dir: str = "site") -> dict:
    """Generate the complete static site from the database.

    Reads DB via context.py, sets up Jinja2, renders all page templates,
    copies static assets, and returns stats.

    Args:
        db_path: Path to the SQLite database file.
        output_dir: Output directory for the generated site.

    Returns:
        Dict with page counts and output path.
    """
    # Connect to DB and build site data
    conn = get_connection(db_path)
    site_data = build_site_data(conn)
    conn.close()

    # Set up Jinja2 environment
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Register custom filters
    env.filters["relative_time"] = _relative_time
    env.filters["staleness_color"] = _staleness_color
    env.filters["grade_class"] = _grade_class
    env.filters["slugify"] = _slugify

    # Create output directory structure
    subdirs = [
        "",
        "browse",
        "dataset",
        "changes",
        "quality",
        "about",
        "static",
    ]
    for subdir in subdirs:
        os.makedirs(os.path.join(output_dir, subdir), exist_ok=True)

    # Render all pages
    stats = {
        "homepage": 0,
        "browse_pages": 0,
        "dataset_pages": 0,
        "changes_page": 0,
        "quality_page": 0,
        "about_page": 0,
        "output_dir": os.path.abspath(output_dir),
    }

    _render_homepage(env, site_data, output_dir)
    stats["homepage"] = 1

    _render_browse_pages(env, site_data, output_dir)
    stats["browse_pages"] = 1 + len(site_data["categories"])  # all-datasets + per-category

    _render_dataset_pages(env, site_data, output_dir)
    stats["dataset_pages"] = len(site_data["datasets"])

    _render_changes_page(env, site_data, output_dir)
    stats["changes_page"] = 1

    _render_quality_page(env, site_data, output_dir)
    stats["quality_page"] = 1

    _render_about_page(env, site_data, output_dir)
    stats["about_page"] = 1

    # Build search index
    index_stats = build_search_index(site_data["datasets"], output_dir)
    stats["index_size_kb"] = round(index_stats["index_size"] / 1024, 1)
    stats["data_size_kb"] = round(index_stats["data_size"] / 1024, 1)

    # Copy static assets
    _copy_static_assets(output_dir)

    total_pages = (
        stats["homepage"]
        + stats["browse_pages"]
        + stats["dataset_pages"]
        + stats["changes_page"]
        + stats["quality_page"]
        + stats["about_page"]
    )
    stats["total_pages"] = total_pages

    logger.info("Generated %d pages in %s", total_pages, output_dir)
    return stats


def _render_page(env, template_name, context, output_path):
    """Render a single template to a file.

    Args:
        env: Jinja2 Environment.
        template_name: Name of the template file.
        context: Dict of template variables.
        output_path: Full path to the output HTML file.
    """
    template = env.get_template(template_name)
    html = template.render(**context)
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def _copy_static_assets(output_dir):
    """Copy style.css and search.js from source static/ to output static/.

    Args:
        output_dir: Root output directory for the generated site.
    """
    source_static = os.path.join(os.path.dirname(__file__), "static")
    dest_static = os.path.join(output_dir, "static")
    os.makedirs(dest_static, exist_ok=True)

    for filename in ["style.css", "search.js", "filter.js"]:
        src = os.path.join(source_static, filename)
        dst = os.path.join(dest_static, filename)
        if os.path.exists(src):
            shutil.copy2(src, dst)
        else:
            logger.warning("Static asset not found: %s", src)


def _render_homepage(env, site_data, output_dir):
    """Render the homepage (index.html).

    Args:
        env: Jinja2 Environment.
        site_data: Complete site data dict from build_site_data.
        output_dir: Root output directory.
    """
    # Build recent datasets list: top 5 by updated_at descending
    datasets_with_dates = [
        ds for ds in site_data["datasets"] if ds.get("updated_at")
    ]
    datasets_with_dates.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
    recent_datasets = datasets_with_dates[:5]

    context = {
        "page_title": "MDC Data Encyclopedia",
        "datasets": site_data["datasets"],
        "categories": site_data["categories"],
        "stats": site_data["stats"],
        "recent_datasets": recent_datasets,
        "generated_at": site_data["generated_at"],
    }
    _render_page(env, "index.html", context, os.path.join(output_dir, "index.html"))


def _render_browse_pages(env, site_data, output_dir):
    """Render category browse pages.

    Creates browse/index.html (all datasets) and
    browse/{category-slug}/index.html for each category.
    Extracts unique formats, publishers, and tags for filter dropdowns.

    Args:
        env: Jinja2 Environment.
        site_data: Complete site data dict.
        output_dir: Root output directory.
    """
    from slugify import slugify as _slugify

    categories = site_data["categories"]
    all_datasets = site_data["datasets"]

    # "Browse All Datasets" page at /browse/index.html
    all_formats, all_publishers, all_tags = _extract_filter_options(all_datasets)
    context = {
        "page_title": "Browse All Datasets",
        "category_name": "Browse All Datasets",
        "datasets": all_datasets,
        "dataset_count": len(all_datasets),
        "formats": sorted(all_formats),
        "publishers": sorted(all_publishers),
        "tags": sorted(all_tags),
        "generated_at": site_data["generated_at"],
    }
    _render_page(
        env, "browse.html", context, os.path.join(output_dir, "browse", "index.html")
    )

    # Per-category browse pages at /browse/{category-slug}/index.html
    for cat_name, cat_datasets in categories.items():
        cat_slug = _slugify(cat_name) if cat_name else "uncategorized"
        cat_formats, cat_publishers, cat_tags = _extract_filter_options(cat_datasets)
        context = {
            "page_title": cat_name,
            "category_name": cat_name,
            "datasets": cat_datasets,
            "dataset_count": len(cat_datasets),
            "formats": sorted(cat_formats),
            "publishers": sorted(cat_publishers),
            "tags": sorted(cat_tags),
            "generated_at": site_data["generated_at"],
        }
        _render_page(
            env,
            "browse.html",
            context,
            os.path.join(output_dir, "browse", cat_slug, "index.html"),
        )


def _extract_filter_options(datasets):
    """Extract unique formats, publishers, and tags from a list of datasets.

    Args:
        datasets: List of dataset dicts.

    Returns:
        Tuple of (formats, publishers, tags) as lists of unique lowercase strings.
    """
    formats = set()
    publishers = set()
    tags = set()

    for ds in datasets:
        fmt = (ds.get("format") or "").strip()
        if fmt:
            formats.add(fmt.lower())
        pub = (ds.get("publisher") or "").strip()
        if pub:
            publishers.add(pub.lower())
        for tag in ds.get("tags_list", []):
            tag = tag.strip()
            if tag:
                tags.add(tag.lower())

    return list(formats), list(publishers), list(tags)


def _render_dataset_pages(env, site_data, output_dir):
    """Render individual dataset detail pages.

    Creates dataset/{slug}/index.html for each dataset so URLs resolve
    as /dataset/{slug}/ with clean paths.

    Args:
        env: Jinja2 Environment.
        site_data: Complete site data dict.
        output_dir: Root output directory.
    """
    for dataset in site_data["datasets"]:
        context = {
            "page_title": dataset.get("title", "Dataset"),
            "dataset": dataset,
            "generated_at": site_data["generated_at"],
        }
        slug = dataset["slug"]
        _render_page(
            env,
            "dataset.html",
            context,
            os.path.join(output_dir, "dataset", slug, "index.html"),
        )


def _render_changes_page(env, site_data, output_dir):
    """Render the What Changed page.

    Groups raw changes records by type (added, removed, schema) and builds
    summary counts for display as stat cards.

    Args:
        env: Jinja2 Environment.
        site_data: Complete site data dict.
        output_dir: Root output directory.
    """
    import json as _json

    raw_changes = site_data["changes"]

    # Build slug lookup for linking to dataset pages
    slug_lookup = {ds["id"]: ds["slug"] for ds in site_data["datasets"]}

    added = []
    removed = []
    schema = []
    detected_at = None

    for ch in raw_changes:
        ds_id = ch.get("dataset_id", "")
        title = ch.get("dataset_title") or ch.get("title") or ds_id
        slug = slug_lookup.get(ds_id)
        change_type = ch.get("change_type", "")

        if detected_at is None and ch.get("detected_at"):
            detected_at = ch["detected_at"]

        # Parse details JSON if available
        details_parsed = ""
        change_description = ""
        details_raw = ch.get("details")
        if details_raw:
            try:
                details_obj = _json.loads(details_raw)
                if isinstance(details_obj, dict):
                    if details_obj.get("title"):
                        title = details_obj["title"]
                    if details_obj.get("columns_added"):
                        cols = details_obj["columns_added"]
                        change_description = (
                            f"{len(cols)} column{'s' if len(cols) != 1 else ''} "
                            f"added: {', '.join(cols[:5])}"
                        )
                        if len(cols) > 5:
                            change_description += f" (+{len(cols) - 5} more)"
                    if details_obj.get("columns_removed"):
                        cols = details_obj["columns_removed"]
                        change_description = (
                            f"{len(cols)} column{'s' if len(cols) != 1 else ''} "
                            f"removed: {', '.join(cols[:5])}"
                        )
                        if len(cols) > 5:
                            change_description += f" (+{len(cols) - 5} more)"
                    details_parsed = str(details_obj)
                else:
                    details_parsed = str(details_raw)
            except (_json.JSONDecodeError, TypeError):
                details_parsed = str(details_raw)

        entry = {
            "dataset_id": ds_id,
            "title": title,
            "slug": slug,
            "source_portal": ch.get("source_portal", ""),
            "category": ch.get("category", ""),
            "details_parsed": details_parsed,
            "change_description": change_description,
        }

        if change_type == "added":
            added.append(entry)
        elif change_type == "removed":
            removed.append(entry)
        elif change_type in ("columns_added", "columns_removed", "schema_changed"):
            schema.append(entry)

    changes_grouped = {
        "added": added,
        "removed": removed,
        "schema": schema,
        "total_added": len(added),
        "total_removed": len(removed),
        "total_schema": len(schema),
        "detected_at": detected_at,
    }

    context = {
        "page_title": "What Changed",
        "changes": changes_grouped,
        "generated_at": site_data["generated_at"],
    }
    _render_page(
        env, "changes.html", context, os.path.join(output_dir, "changes", "index.html")
    )


def _render_quality_page(env, site_data, output_dir):
    """Render the Data Quality report page.

    Passes quality_summary as 'quality' to the template for cleaner access.
    quality_summary contains: total_datasets, avg_score, avg_grade,
    pct_described, stale_count, grade_distribution, top_findings,
    dimension_averages, and below_threshold counts.

    Args:
        env: Jinja2 Environment.
        site_data: Complete site data dict.
        output_dir: Root output directory.
    """
    context = {
        "page_title": "Data Quality",
        "quality": site_data["quality_summary"],
        "stats": site_data["stats"],
        "generated_at": site_data["generated_at"],
    }
    _render_page(
        env, "quality.html", context, os.path.join(output_dir, "quality", "index.html")
    )


def _render_about_page(env, site_data, output_dir):
    """Render the About page.

    Args:
        env: Jinja2 Environment.
        site_data: Complete site data dict.
        output_dir: Root output directory.
    """
    context = {
        "page_title": "About",
        "stats": site_data["stats"],
        "generated_at": site_data["generated_at"],
    }
    _render_page(
        env, "about.html", context, os.path.join(output_dir, "about", "index.html")
    )
