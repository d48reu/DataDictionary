# Phase 5: Change Detection - Research

**Researched:** 2026-02-25
**Domain:** SQLite snapshot-based catalog diffing, CLI output formatting
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Structural changes only: dataset added, dataset removed, columns added/removed on existing datasets
- No metadata change tracking (description, tags, row_count changes are ignored)
- Column changes limited to additions and removals -- no type change or rename detection
- Removed datasets reported honestly as removed; no soft-delete grace period or API-flakiness handling
- If a dataset disappears then reappears, it shows as "removed" then "added" in successive diffs
- Append-only changelog: each pull appends new change records with timestamps
- Enables "history of changes over time" on the static site
- Running `diff` displays stored results; it does not recompute
- `pull` automatically computes and stores the diff after ingestion completes
- Pull prints a one-liner count summary: "3 added, 1 removed, 5 with column changes. Run `diff` for details."
- First pull (no previous state): print "First pull -- {N} datasets cataloged. Future pulls will show changes."
- `diff` command displays the full detailed breakdown of stored change records

### Claude's Discretion
- Diff output formatting and Rich table layout
- Snapshot mechanism (how "previous state" is captured for comparison)
- Schema design for the changes table
- How `diff` groups and sorts the output (by change type, by dataset, etc.)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DIFF-01 | CLI compares current pull against previous pull state | Snapshot-before-pull pattern captures dataset IDs and column names pre-ingestion; post-pull comparison detects adds/removes/schema changes |
| DIFF-02 | Diff identifies newly added datasets | Set difference: `post_pull_ids - pre_pull_ids` yields new datasets |
| DIFF-03 | Diff identifies removed datasets | Set difference: `pre_pull_ids - post_pull_ids` yields removed datasets |
| DIFF-04 | Diff identifies schema changes (column additions/removals) | Per-dataset column name set comparison for datasets present in both pre and post snapshots |
| DIFF-05 | Diff results stored in SQLite for site generation | Existing `changes` table in V1 schema already has the right structure; append-only inserts with `detected_at` timestamp |
| CLI-07 | `diff` command shows changes between pulls | Rich-formatted grouped output reading from `changes` table, grouped by `detected_at` timestamp batches |
</phase_requirements>

## Summary

Phase 5 adds change detection to the MDC Encyclopedia pipeline. The core challenge is that the current `pull` command overwrites dataset rows in-place via `INSERT OR REPLACE`, destroying the previous state needed for comparison. The solution is a **snapshot-before-pull** pattern: capture the set of dataset IDs and per-dataset column names from SQLite before ingestion begins, then compare against the post-ingestion state to detect additions, removals, and schema changes.

The `changes` table already exists in the V1 schema (`id`, `dataset_id`, `change_type`, `details`, `detected_at`) and requires no migration. Change records are appended during each pull, and the `diff` CLI command reads and displays them using Rich tables. The implementation is straightforward Python set operations -- no external diffing libraries are needed.

**Primary recommendation:** Use in-memory snapshots (Python sets/dicts) captured before the pull begins, compare against post-pull database state, and insert results into the existing `changes` table. Keep the diffing logic in a dedicated `diff` module separate from both `db.py` and `cli.py`.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib | Change record storage and snapshot queries | Already used throughout project; `changes` table exists |
| rich | >=13.0 | Diff output formatting with colored tables | Already a project dependency; supports per-row styling |
| rich-click | >=1.8 | CLI command registration | Already used for all commands |
| click | >=8.0 | Command decorator and context passing | Already used; `@click.pass_context` for db_path access |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json (stdlib) | stdlib | Serialize column change details | For storing added/removed column lists in `details` field |
| datetime (stdlib) | stdlib | Timestamp formatting for display | For formatting `detected_at` in human-readable form |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| In-memory snapshot sets | SQLite shadow/history table | Shadow table adds schema complexity for no benefit -- catalog is small enough (<2000 datasets) for in-memory sets |
| Manual set comparison | Python `difflib` | difflib is for text/sequence diffs, not set membership; overkill for structural change detection |
| Append-only changes table | Separate snapshots table with full copies | Snapshots table would store redundant data; append-only changelog is cleaner for the static site consumer |

