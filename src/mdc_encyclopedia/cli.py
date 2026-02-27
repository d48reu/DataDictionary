"""CLI entry point for MDC Open Data Encyclopedia."""

import json
import logging
import os
import time
from collections import Counter, defaultdict
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
    get_recent_changes,
    get_unenriched_datasets,
    init_db,
    insert_enrichment,
    upsert_audit_score,
    upsert_columns,
    upsert_dataset,
)
from mdc_encyclopedia.diff.detector import capture_snapshot, compute_changes
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
from mdc_encyclopedia.registry import load_registry

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
@click.option(
    "--jurisdiction", "-j", default=None,
    help="Pull from a specific jurisdiction (e.g., broward). Pulls all if omitted.",
)
@click.pass_context
def pull(ctx, verbose, jurisdiction):
    """Pull dataset metadata from registered open data portals."""
    start_time = time.time()
    db_path = ctx.obj["db_path"]
    conn = get_connection(db_path)

    # Load jurisdiction registry
    registry = load_registry()

    # Determine target jurisdictions
    if jurisdiction:
        if jurisdiction not in registry:
            available = ", ".join(sorted(registry.keys()))
            console.print(
                f"[red]Unknown jurisdiction '{jurisdiction}'. "
                f"Available: {available}[/red]"
            )
            conn.close()
            raise click.Abort()
        targets = {jurisdiction: registry[jurisdiction]}
    else:
        targets = registry

    pre_snapshot = capture_snapshot(conn)
    is_first_pull = len(pre_snapshot["dataset_ids"]) == 0

    # Per-jurisdiction results tracking
    jurisdiction_results: list[dict] = []
    total_new = 0
    total_updated = 0
    total_skipped = 0
    all_failed_datasets: list[tuple[str, str]] = []

    # Stage 1: Catalog Fetch -- loop over jurisdictions
    for slug, config in targets.items():
        display_name = config["display_name"]
        hub_url = config["hub_url"]
        console.print(f"\n[bold]Pulling from {display_name}...[/bold]")

        j_new = 0
        j_updated = 0
        j_skipped = 0
        j_error = None

        try:
            client = create_client(hub_url)
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
                    task = progress.add_task(display_name, total=0)

                    for feature, index, total in fetch_all_datasets(client):
                        if index == 1:
                            progress.update(task, total=total)

                        try:
                            normalized = normalize_hub_dataset(
                                feature,
                                jurisdiction=slug,
                                hub_url=hub_url,
                            )
                            result = upsert_dataset(conn, normalized)
                            if result == "new":
                                j_new += 1
                            else:
                                j_updated += 1
                        except Exception as exc:
                            ds_id = feature.get("id", f"index-{index}")
                            j_skipped += 1
                            all_failed_datasets.append((f"{slug}/{ds_id}", str(exc)))
                            logger.warning(
                                "Failed to process dataset %s/%s: %s", slug, ds_id, exc
                            )

                        progress.update(task, completed=index)

                # Field metadata fetch for this jurisdiction's datasets
                rows = conn.execute(
                    "SELECT id, api_endpoint FROM datasets "
                    "WHERE jurisdiction = ? AND api_endpoint IS NOT NULL",
                    (slug,),
                ).fetchall()

                if rows:
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        TaskProgressColumn(),
                        TextColumn("datasets"),
                        TimeElapsedColumn(),
                        console=console,
                    ) as progress:
                        ftask = progress.add_task(
                            f"Fields ({display_name})", total=len(rows)
                        )
                        for row in rows:
                            dataset_id = row["id"]
                            api_endpoint = row["api_endpoint"]
                            try:
                                fields = fetch_fields_for_dataset(
                                    client, dataset_id, api_endpoint
                                )
                                if fields:
                                    upsert_columns(conn, dataset_id, fields)
                            except Exception as exc:
                                logger.warning(
                                    "Failed to fetch fields for %s: %s",
                                    dataset_id, exc,
                                )
                            progress.advance(ftask)

            finally:
                client.close()

        except Exception as exc:
            j_error = str(exc)
            console.print(
                f"[red]Failed to pull from {display_name}: {exc}[/red]"
            )
            logger.warning("Jurisdiction %s failed: %s", slug, exc)

        total_new += j_new
        total_updated += j_updated
        total_skipped += j_skipped

        jurisdiction_results.append({
            "slug": slug,
            "display_name": display_name,
            "new": j_new,
            "updated": j_updated,
            "skipped": j_skipped,
            "error": j_error,
        })

    # Stage 2: Dedup Detection (across all jurisdictions)
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

    # Stage 3: Per-jurisdiction results table
    conn.commit()

    elapsed = time.time() - start_time
    elapsed_min = int(elapsed // 60)
    elapsed_sec = int(elapsed % 60)
    elapsed_str = f"{elapsed_min}m {elapsed_sec}s"

    results_table = Table(title="Pull Summary")
    results_table.add_column("Jurisdiction", style="bold")
    results_table.add_column("New", justify="right")
    results_table.add_column("Updated", justify="right")
    results_table.add_column("Skipped", justify="right")
    results_table.add_column("Status")

    for jr in jurisdiction_results:
        if jr["error"]:
            status = f"[red]ERROR: {jr['error'][:40]}[/red]"
        else:
            status = "[green]OK[/green]"
        results_table.add_row(
            jr["display_name"],
            str(jr["new"]),
            str(jr["updated"]),
            str(jr["skipped"]),
            status,
        )

    results_table.add_section()
    results_table.add_row(
        "Total",
        str(total_new),
        str(total_updated),
        str(total_skipped),
        elapsed_str,
    )

    console.print(results_table)

    if all_failed_datasets:
        fail_table = Table(title="Failed Datasets")
        fail_table.add_column("Dataset ID")
        fail_table.add_column("Error")
        for ds_id, error in all_failed_datasets:
            fail_table.add_row(ds_id, error[:80])
        console.print(fail_table)

    # Stage 4: Change Detection
    if is_first_pull:
        total_now = conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]
        console.print(
            f"[green]First pull -- {total_now} datasets cataloged. "
            f"Future pulls will show changes.[/green]"
        )
    else:
        post_snapshot = capture_snapshot(conn)
        summary = compute_changes(conn, pre_snapshot, post_snapshot)
        if summary["added"] or summary["removed"] or summary["schema_changed"]:
            console.print(
                f"[cyan]{summary['added']} added, {summary['removed']} removed, "
                f"{summary['schema_changed']} with column changes. "
                f"Run `diff` for details.[/cyan]"
            )
        else:
            console.print("[green]No changes detected since last pull.[/green]")

    # Stage 5: Cleanup
    conn.close()


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
@click.option("--latest", is_flag=True, default=True,
              help="Show only the most recent pull's changes (default).")
