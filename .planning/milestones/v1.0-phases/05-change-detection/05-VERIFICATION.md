---
phase: 05-change-detection
verified: 2026-02-25T00:00:00Z
status: passed
score: 7/7 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Run mdc-encyclopedia pull twice against live MDC portals, then run mdc-encyclopedia diff"
    expected: "Second pull prints a cyan one-liner change summary; diff shows Rich-formatted table with green/red/yellow rows grouped by timestamp"
    why_human: "Cannot programmatically verify Rich terminal rendering, live API behavior, and correct portal-sourced change detection in CI"
---

# Phase 5: Change Detection Verification Report

**Phase Goal:** Users can see what changed between catalog pulls -- new datasets, removed datasets, and schema changes
**Verified:** 2026-02-25
**Status:** PASSED
**Re-verification:** No -- initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Running `mdc-encyclopedia diff` after a second pull shows newly added datasets, removed datasets, and schema changes in Rich-formatted output | VERIFIED | `diff` command in cli.py (line 476) renders a Rich `Table` with green/red/yellow color-coded rows per change type, grouping by `detected_at` timestamp batch |
| 2 | Diff results are stored in the SQLite changes table for consumption by the static site export | VERIFIED | `insert_change` writes to `changes` table (schema confirmed: id, dataset_id, change_type, details, detected_at); `get_recent_changes` LEFT JOINs to datasets; integration test verified 3 records stored correctly |
| 3 | Running diff after the first-ever pull produces a clean "no previous state" message (not an error) | VERIFIED | `compute_changes` returns zeros immediately when `pre_ids` is empty (line 64-65 of detector.py); `diff` command prints "No changes recorded yet. Changes are tracked starting from the second pull." when `changes` list is empty |