**Installation:**
No new dependencies needed. All libraries are already in `pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure
```
src/mdc_encyclopedia/
├── diff/
│   ├── __init__.py      # Module init
│   └── detector.py      # Snapshot capture, comparison logic, change storage
├── db.py                # Add snapshot query helpers and change insert functions
└── cli.py               # Add diff command implementation, modify pull command
```

### Pattern 1: Snapshot-Before-Pull
**What:** Before the pull overwrites data, capture the current state as lightweight Python data structures (sets of IDs, dict of dataset_id -> set of column names). After the pull completes, query the new state and compute set differences.

**When to use:** When the data store uses INSERT OR REPLACE (destructive upsert) and you need to detect what changed.

**Example:**
```python
# Before pull begins
def capture_snapshot(conn: sqlite3.Connection) -> dict:
    """Capture pre-pull state for diff comparison.

    Returns dict with:
        dataset_ids: set of all dataset IDs
        columns_by_dataset: dict mapping dataset_id -> set of column names
    """
    rows = conn.execute("SELECT id FROM datasets").fetchall()
    dataset_ids = {row["id"] for row in rows}

    col_rows = conn.execute(
        "SELECT dataset_id, name FROM columns"
    ).fetchall()
    columns_by_dataset: dict[str, set[str]] = {}
    for row in col_rows:
        ds_id = row["dataset_id"]
        if ds_id not in columns_by_dataset:
            columns_by_dataset[ds_id] = set()
        columns_by_dataset[ds_id].add(row["name"])

    return {
        "dataset_ids": dataset_ids,
        "columns_by_dataset": columns_by_dataset,
    }
```

### Pattern 2: Compute and Store Changes
**What:** After the pull, capture the new state the same way, then compute three categories of changes using set operations. Insert each change as a row in the `changes` table with a shared `detected_at` timestamp.

**When to use:** Immediately after pull ingestion completes, before printing summary.

**Example:**
```python
import json

def compute_changes(
    conn: sqlite3.Connection,
    pre_snapshot: dict,
    post_snapshot: dict,
) -> dict:
    """Compare snapshots and insert change records.

    Returns summary counts: {added: int, removed: int, schema_changed: int}
    """
    pre_ids = pre_snapshot["dataset_ids"]
    post_ids = post_snapshot["dataset_ids"]
    pre_cols = pre_snapshot["columns_by_dataset"]
    post_cols = post_snapshot["columns_by_dataset"]

    added_ids = post_ids - pre_ids
    removed_ids = pre_ids - post_ids

    # Schema changes: datasets in both snapshots with different column sets
    common_ids = pre_ids & post_ids
    schema_changes = []
    for ds_id in common_ids:
        old_cols = pre_cols.get(ds_id, set())
        new_cols = post_cols.get(ds_id, set())
        if old_cols != new_cols:
            added_cols = new_cols - old_cols
            removed_cols = old_cols - new_cols
            schema_changes.append((ds_id, added_cols, removed_cols))

    # Insert change records with shared timestamp
    for ds_id in added_ids:
        conn.execute(
            "INSERT INTO changes (dataset_id, change_type, details) VALUES (?, ?, ?)",
            (ds_id, "added", None),
        )

    for ds_id in removed_ids:
        conn.execute(
            "INSERT INTO changes (dataset_id, change_type, details) VALUES (?, ?, ?)",
            (ds_id, "removed", None),
        )

    for ds_id, added_cols, removed_cols in schema_changes:
        details = json.dumps({
            "columns_added": sorted(added_cols),
            "columns_removed": sorted(removed_cols),
        })
        conn.execute(
            "INSERT INTO changes (dataset_id, change_type, details) VALUES (?, ?, ?)",
            (ds_id, "schema_changed", details),
        )

    conn.commit()
    return {
        "added": len(added_ids),
        "removed": len(removed_ids),
        "schema_changed": len(schema_changes),
    }
