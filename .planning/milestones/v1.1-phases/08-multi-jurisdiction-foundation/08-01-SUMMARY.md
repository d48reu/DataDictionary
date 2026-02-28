---
phase: 08-multi-jurisdiction-foundation
plan: 01
subsystem: database
tags: [yaml, pyyaml, sqlite, migration, composite-key, registry, multi-jurisdiction]

# Dependency graph
requires:
  - phase: 07-static-site
    provides: "Existing V2 database schema, pyproject.toml build config"
provides:
  - "jurisdictions.yaml config with 3 South Florida jurisdictions"
  - "registry.py loader with fallback chain and get_jurisdiction() helper"
  - "Schema V3 migration with synthetic composite key (jurisdiction_arcgis_id)"
  - "Auto-backup before migration for safety"
  - "get_datasets_by_jurisdiction() query helper"
  - "ai_description column denormalized from enrichments"
affects: [08-02, 09-cross-jurisdiction-search, 11-field-enrichment, 12-ui-polish]

# Tech tracking
tech-stack:
  added: [pyyaml]
  patterns: [registry-driven-config, synthetic-composite-key, create-copy-swap-migration, auto-backup-before-migration]

key-files:
  created:
    - src/mdc_encyclopedia/jurisdictions.yaml
    - src/mdc_encyclopedia/registry.py
  modified:
    - src/mdc_encyclopedia/db.py
    - pyproject.toml

key-decisions:
  - "Used YAML over JSON for jurisdiction config -- supports comments, more human-editable"
  - "Synthetic composite key (jurisdiction_arcgis_id) over composite PRIMARY KEY -- preserves single-column FK pattern"
  - "Path(__file__).parent for config discovery -- consistent with existing template loading in generator.py"

patterns-established:
  - "Registry fallback chain: explicit path > env var > user data dir > package default"
  - "Create-copy-swap migration: create new table, INSERT with transform, update child FKs, drop old, rename new"
  - "Auto-backup before any destructive schema migration"

requirements-completed: [MULTI-01, MULTI-03]

# Metrics
duration: 4min
completed: 2026-02-27
---

# Phase 8 Plan 1: Jurisdiction Registry and Schema V3 Migration Summary

**YAML jurisdiction registry with 3 South Florida portals plus SQLite Schema V3 migration with synthetic composite key, auto-backup, and ai_description denormalization**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-27T04:56:23Z
- **Completed:** 2026-02-27T05:00:47Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Jurisdiction registry loads 3 portals (miami-dade, broward, miami) from YAML config with 4-level fallback chain
- Schema V3 migration safely transforms existing V2 databases: auto-backup, synthetic composite key, FK updates across all 4 child tables, row count verification
- Fresh databases start directly at V3 schema with jurisdiction/arcgis_id/ai_description columns and indexes
- PyYAML added as dependency; jurisdictions.yaml force-included in wheel distribution

## Task Commits

Each task was committed atomically:

1. **Task 1: Create jurisdiction registry config and loader module** - `3a064c4` (feat)
2. **Task 2: Implement Schema V3 migration with synthetic composite key and auto-backup** - `073a51d` (feat)

## Files Created/Modified
- `src/mdc_encyclopedia/jurisdictions.yaml` - YAML config with 3 South Florida jurisdiction entries (slug, display_name, hub_url, portal_type)
- `src/mdc_encyclopedia/registry.py` - Registry loader with load_registry() fallback chain and get_jurisdiction() convenience function
- `src/mdc_encyclopedia/db.py` - Schema V3 migration (_backup_database, _migrate_v2_to_v3), updated init_db() with V3 path, get_datasets_by_jurisdiction() helper, V3 CREATE TABLE for fresh databases
- `pyproject.toml` - Added pyyaml>=6.0 dependency and jurisdictions.yaml force-include

## Decisions Made
- Used YAML over JSON for jurisdiction config because it supports comments and is more human-editable for users adding future jurisdictions
- Used synthetic composite key (jurisdiction_arcgis_id as single TEXT PK) over composite PRIMARY KEY to preserve the existing single-column FK pattern across all child tables
- Used Path(__file__).parent for package default config discovery, consistent with existing template loading in generator.py
- Denormalized ai_description from enrichments into datasets table during migration for faster query access

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Registry and V3 schema are ready for Plan 02 (hub client parameterization, normalizer updates, CLI --jurisdiction flag)
- All existing queries in db.py remain compatible with the V3 schema
- upsert_dataset() will need updating in Plan 02 to handle the new jurisdiction/arcgis_id/ai_description columns

## Self-Check: PASSED

All files and commits verified:
- FOUND: src/mdc_encyclopedia/jurisdictions.yaml
- FOUND: src/mdc_encyclopedia/registry.py
- FOUND: src/mdc_encyclopedia/db.py
- FOUND: pyproject.toml
- FOUND: commit 3a064c4 (Task 1)
- FOUND: commit 073a51d (Task 2)

---
*Phase: 08-multi-jurisdiction-foundation*
*Completed: 2026-02-27*
