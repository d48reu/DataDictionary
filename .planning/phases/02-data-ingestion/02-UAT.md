---
status: diagnosed
phase: 02-data-ingestion
source: [02-01-SUMMARY.md, 02-02-SUMMARY.md]
started: 2026-02-25T02:30:00Z
updated: 2026-02-25T02:45:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Pull command fetches full catalog
expected: Running `mdc-encyclopedia pull` fetches all ~576 datasets from ArcGIS Hub with a Rich progress bar showing count and elapsed time. Command completes without errors.
result: pass

### 2. Database contains dataset records
expected: After pull completes, querying the SQLite database shows 570+ dataset records with populated title, description (plain text, no HTML tags), category, publisher, and ISO 8601 timestamps.
result: issue
reported: "Database has 0 records. The pull command created the DB and tables but no data was inserted. Need to debug the ingestion."
severity: blocker

### 3. Field metadata stored
expected: After pull, the columns/fields table contains field metadata for Feature Service datasets — field name, type, and alias. File Geodatabase datasets are skipped gracefully (no errors).
result: skipped
reason: Blocked by test 2 — no data in database

### 4. Duplicate title detection
expected: Pull detects any within-catalog duplicate titles and displays a Rich panel with duplicate count. Running with `--verbose` shows per-pair detail of which datasets share titles.
result: skipped
reason: Blocked by test 2 — no data in database

### 5. Rich summary table
expected: After pull completes, a Rich summary table displays: total datasets, portal breakdown (ArcGIS Hub: N), deduplicated count, new vs updated counts, skipped/failed (if any), and elapsed time.
result: skipped
reason: Blocked by test 2 — no data in database

### 6. Rate limiting observed
expected: During pull, the progress bar advances at roughly 1 dataset per second (visible pacing), confirming the 1 req/s rate limit is active. The full pull takes approximately 10 minutes for ~576 datasets.
result: pass

## Summary

total: 6
passed: 2
issues: 1
pending: 0
skipped: 3

## Gaps

- truth: "After pull completes, SQLite database contains 570+ dataset records with populated metadata fields"
  status: failed
  reason: "User reported: Database has 0 records. The pull command created the DB and tables but no data was inserted. Need to debug the ingestion."
  severity: blocker
  test: 2
  root_cause: "Database path is relative ('mdc_encyclopedia.db') so DB is created in CWD. Pull works correctly but user checked a different empty DB in the project directory."
  artifacts:
    - path: "src/mdc_encyclopedia/cli.py"
      issue: "Line 39: db_path defaults to bare relative filename 'mdc_encyclopedia.db'"
  missing:
    - "Use an absolute default path (e.g., ~/.local/share/mdc-encyclopedia/mdc_encyclopedia.db or click.get_app_dir())"
  debug_session: ".planning/debug/pull-inserts-zero-records.md"