```

### Pattern 3: Diff Display with Grouped Rich Tables
**What:** The `diff` command reads from the `changes` table, groups by `detected_at` timestamp (or most recent batch), and displays using Rich tables with per-change-type styling.

**When to use:** For the `diff` CLI command output.

**Example:**
```python
from rich.table import Table
from rich.console import Console
from rich.panel import Panel

console = Console()

# Group changes by detected_at for "per-pull" display
# Most recent batch first
table = Table(title="Changes Detected")
table.add_column("Type", style="bold")
table.add_column("Dataset")
table.add_column("Details")

for change in changes:
    if change["change_type"] == "added":
        style = "green"
        type_label = "+ Added"
    elif change["change_type"] == "removed":
        style = "red"
        type_label = "- Removed"
    else:
        style = "yellow"
        type_label = "~ Schema"

    table.add_row(type_label, change["title"] or change["dataset_id"],
                  change.get("details_summary", ""), style=style)

console.print(table)
```

### Pattern 4: First-Pull Detection
**What:** Before computing the diff, check if the pre-snapshot is empty (no datasets existed before this pull). If so, skip diff computation and print the first-pull message instead.

**When to use:** In the pull command, after capturing the pre-snapshot.

**Example:**
```python
pre_snapshot = capture_snapshot(conn)

if not pre_snapshot["dataset_ids"]:
    # First pull -- no previous state to compare against
    # After pull completes:
    post_count = conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]
    console.print(
        f"[green]First pull -- {post_count} datasets cataloged. "
        f"Future pulls will show changes.[/green]"
    )
