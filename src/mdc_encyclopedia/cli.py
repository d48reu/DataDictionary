"""CLI entry point for MDC Open Data Encyclopedia."""

import os

import rich_click as click
from rich.console import Console

from mdc_encyclopedia.db import init_db

console = Console()


@click.group()
@click.version_option(package_name="mdc-encyclopedia")
@click.pass_context
def cli(ctx):
    """MDC Open Data Encyclopedia - catalog, enrich, and publish Miami-Dade County open datasets."""
    ctx.ensure_object(dict)
    db_path = os.environ.get("MDC_ENCYCLOPEDIA_DB", "mdc_encyclopedia.db")
    is_new = init_db(db_path)
    if is_new:
        console.print(f"[green]\u2713[/green] Created database: {db_path}")
    ctx.obj["db_path"] = db_path


@cli.command()
def pull():
    """Pull dataset metadata from Miami-Dade open data portals."""
    console.print("[yellow]Not yet implemented[/yellow]")


@cli.command()
def enrich():
    """Enrich datasets with AI-generated descriptions and metadata."""
    console.print("[yellow]Not yet implemented[/yellow]")


@cli.command()
def audit():
    """Run quality audit on all datasets."""
    console.print("[yellow]Not yet implemented[/yellow]")


@cli.command()
def diff():
    """Show changes between the current and previous catalog pulls."""
    console.print("[yellow]Not yet implemented[/yellow]")


@cli.command()
def export():
    """Generate static HTML site from the catalog database."""
    console.print("[yellow]Not yet implemented[/yellow]")


@cli.command()
def serve():
    """Start a local preview server for the static site."""
    console.print("[yellow]Not yet implemented[/yellow]")


@cli.command()
def stats():
    """Show database summary: dataset counts, enrichment status, quality overview."""
    console.print("[yellow]Not yet implemented[/yellow]")
