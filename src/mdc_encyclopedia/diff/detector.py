"""Snapshot capture, comparison logic, and change record storage.

Provides the core diffing engine that compares pre-pull and post-pull
database state to detect added, removed, and schema-changed datasets.
"""

import json
from datetime import datetime, timezone

from mdc_encyclopedia.db import (
    get_columns_snapshot,
    get_dataset_ids,
    insert_change,
)


def capture_snapshot(conn) -> dict:
    """Capture current database state for diff comparison.

    Bundles dataset ID and column name queries into a single snapshot
    dict suitable for before/after comparison.

    Args:
        conn: An open sqlite3.Connection with row_factory=sqlite3.Row.

    Returns:
        Dict with keys:
            dataset_ids: set of all dataset ID strings
            columns_by_dataset: dict mapping dataset_id to set of column names
    """
    return {
        "dataset_ids": get_dataset_ids(conn),
        "columns_by_dataset": get_columns_snapshot(conn),
    }


def compute_changes(conn, pre_snapshot: dict, post_snapshot: dict) -> dict:
    """Compare snapshots and insert change records.

    Computes three categories of changes using set operations:
    - Added: datasets in post but not in pre
    - Removed: datasets in pre but not in post
    - Schema changed: datasets in both with different column name sets

    All change records share a single detected_at timestamp so they can
    be grouped as a batch. The caller (pull command) captures snapshots
    before and after ingestion.

    If pre_snapshot has no dataset_ids (first pull), returns zeros
    immediately without inserting anything.

    Args:
        conn: An open sqlite3.Connection (caller manages lifecycle).
        pre_snapshot: Snapshot dict from capture_snapshot before pull.
        post_snapshot: Snapshot dict from capture_snapshot after pull.

    Returns:
        Dict with counts: {added: int, removed: int, schema_changed: int}
    """
    pre_ids = pre_snapshot["dataset_ids"]
    post_ids = post_snapshot["dataset_ids"]

    # First pull: no previous state to compare against
    if not pre_ids:
        return {"added": 0, "removed": 0, "schema_changed": 0}

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
            columns_added = new_cols - old_cols
            columns_removed = old_cols - new_cols
            schema_changes.append((ds_id, columns_added, columns_removed))

    # If nothing changed, skip inserts
    if not added_ids and not removed_ids and not schema_changes:
        return {"added": 0, "removed": 0, "schema_changed": 0}

    # Generate a shared timestamp for all changes in this batch
    detected_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # Insert added dataset records
    for ds_id in sorted(added_ids):
        insert_change(conn, ds_id, "added", None, detected_at)

    # Insert removed dataset records with title stored defensively
    for ds_id in sorted(removed_ids):
        row = conn.execute(
            "SELECT title FROM datasets WHERE id = ?", (ds_id,)
        ).fetchone()
        title = row["title"] if row else None
        details = json.dumps({"title": title})
        insert_change(conn, ds_id, "removed", details, detected_at)

    # Insert schema change records with column diff details
    for ds_id, columns_added, columns_removed in sorted(
        schema_changes, key=lambda x: x[0]
    ):
        details = json.dumps(
            {
                "columns_added": sorted(columns_added),
                "columns_removed": sorted(columns_removed),
            }
        )
        insert_change(conn, ds_id, "schema_changed", details, detected_at)

    conn.commit()

    return {
        "added": len(added_ids),
        "removed": len(removed_ids),
        "schema_changed": len(schema_changes),
    }