else:
    # Normal pull -- compute and store diff
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
```

### Anti-Patterns to Avoid
- **Storing full dataset copies as snapshots:** The catalog is <2000 datasets. Storing full row copies in a shadow table is unnecessary complexity. In-memory sets of IDs and column names are sufficient and ephemeral.
- **Recomputing diff on every `diff` command call:** The user decision explicitly says `diff` displays stored results, not recomputes. All computation happens during `pull`.
- **Using pulled_at to detect "previous state":** The `pulled_at` column is overwritten on every upsert. It cannot distinguish "this dataset existed before this pull" from "this dataset was just refreshed." Use the pre-pull snapshot instead.
- **Deleting removed datasets from the datasets table:** The `pull` command does `INSERT OR REPLACE` but never deletes. Removed datasets stay in the DB. The diff detects removal by comparing the set of IDs returned by the API against what was in the DB before. However, stale datasets should NOT be deleted from the datasets table -- they remain for reference. The `changes` table records the removal event.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Set comparison | Custom loop iterating both lists | Python `set` operations (`-`, `&`) | Set operations are O(n), correct by construction, and readable |
| JSON serialization of column changes | String concatenation | `json.dumps()` / `json.loads()` | Structured data in the `details` column; stdlib handles edge cases |
| Rich table styling | ANSI escape codes | Rich `Table.add_row(style=...)` | Rich handles terminal width, color support detection, and alignment |
| Timestamp grouping for display | Manual string parsing | SQLite `GROUP BY` or `DISTINCT detected_at` | Let the DB handle grouping; detected_at uses `datetime('now')` default |

**Key insight:** This phase is fundamentally about set membership comparison (which datasets exist, which columns exist per dataset). Python's built-in `set` type handles all three diff categories cleanly. No diffing library is needed.

## Common Pitfalls

### Pitfall 1: Snapshot Timing vs. Commit Timing
**What goes wrong:** If the pre-snapshot is captured after the pull has already started inserting rows, new datasets appear in both snapshots and are missed as "added."
**Why it happens:** The snapshot must be captured BEFORE any `upsert_dataset` calls in the pull command, but the code might capture it too late.
**How to avoid:** Capture the snapshot as the very first operation inside the `pull` command, before Stage 1 (catalog fetch) begins. The snapshot reads from the DB, the pull writes to it, and the post-snapshot reads the new state.
**Warning signs:** Running pull twice in a row shows 0 additions when it should show new datasets.

### Pitfall 2: Removed Dataset Detection When Pull Fails Partway
**What goes wrong:** If the API returns only 50 of 200 datasets (network error mid-pull), the diff would incorrectly report 150 datasets as "removed."
**Why it happens:** The post-snapshot only reflects what was successfully ingested, not the full catalog.
**How to avoid:** The user's locked decision says "removed datasets reported honestly as removed; no soft-delete grace period or API-flakiness handling." This means partial pulls WILL produce false removal events. This is acceptable per the user's decision. However, document this behavior clearly. If the pull command aborts (raises `click.Abort()`), it should skip diff computation entirely -- only compute diffs on successful pulls.
**Warning signs:** Large numbers of "removed" datasets after a pull that had network errors.

### Pitfall 3: Column Snapshot Misses Datasets Without Fields
**What goes wrong:** Datasets with `api_endpoint IS NULL` (File Geodatabases) have no column records. If a dataset transitions from having columns to not (or vice versa), the diff might incorrectly report schema changes.
**Why it happens:** The `columns` table only contains rows for datasets that have fetchable fields.
**How to avoid:** When comparing column sets, treat "no rows in columns table" as an empty set. Only report schema_changed when the column set genuinely differs (empty-to-empty is not a change).
**Warning signs:** Schema changes reported for datasets that never had columns.

### Pitfall 4: Duplicate Change Records on Re-runs
**What goes wrong:** If the user runs `pull` twice rapidly without the catalog changing, the second pull should produce no new change records. But if the snapshot/comparison logic has a bug, it might insert duplicate "added" records.
**Why it happens:** The changes table is append-only with no uniqueness constraint on (dataset_id, change_type, detected_at).
**How to avoid:** The comparison logic is inherently safe: if the pre and post snapshots are identical, all set differences are empty, and no records are inserted. Verify this in testing.
**Warning signs:** Duplicate entries in `changes` table with near-identical timestamps.

### Pitfall 5: The diff Command Showing Empty Results After First Pull
**What goes wrong:** After the first pull, `diff` shows nothing because no change records were stored (first pull has no previous state to compare against).
**Why it happens:** The first pull correctly skips diff computation. But the user might expect `diff` to show something.
**How to avoid:** The `diff` command should handle the case where the `changes` table is empty with a user-friendly message: "No changes recorded yet. Changes are tracked after the second pull." This is distinct from "no changes detected" (which means a pull ran but found no differences).
**Warning signs:** Confused user running `diff` immediately after first pull.

## Code Examples

### Snapshot Query Helper (for db.py)
```python
def get_dataset_ids(conn: sqlite3.Connection) -> set[str]:
    """Get all dataset IDs currently in the database."""
    rows = conn.execute("SELECT id FROM datasets").fetchall()
    return {row["id"] for row in rows}

def get_columns_snapshot(conn: sqlite3.Connection) -> dict[str, set[str]]:
    """Get column names grouped by dataset_id."""
    rows = conn.execute("SELECT dataset_id, name FROM columns").fetchall()
    result: dict[str, set[str]] = {}
    for row in rows:
        ds_id = row["dataset_id"]
        if ds_id not in result:
            result[ds_id] = set()
        result[ds_id].add(row["name"])
    return result
```

### Change Record Insert Helper (for db.py)
```python
def insert_change(
    conn: sqlite3.Connection,
    dataset_id: str,
    change_type: str,
    details: str | None = None,
) -> None:
    """Insert a change record into the changes table.

    Uses the default datetime('now') for detected_at so all changes
    from a single pull share approximately the same timestamp.
    """
    conn.execute(
        "INSERT INTO changes (dataset_id, change_type, details) VALUES (?, ?, ?)",
        (dataset_id, change_type, details),
    )
