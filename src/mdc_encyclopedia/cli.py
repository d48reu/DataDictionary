"""CLI entry point for MDC Open Data Encyclopedia."""

import logging
import os
import time

import rich_click as click
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from mdc_encyclopedia.db import get_connection, init_db, upsert_columns, upsert_dataset
from mdc_encyclopedia.ingestion.field_fetcher import fetch_fields_for_dataset
from mdc_encyclopedia.ingestion.hub_client import (
    create_client,
    detect_duplicate_titles,
    fetch_all_datasets,
)
from mdc_encyclopedia.ingestion.normalizer import normalize_hub_dataset

logger = logging.getLogger(__name__)
console = Console()


def get_default_db_path() -> str:
    """Return absolute default database path using XDG data directory convention."""
    data_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "mdc-encyclopedia")
    return os.path.join(data_dir, "mdc_encyclopedia.db")


@click.group()
@click.version_option(package_name="mdc-encyclopedia")
@click.pass_context
def cli(ctx):
    """MDC Open Data Encyclopedia - catalog, enrich, and publish Miami-Dade County open datasets."""
    ctx.ensure_object(dict)
    db_path = os.environ.get("MDC_ENCYCLOPEDIA_DB", get_default_db_path())
    is_new = init_db(db_path)
    if is_new:
        console.print(f"[green]\u2713[/green] Created database: {os.path.abspath(db_path)}")
    ctx.obj["db_path"] = db_path


@cli.command()
@click.option("--verbose", is_flag=True, help="Show detailed duplicate title pairs.")
@click.pass_context
def pull(ctx, verbose):
    """Pull dataset metadata from Miami-Dade open data portals."""
    start_time = time.time()
    db_path = ctx.obj["db_path"]
    conn = get_connection(db_path)
    client = create_client()

    new_count = 0
    updated_count = 0
    skipped_count = 0
    failed_datasets: list[tuple[str, str]] = []

    # Stage 1: Catalog Fetch
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("datasets"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("ArcGIS Hub", total=0)

            for feature, index, total in fetch_all_datasets(client):
                if index == 1:
                    progress.update(task, total=total)

                try:
                    normalized = normalize_hub_dataset(feature)
                    result = upsert_dataset(conn, normalized)
                    if result == "new":
                        new_count += 1
                    else:
                        updated_count += 1
                except Exception as exc:
                    ds_id = feature.get("id", f"index-{index}")
                    skipped_count += 1
                    failed_datasets.append((ds_id, str(exc)))
                    logger.warning("Failed to process dataset %s: %s", ds_id, exc)

                progress.update(task, completed=index)

    except Exception as exc:
        console.print(f"[red]Catalog fetch failed: {exc}[/red]")
        client.close()
        conn.close()
        raise click.Abort() from exc

    # Stage 2: Field Metadata Fetch
    rows = conn.execute(
        "SELECT id, api_endpoint FROM datasets WHERE api_endpoint IS NOT NULL"
    ).fetchall()

    field_fetch_count = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("datasets"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching fields", total=len(rows))

        for row in rows:
            dataset_id = row["id"]
            api_endpoint = row["api_endpoint"]
            try:
                fields = fetch_fields_for_dataset(client, dataset_id, api_endpoint)
                if fields:
                    upsert_columns(conn, dataset_id, fields)
                    field_fetch_count += 1
            except Exception as exc:
                logger.warning(
                    "Failed to fetch fields for %s: %s", dataset_id, exc
                )

            progress.advance(task)

    # Stage 3: Dedup Detection
    all_datasets = conn.execute("SELECT id, title FROM datasets").fetchall()
    dataset_dicts = [{"id": row["id"], "title": row["title"]} for row in all_datasets]
    duplicates = detect_duplicate_titles(dataset_dicts)
    dup_count = len(duplicates)

    if duplicates:
        dup_lines = [f"  {title} ({len(ids)} copies)" for title, ids in duplicates]
        panel_text = f"[yellow]{dup_count} duplicate title(s) detected:[/yellow]\n"
        panel_text += "\n".join(dup_lines[:10])
        if len(dup_lines) > 10:
            panel_text += f"\n  ... and {len(dup_lines) - 10} more"
        console.print(Panel(panel_text, title="Duplicate Titles", border_style="yellow"))

        if verbose:
            for title, ids in duplicates:
                console.print(f"  [dim]{title}:[/dim] {', '.join(ids)}")

    # Stage 4: Summary Table
    conn.commit()

    datasets_with_fields = conn.execute(
        "SELECT COUNT(DISTINCT dataset_id) FROM columns"
    ).fetchone()[0]

    elapsed = time.time() - start_time
    elapsed_min = int(elapsed // 60)
    elapsed_sec = int(elapsed % 60)
    elapsed_str = f"{elapsed_min}m {elapsed_sec}s"

    total_datasets = new_count + updated_count

    table = Table(title="Pull Summary")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_row("Portal", "ArcGIS Hub")
    table.add_row("Total datasets", str(total_datasets))
    table.add_row("New datasets", str(new_count))
    table.add_row("Updated datasets", str(updated_count))
    table.add_row("Duplicate titles", str(dup_count))
    table.add_row("Datasets with fields", str(datasets_with_fields))
    table.add_row("Skipped/failed", str(skipped_count))
    table.add_row("Elapsed time", elapsed_str)

    console.print(table)

    if failed_datasets:
        fail_table = Table(title="Failed Datasets")
        fail_table.add_column("Dataset ID")
        fail_table.add_column("Error")
        for ds_id, error in failed_datasets:
            fail_table.add_row(ds_id, error[:80])
        console.print(fail_table)

    # Stage 5: Cleanup
    conn.close()
    client.close()


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