**Score:** 3/3 success criteria verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/mdc_encyclopedia/diff/__init__.py` | Module init | VERIFIED | Exists, 1 line: `"""Change detection module."""` |
| `src/mdc_encyclopedia/diff/detector.py` | Snapshot capture, comparison logic, change record storage | VERIFIED | Exists, 122 lines (min 60), substantive implementation of `capture_snapshot` and `compute_changes` |
| `src/mdc_encyclopedia/db.py` | get_dataset_ids, get_columns_snapshot, insert_change, get_recent_changes helpers | VERIFIED | All 4 functions present at lines 321, 336, 359, 391. Contain proper SQL queries, type hints, docstrings |
| `src/mdc_encyclopedia/cli.py` | Pull command with diff integration, diff command with Rich display | VERIFIED | `def diff` at line 482; pre-snapshot capture at lines 86-87; Stage 5 Change Detection at lines 218-235 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `diff/detector.py` | `db.py` | `from mdc_encyclopedia.db import get_dataset_ids, get_columns_snapshot, insert_change` | WIRED | Lines 10-14 of detector.py; all three functions called in `capture_snapshot` and `compute_changes` |
| `diff/detector.py` | `changes` table | `insert_change(` calls for each change category | WIRED | Lines 93, 102, 114 of detector.py -- one call per added, removed, and schema-changed record respectively |
| `cli.py` | `diff/detector.py` | `from mdc_encyclopedia.diff.detector import capture_snapshot, compute_changes` | WIRED | Line 37 of cli.py; `capture_snapshot` called at lines 86 and 226; `compute_changes` called at line 227 |
| `cli.py` | `db.py` | `get_recent_changes` imported and called | WIRED | Line 29 of cli.py import block; called at line 487 inside the `diff` command body |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DIFF-01 | 05-01, 05-02 | CLI compares current pull against previous pull state | SATISFIED | `capture_snapshot` before ingestion (pre) and after (post) in pull command; `compute_changes(conn, pre_snapshot, post_snapshot)` performs set-based comparison |
| DIFF-02 | 05-01, 05-02 | Diff identifies newly added datasets | SATISFIED | `added_ids = post_ids - pre_ids` in detector.py line 70; inserted as `change_type="added"` records; shown with `+ Added` label in green in diff command |
| DIFF-03 | 05-01, 05-02 | Diff identifies removed datasets | SATISFIED | `removed_ids = pre_ids - post_ids` in detector.py line 71; title stored defensively in details JSON; shown with `- Removed` label in red in diff command |
| DIFF-04 | 05-01, 05-02 | Diff identifies schema changes (column additions/removals) | SATISFIED | `schema_changes` computed by comparing `pre_cols.get(ds_id, set())` vs `new_cols`; columns_added/columns_removed stored as JSON; shown with `~ Schema` label in yellow with `+N cols / -N cols` summary |
| DIFF-05 | 05-01, 05-02 | Diff results stored in SQLite for site generation | SATISFIED | `changes` table verified to exist with correct schema; `get_recent_changes` LEFT JOINs for site consumption; integration test confirmed 3 records stored with shared timestamp |
| CLI-07 | 05-02 | `diff` command shows changes between pulls | SATISFIED | `@cli.command()` `def diff(ctx, latest, show_all)` at line 476 of cli.py; supports `--latest` (default) and `--all` flags; registers in the CLI entry point |

All 6 requirement IDs declared across both plans are accounted for. No orphaned requirements found for Phase 5 in REQUIREMENTS.md.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `cli.py` | 583, 589 | "Not yet implemented" in `export` and `serve` commands | INFO | Out of Phase 5 scope -- these are Phase 6 stubs. Not a Phase 5 concern. |

No anti-patterns found in Phase 5 artifacts (`diff/detector.py`, `diff/__init__.py`, or Phase 5 additions to `db.py` and `cli.py`).

---

### Functional Verification Results

All automated tests executed and passed:

1. **Import checks** -- All 4 DB helpers, detector module, and both CLI commands (`pull`, `diff`) import successfully
2. **Empty DB smoke test** -- `capture_snapshot` returns `{dataset_ids: set(), columns_by_dataset: {}}` on empty DB; `compute_changes` with identical empty snapshots returns zeros; `get_recent_changes` returns empty list
3. **First-pull edge case** -- When `pre_ids` is empty, `compute_changes` returns zeros immediately without inserting any records into the changes table
4. **Full change detection integration** -- Simulated second pull: detected 1 added (ds3), 1 removed (ds2), 1 schema-changed (ds1 col_a -> col_b); all 3 records stored with correct `change_type` values
5. **Removed dataset title preservation** -- `details` JSON for removed records contains `{"title": "Dataset Two"}` as defensive measure
6. **Shared timestamp** -- All 3 change records from a single `compute_changes` call share exactly the same `detected_at` string
7. **SQLite schema** -- `changes` table exists with columns: id, dataset_id, change_type, details, detected_at

---

### Human Verification Required

#### 1. End-to-End Rich Output with Live Data

**Test:** Install the package (`pip install -e .`), run `mdc-encyclopedia pull`, run it again, then run `mdc-encyclopedia diff`
**Expected:** Pull 1 prints "First pull -- N datasets cataloged. Future pulls will show changes." Pull 2 prints either the cyan change summary or "No changes detected since last pull." `mdc-encyclopedia diff` shows a Rich table with color-coded rows (green for added, red for removed, yellow for schema).
**Why human:** Rich terminal rendering requires visual inspection; live MDC API behavior determines whether real changes are present.

#### 2. `diff --all` Flag with Multiple Pull Batches

**Test:** Run three pulls against the live portal, then `mdc-encyclopedia diff --all`
**Expected:** Multiple batched change tables displayed, each titled with their `detected_at` timestamp, plus a dim hint showing total batch count
**Why human:** Requires multiple live pull cycles to accumulate multiple batches; grouping behavior needs visual confirmation.

---

### Gaps Summary

No gaps found. All automated checks passed across all three verification levels:
- Level 1 (Exists): All artifacts present at expected paths
- Level 2 (Substantive): No stubs -- all functions contain real SQL queries, set operations, and Rich rendering logic
- Level 3 (Wired): All key links verified -- detector imports from db, cli imports from detector, changes table wired through the full chain

Phase 5 goal is achieved: users can see what changed between catalog pulls.

---

_Verified: 2026-02-25_
_Verifier: Claude (gsd-verifier)_