```

### Reading Changes for Display (for db.py)
```python
def get_recent_changes(conn: sqlite3.Connection, limit: int | None = None) -> list[dict]:
    """Get change records joined with dataset titles, most recent first.

    Joins with datasets table to get titles for added/schema_changed records.
    Removed datasets may not have a row in datasets, so LEFT JOIN is needed
    from changes to datasets.
    """
    query = """
        SELECT c.id, c.dataset_id, c.change_type, c.details, c.detected_at,
               d.title
        FROM changes c
        LEFT JOIN datasets d ON c.dataset_id = d.id
        ORDER BY c.detected_at DESC, c.change_type, c.dataset_id
    """
    if limit:
        query += f" LIMIT {limit}"

    rows = conn.execute(query).fetchall()
    return [dict(row) for row in rows]
```

### Diff Command Output Pattern
```python
@cli.command()
@click.option("--latest", is_flag=True, default=False,
              help="Show only the most recent pull's changes.")
@click.pass_context
def diff(ctx):
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

    # Group by detected_at timestamp (batch)
    # Display with Rich tables, color-coded by change type
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Full database snapshots before each operation | Lightweight in-memory set snapshots | Standard practice | Avoids doubling storage for change tracking |
| Custom diff algorithms | Set operations on IDs/names | Always been standard | Correct by construction for membership-based changes |
| Storing diffs as text blobs | Structured JSON in details column | Standard practice | Enables programmatic consumption by static site generator |

**Deprecated/outdated:**
- None relevant. This phase uses only Python stdlib and existing project dependencies.

## Open Questions

1. **Removed dataset title resolution**
   - What we know: When a dataset is removed, its row stays in the `datasets` table (the pull never deletes rows). So `LEFT JOIN datasets` should still resolve titles for removed datasets.
   - What's unclear: If a future phase adds cleanup of stale datasets, removed dataset titles would be lost. The `details` field could store the title at removal time as a safety measure.
   - Recommendation: Store the dataset title in the `details` JSON for "removed" change records as a defensive measure. Low cost, high future-proofing value.

2. **Diff grouping by pull batch**
   - What we know: All change records from a single pull share the same `detected_at` timestamp (from SQLite `datetime('now')` default). This naturally groups changes by pull.
   - What's unclear: If a pull takes longer than 1 second, `datetime('now')` called at different insert times could produce slightly different timestamps. SQLite's `datetime('now')` resolution is 1 second.
   - Recommendation: Pass an explicit timestamp to `insert_change` rather than relying on the DEFAULT. This guarantees all changes from one pull share exactly the same `detected_at` value, enabling clean grouping.

3. **Diff output for `--latest` flag**
   - What we know: The CONTEXT.md says `diff` shows stored results. It doesn't specify whether it shows ALL historical changes or just the latest batch.
   - What's unclear: Should the default show all changes ever, or just the most recent pull's changes?
   - Recommendation: Default to showing the most recent pull's changes (most useful for day-to-day use). Add a `--all` flag for full history. This is Claude's discretion per CONTEXT.md.

## Sources

### Primary (HIGH confidence)
- Project codebase analysis: `db.py`, `cli.py`, `hub_client.py`, `normalizer.py`, `field_fetcher.py` -- direct inspection of existing schema, pull flow, and upsert patterns
- Context7 `/websites/rich_readthedocs_io_en_stable` -- Rich Table styling, `add_row(style=...)`, table options for grouped display
- Context7 `/pallets/click` -- `@click.pass_context` pattern for accessing `ctx.obj["db_path"]` in commands

### Secondary (MEDIUM confidence)
- SQLite documentation on `datetime('now')` behavior -- 1-second resolution, UTC, deterministic within a single statement but not across statements in a transaction

### Tertiary (LOW confidence)
- None. All findings verified against codebase and official documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in use; no new dependencies
- Architecture: HIGH - Snapshot-before-pull is a well-understood pattern; existing `changes` table matches requirements exactly
- Pitfalls: HIGH - Identified from direct codebase analysis (INSERT OR REPLACE behavior, column deletion pattern, first-pull edge case)

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (stable domain, no fast-moving dependencies)
