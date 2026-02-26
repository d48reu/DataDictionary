"""Main export orchestrator: reads DB, renders templates, writes static files."""

import logging
import os
import shutil

from jinja2 import Environment, FileSystemLoader

from mdc_encyclopedia.db import get_connection
from mdc_encyclopedia.site.context import (
    _grade_class,
    _relative_time,
    _staleness_color,
    build_site_data,
)

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
    stats["browse_pages"] = len(site_data["categories"])

    _render_dataset_pages(env, site_data, output_dir)
    stats["dataset_pages"] = len(site_data["datasets"])

    _render_changes_page(env, site_data, output_dir)
    stats["changes_page"] = 1

    _render_quality_page(env, site_data, output_dir)
    stats["quality_page"] = 1

    _render_about_page(env, site_data, output_dir)
    stats["about_page"] = 1

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

    for filename in ["style.css", "search.js"]:
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
    context = {
        "page_title": "MDC Data Encyclopedia",
        "datasets": site_data["datasets"],
        "categories": site_data["categories"],
        "stats": site_data["stats"],
        "generated_at": site_data["generated_at"],
    }
    _render_page(env, "index.html", context, os.path.join(output_dir, "index.html"))


def _render_browse_pages(env, site_data, output_dir):
    """Render category browse pages.

    Creates browse/index.html (all categories) and browse/{category-slug}.html
    for each category.

    Args:
        env: Jinja2 Environment.
        site_data: Complete site data dict.
        output_dir: Root output directory.
    """
    categories = site_data["categories"]

    # Browse index page
    context = {
        "page_title": "Browse Datasets",
        "categories": categories,
        "stats": site_data["stats"],
        "generated_at": site_data["generated_at"],
    }
    _render_page(
        env, "browse.html", context, os.path.join(output_dir, "browse", "index.html")
    )


def _render_dataset_pages(env, site_data, output_dir):
    """Render individual dataset detail pages.

    Creates dataset/{slug}.html for each dataset.

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
            os.path.join(output_dir, "dataset", f"{slug}.html"),
        )


def _render_changes_page(env, site_data, output_dir):
    """Render the What Changed page.

    Args:
        env: Jinja2 Environment.
        site_data: Complete site data dict.
        output_dir: Root output directory.
    """
    context = {
        "page_title": "What Changed",
        "changes": site_data["changes"],
        "generated_at": site_data["generated_at"],
    }
    _render_page(
        env, "changes.html", context, os.path.join(output_dir, "changes", "index.html")
    )


def _render_quality_page(env, site_data, output_dir):
    """Render the Data Quality report page.

    Args:
        env: Jinja2 Environment.
        site_data: Complete site data dict.
        output_dir: Root output directory.
    """
    context = {
        "page_title": "Data Quality",
        "quality_summary": site_data["quality_summary"],
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