@click.option("--all", "show_all", is_flag=True, default=False,
              help="Show full change history across all pulls.")
@click.pass_context
def diff(ctx, latest, show_all):
    """Show changes between catalog pulls."""
    db_path = ctx.obj["db_path"]
    conn = get_connection(db_path)

    changes = get_recent_changes(conn)

    if not changes:
        console.print(
            "[yellow]No changes recorded yet. "
            "Changes are tracked starting from the second pull.[/yellow]"
        )
        conn.close()
        return

    # Group changes by detected_at timestamp (each pull produces one batch)
    batches = defaultdict(list)
    for change in changes:
        batches[change["detected_at"]].append(change)

    # Sort batches by timestamp descending (most recent first)
    sorted_timestamps = sorted(batches.keys(), reverse=True)

    # If --latest (default, unless --all), only show most recent batch
    if not show_all:
        sorted_timestamps = sorted_timestamps[:1]

    for ts in sorted_timestamps:
        batch = batches[ts]
        table = Table(title=f"Changes detected: {ts}")
        table.add_column("Type", style="bold", width=12)
        table.add_column("Dataset", no_wrap=False)
        table.add_column("Details", no_wrap=False)

        for change in batch:
            change_type = change["change_type"]
            # Use dataset title if available, fall back to dataset_id
            dataset_label = change.get("title") or change["dataset_id"]

            if change_type == "added":
                style = "green"
                type_label = "+ Added"
                detail = ""
            elif change_type == "removed":
                style = "red"
                type_label = "- Removed"
                # Try to get title from details JSON (stored defensively)
                detail = ""
                if change.get("details"):
                    try:
                        d = json.loads(change["details"])
                        if d.get("title") and not change.get("title"):
                            dataset_label = d["title"]
                    except (json.JSONDecodeError, TypeError):
                        pass
            else:  # schema_changed
                style = "yellow"
                type_label = "~ Schema"
                detail = ""
                if change.get("details"):
                    try:
                        d = json.loads(change["details"])
                        parts = []
                        if d.get("columns_added"):
                            parts.append(f"+{len(d['columns_added'])} cols")
                        if d.get("columns_removed"):
                            parts.append(f"-{len(d['columns_removed'])} cols")
                        detail = ", ".join(parts)
                    except (json.JSONDecodeError, TypeError):
                        pass

            table.add_row(type_label, dataset_label[:80], detail, style=style)

        # Add summary row
        added_count = sum(1 for c in batch if c["change_type"] == "added")
        removed_count = sum(1 for c in batch if c["change_type"] == "removed")
        schema_count = sum(1 for c in batch if c["change_type"] == "schema_changed")

        table.add_section()
        table.add_row(
            "Total",
            f"{len(batch)} change(s)",
            f"{added_count} added, {removed_count} removed, {schema_count} schema",
            style="bold",
        )

        console.print(table)

    if not show_all and len(list(batches.keys())) > 1:
        total_batches = len(batches)
        console.print(
            f"\n[dim]Showing latest pull only. "
            f"Use --all to see all {total_batches} recorded pull(s).[/dim]"
        )

    conn.close()


