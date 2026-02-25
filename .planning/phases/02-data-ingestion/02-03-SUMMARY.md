---
phase: 02-data-ingestion
plan: 03
subsystem: database
tags: [sqlite, xdg, cli, path-resolution, bug-fix]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: SQLite schema and init_db function
  - phase: 02-data-ingestion
    provides: CLI pull command and hub client (plans 01-02)
provides:
  - Absolute XDG-compliant default database path via get_default_db_path()
  - Automatic parent directory creation in init_db
  - Deterministic DB location regardless of CWD
affects: [03-enrichment, 04-audit, 05-diff, 06-site-gen, UAT]

# Tech tracking
tech-stack:
  added: []
  patterns: [XDG Base Directory Specification for data storage]

key-files:
  created: []
  modified:
    - src/mdc_encyclopedia/cli.py
    - src/mdc_encyclopedia/db.py

key-decisions:
  - "Used os.path.expanduser + os.path.join for XDG path instead of platformdirs dependency"
  - "Default DB at ~/.local/share/mdc-encyclopedia/mdc_encyclopedia.db follows XDG Base Directory Spec"
  - "Parent dir guard uses if parent: to avoid empty-string makedirs for bare filenames"

patterns-established:
  - "XDG data path: ~/.local/share/mdc-encyclopedia/ for all persistent user data"
  - "init_db always creates parent directories before sqlite3.connect"

requirements-completed: [INGEST-04]

# Metrics
duration: 2min
completed: 2026-02-25
---

# Phase 2 Plan 3: Fix DB Path Summary

**Absolute XDG-compliant default database path replacing relative CWD-dependent path, fixing UAT test 2 blocker**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-25T04:08:47Z
- **Completed:** 2026-02-25T04:10:18Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `get_default_db_path()` returning `~/.local/share/mdc-encyclopedia/mdc_encyclopedia.db`
- Replaced bare `"mdc_encyclopedia.db"` default with absolute XDG path in CLI
- Added automatic parent directory creation (`os.makedirs`) in `init_db` before `sqlite3.connect`
- Cleaned up stale DB files from project root and home directory
- Verified env var override (`MDC_ENCYCLOPEDIA_DB`) still takes precedence

## Task Commits

Each task was committed atomically:

1. **Task 1: Add get_default_db_path helper and fix default path in CLI and DB** - `ac0def1` (fix)
2. **Task 2: Verify end-to-end DB path resolution and cleanup stale DB files** - No tracked file changes (verification-only task; stale .db files in .gitignore)

## Files Created/Modified
- `src/mdc_encyclopedia/cli.py` - Added `get_default_db_path()` function; updated default db_path to use it; improved "Created database" message to show absolute path
- `src/mdc_encyclopedia/db.py` - Added `os.makedirs(parent, exist_ok=True)` in `init_db` before `sqlite3.connect`

## Decisions Made
- Used `os.path.expanduser("~")` + `os.path.join` for XDG path instead of adding platformdirs dependency -- zero new dependencies
- Default path `~/.local/share/mdc-encyclopedia/mdc_encyclopedia.db` follows XDG Base Directory Specification for Linux
- `if parent:` guard on makedirs ensures bare filenames (from explicit env var override) don't cause errors

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- UAT test 2 root cause eliminated -- all 4 blocked UAT tests should now pass on re-run
- Database location is deterministic regardless of working directory
- Ready for `mdc-encyclopedia pull` to populate the XDG-path database for enrichment phase

## Self-Check: PASSED

- FOUND: src/mdc_encyclopedia/cli.py
- FOUND: src/mdc_encyclopedia/db.py
- FOUND: 02-03-SUMMARY.md
- FOUND: ac0def1 (Task 1 commit)

---
*Phase: 02-data-ingestion*
*Completed: 2026-02-25*
