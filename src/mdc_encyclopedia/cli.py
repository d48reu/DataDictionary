"""CLI entry point for MDC Open Data Encyclopedia."""

import json
import logging
import os
import time
from collections import Counter
from datetime import datetime, timezone

import anthropic
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

from mdc_encyclopedia.audit.scorer import audit_dataset
from mdc_encyclopedia.db import (
    get_all_datasets_for_audit,
    get_columns_for_dataset,
    get_connection,
    get_unenriched_datasets,
    init_db,
    insert_enrichment,
    upsert_audit_score,
    upsert_columns,
    upsert_dataset,
)
from mdc_encyclopedia.enrichment.client import (
    create_enrichment_client,
    enrich_dataset,
    estimate_cost,
)
from mdc_encyclopedia.enrichment.models import DEFAULT_MODEL
from mdc_encyclopedia.enrichment.prompts import PROMPT_VERSION
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
@click.option("--dry-run", is_flag=True, help="Show what would be enriched and estimated cost without calling the API.")
@click.option("--resume", is_flag=True, help="Resume enrichment from where it left off (skips already-enriched datasets).")
@click.option("--model", default=DEFAULT_MODEL, show_default=True, help="Anthropic model to use for enrichment.")
@click.option("--limit", type=int, default=None, help="Limit number of datasets to enrich (useful for testing).")
@click.pass_context
def enrich(ctx, dry_run, resume, model, limit):
    """Enrich datasets with AI-generated descriptions and metadata."""
    start_time = time.time()
    db_path = ctx.obj["db_path"]
    conn = get_connection(db_path)

    # Step 1: Get unenriched datasets (resume is implicit -- always skips enriched)
    unenriched = get_unenriched_datasets(conn)
    if not unenriched:
        console.print("[green]All datasets already enriched.[/green]")
        conn.close()
        return

    # Step 2: Apply --limit
    if limit is not None:
        unenriched = unenriched[:limit]

    console.print(f"Found [bold]{len(unenriched)}[/bold] unenriched dataset(s).")

    # Step 3: Check API key early (unless --dry-run)
    client = None
    if not dry_run:
        try:
            client = create_enrichment_client(model=model)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            conn.close()
            raise click.Abort() from exc

    # Step 4: Build column lookup
    columns_by_dataset = {
        ds["id"]: get_columns_for_dataset(conn, ds["id"]) for ds in unenriched
    }

    # Step 5: Cost estimation
    # For dry-run, we need a client for count_tokens
    if dry_run:
        try:
            client = create_enrichment_client(model=model)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            conn.close()
            raise click.Abort() from exc

    cost = estimate_cost(client, model, unenriched, columns_by_dataset)

    # Display cost estimate table
    cost_table = Table(title="Cost Estimate")
    cost_table.add_column("Metric", style="bold")
    cost_table.add_column("Value", justify="right")
    cost_table.add_row("Datasets to enrich", str(cost["dataset_count"]))
    cost_table.add_row("Estimated input tokens", f"{cost['input_tokens']:,}")
    cost_table.add_row("Estimated output tokens", f"{cost['output_tokens_est']:,}")
    cost_table.add_row("Estimated input cost", f"${cost['input_cost']:.4f}")
    cost_table.add_row("Estimated output cost", f"${cost['output_cost_est']:.4f}")
    cost_table.add_row("Estimated total cost", f"${cost['total_est']:.4f}")
    cost_table.add_row("Model", model)
    console.print(cost_table)

    if dry_run:
        # Show unenriched dataset list
        ds_table = Table(title="Unenriched Datasets")
        ds_table.add_column("#", justify="right")
        ds_table.add_column("Title")
        for i, ds in enumerate(unenriched, 1):
            title = ds.get("title", "Unknown") or "Unknown"
            ds_table.add_row(str(i), title[:60])
        console.print(ds_table)
        conn.close()
        return

    # Step 6: Confirmation flow
    if cost["total_est"] > 5.0:
        click.confirm(
            f"Estimated cost exceeds $5 (${cost['total_est']:.2f}). Proceed?",
            abort=True,
        )
    else:
        console.print(
            f"[green]Estimated cost: ${cost['total_est']:.2f} "
            f"(under $5 threshold, auto-proceeding)[/green]"
        )

    # Step 7: Enrichment loop with Rich progress
    enriched_count = 0
    failed_count = 0
    failed_datasets: list[tuple[str, str]] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("datasets"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Enriching", total=len(unenriched))

        for ds in unenriched:
            ds_title = ds.get("title", "Unknown") or "Unknown"
            try:
                result = enrich_dataset(
                    client, model, ds, columns_by_dataset.get(ds["id"], [])
                )
                insert_enrichment(conn, ds["id"], result.model_dump(), PROMPT_VERSION)
                enriched_count += 1
            except (anthropic.APIError, anthropic.RateLimitError) as exc:
                failed_count += 1
                failed_datasets.append((ds_title, str(exc)))
                logger.warning("Failed to enrich '%s': %s", ds_title, exc)
            except Exception as exc:
                failed_count += 1
                failed_datasets.append((ds_title, str(exc)))
                logger.warning("Failed to enrich '%s': %s", ds_title, exc)

            progress.advance(task)
            # Rate limiting delay between API calls
            time.sleep(1)

    # Step 8: Summary table
    elapsed = time.time() - start_time
    elapsed_min = int(elapsed // 60)
    elapsed_sec = int(elapsed % 60)
    elapsed_str = f"{elapsed_min}m {elapsed_sec}s"

    summary_table = Table(title="Enrichment Summary")
    summary_table.add_column("Metric", style="bold")
    summary_table.add_column("Value", justify="right")
    summary_table.add_row("Total enriched", str(enriched_count))
    summary_table.add_row("Failed", str(failed_count))
    summary_table.add_row("Model", model)
    summary_table.add_row("Prompt version", PROMPT_VERSION)
    summary_table.add_row("Elapsed time", elapsed_str)
    console.print(summary_table)

    if failed_datasets:
        fail_table = Table(title="Failed Datasets")
        fail_table.add_column("Dataset")
        fail_table.add_column("Error")
        for ds_title, error in failed_datasets:
            fail_table.add_row(ds_title[:60], error[:80])
        console.print(fail_table)

    # Step 9: Cleanup
    conn.close()


@cli.command()
@click.pass_context
def audit(ctx):
    """Run quality audit on all datasets."""
    db_path = ctx.obj["db_path"]
    conn = get_connection(db_path)

    datasets = get_all_datasets_for_audit(conn)

    if not datasets:
        console.print("[yellow]No datasets found. Run `mdc-encyclopedia pull` first.[/yellow]")
        conn.close()
        return

    now = datetime.now(timezone.utc)
    findings_counter: Counter = Counter()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("datasets"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Auditing", total=len(datasets))

        for dataset_row in datasets:
            result = audit_dataset(dataset_row, now)
            upsert_audit_score(
                conn,
                dataset_row["id"],
                result["composite_score"],
                result["letter_grade"],
                result["staleness"],
                result["completeness"],
                result["documentation"],
                json.dumps(result["findings"]),
            )
            # Accumulate findings for top-findings summary
            for finding in result["findings"]:
                findings_counter[finding] += 1
            progress.advance(task)

    # Grade distribution from the database
    grade_rows = conn.execute(
        "SELECT letter_grade, COUNT(*) as cnt FROM audit_scores GROUP BY letter_grade ORDER BY letter_grade"
    ).fetchall()

    grade_table = Table(title="Audit Summary - Grade Distribution")
    grade_table.add_column("Grade", style="bold")
    grade_table.add_column("Count", justify="right")
    grade_table.add_column("Bar")

    for row in grade_rows:
        grade = row["letter_grade"]
        count = row["cnt"]
        bar = "\u2588" * min(count, 50)
        grade_table.add_row(grade, str(count), bar)

    grade_table.add_section()
    grade_table.add_row("Total", str(len(datasets)), "")

    console.print(grade_table)

    # Top findings
    if findings_counter:
        findings_table = Table(title="Top Findings")
        findings_table.add_column("Finding", style="bold")
        findings_table.add_column("Count", justify="right")

        for finding, count in findings_counter.most_common(5):
            findings_table.add_row(finding, str(count))

        console.print(findings_table)

    conn.close()


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