@cli.command(name="export")
@click.option("--output", "-o", default="site", help="Output directory for the generated site.")
@click.option("--base-url", default="", help="Base URL prefix for GitHub Pages (e.g. /DataDictionary).")
@click.option("--site-url", default=None,
              help="Full site URL for feed generation (e.g. https://example.github.io/DataDictionary). Required for Atom feed.")
@click.pass_context
def export_site(ctx, output, base_url, site_url):
    """Generate static HTML site from the catalog database."""
    from mdc_encyclopedia.site.generator import generate_site

    db_path = ctx.obj["db_path"]
    # Strip trailing slash from base_url
    base_url = base_url.rstrip("/")

    if not site_url:
        console.print(
            "[yellow]Warning: --site-url not provided. "
            "Atom feed will not be generated. "
            "Pass --site-url to enable feed generation.[/yellow]"
        )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        progress.add_task("Generating site...", total=None)
        stats = generate_site(db_path, output, base_url=base_url, site_url=site_url)

    table = Table(title="Export Summary")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_row("Dataset pages", str(stats.get("dataset_pages", 0)))
    table.add_row("Category pages", str(stats.get("browse_pages", 0)))
    table.add_row("Total pages", str(stats.get("total_pages", 0)))
    table.add_row("Output directory", stats.get("output_dir", output))
    if stats.get("feed_entries") is not None:
        table.add_row("Feed entries", str(stats["feed_entries"]))
    if stats.get("catalog_dataset_count") is not None:
        table.add_row("Catalog datasets", str(stats["catalog_dataset_count"]))
        table.add_row("Catalog JSON", f"{round(stats.get('catalog_json_size', 0) / 1024, 1)} KB")
        table.add_row("Catalog CSV", f"{round(stats.get('catalog_csv_size', 0) / 1024, 1)} KB")

    console.print(table)
    console.print(f"[green]Site generated in {output}/[/green]")


@cli.command()
@click.option("--port", "-p", default=8000, help="Port to serve on.")
@click.option("--directory", "-d", default="site", help="Directory to serve.")
def serve(port, directory):
    """Start a local preview server for the static site."""
    import functools
    import http.server
    import socketserver

    if not os.path.isdir(directory):
        console.print(
            f"[red]Directory '{directory}' does not exist. "
            f"Run `mdc-encyclopedia export` first.[/red]"
        )
        raise click.Abort()

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=directory
    )

    console.print(
        f"[green]Serving {directory}/ at http://localhost:{port}[/green]"
    )
    console.print("[dim]Press Ctrl+C to stop.[/dim]")

    try:
        with socketserver.TCPServer(("", port), handler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped.[/yellow]")


@cli.command()
@click.pass_context
def stats(ctx):
    """Show database summary: dataset counts, enrichment status, quality overview."""
    db_path = ctx.obj["db_path"]
    conn = get_connection(db_path)

    # Total datasets
    total_datasets = conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]

    if total_datasets == 0:
        console.print("[yellow]No datasets in database. Run `mdc-encyclopedia pull` first.[/yellow]")
        conn.close()
        return

    # Section 1: Datasets by Portal
    portal_rows = conn.execute(
        "SELECT source_portal, COUNT(*) as cnt FROM datasets GROUP BY source_portal"
    ).fetchall()

    portal_table = Table(title="Datasets by Portal")
    portal_table.add_column("Portal", style="bold")
    portal_table.add_column("Count", justify="right")

    for row in portal_rows:
        portal_table.add_row(row["source_portal"], str(row["cnt"]))

    portal_table.add_section()
    portal_table.add_row("Total", str(total_datasets))

    console.print(portal_table)

    # Section 1b: Datasets by Jurisdiction
    jurisdiction_rows = conn.execute(
        "SELECT jurisdiction, COUNT(*) as cnt FROM datasets "
        "GROUP BY jurisdiction ORDER BY jurisdiction"
    ).fetchall()

    jurisdiction_table = Table(title="Datasets by Jurisdiction")
    jurisdiction_table.add_column("Jurisdiction", style="bold")
    jurisdiction_table.add_column("Count", justify="right")

    for row in jurisdiction_rows:
        jurisdiction_table.add_row(row["jurisdiction"], str(row["cnt"]))

    jurisdiction_table.add_section()
    jurisdiction_table.add_row("Total", str(total_datasets))

    console.print(jurisdiction_table)

    # Section 2: Enrichment Status
    enriched_count = conn.execute("SELECT COUNT(*) FROM enrichments").fetchone()[0]
    pending_count = total_datasets - enriched_count

    enrichment_table = Table(title="Enrichment Status")
    enrichment_table.add_column("Status", style="bold")
    enrichment_table.add_column("Count", justify="right")

    enrichment_table.add_row("[green]Enriched[/green]", str(enriched_count))
    enrichment_table.add_row("[yellow]Pending[/yellow]", str(pending_count))

    console.print(enrichment_table)

    # Section 3: Quality Score Distribution (conditional)
    audit_count = conn.execute("SELECT COUNT(*) FROM audit_scores").fetchone()[0]

    if audit_count > 0:
        grade_rows = conn.execute(
            "SELECT letter_grade, COUNT(*) as cnt FROM audit_scores GROUP BY letter_grade ORDER BY letter_grade"
        ).fetchall()

        grade_colors = {"A": "green", "B": "blue", "C": "yellow", "D": "red", "F": "bold red"}

        quality_table = Table(title="Quality Score Distribution")
        quality_table.add_column("Grade", style="bold")
        quality_table.add_column("Count", justify="right")
        quality_table.add_column("Percentage", justify="right")

        for row in grade_rows:
            grade = row["letter_grade"]
            count = row["cnt"]
            pct = (count / audit_count) * 100
            color = grade_colors.get(grade, "white")
            quality_table.add_row(
                f"[{color}]{grade}[/{color}]",
                str(count),
                f"{pct:.1f}%",
            )

        console.print(quality_table)

        # Section 4: Top Findings (conditional)
        findings_rows = conn.execute(
            "SELECT findings_json FROM audit_scores WHERE findings_json IS NOT NULL"
        ).fetchall()

        findings_counter: Counter = Counter()
        for row in findings_rows:
            try:
                findings_list = json.loads(row["findings_json"])
                for finding in findings_list:
                    findings_counter[finding] += 1
            except (json.JSONDecodeError, TypeError):
                pass

        if findings_counter:
            findings_table = Table(title="Top Findings")
            findings_table.add_column("Finding", style="bold")
            findings_table.add_column("Count", justify="right")

            for finding, count in findings_counter.most_common(5):
                findings_table.add_row(finding, str(count))

            console.print(findings_table)
    else:
        console.print(
            Panel("[yellow]No audit data. Run `mdc-encyclopedia audit` first.[/yellow]", title="Quality Scores")
        )

    conn.close()
