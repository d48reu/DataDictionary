# Phase 1: Foundation - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Installable Python package skeleton with CLI entry point (`mdc-encyclopedia`), complete SQLite schema for all downstream phases, and Rich-formatted terminal output. This is the base that all other phases build on. No data ingestion, no enrichment, no site generation.

</domain>

<decisions>
## Implementation Decisions

### Database location & config
- Default location: current working directory as `mdc_encyclopedia.db`
- Override via `MDC_ENCYCLOPEDIA_DB` environment variable (no CLI flag)
- On first run, print one-line Rich message: "Created database: mdc_encyclopedia.db" (green checkmark, non-intrusive)
- No XDG paths, no data subdirectory — keep it visible and simple

### Package structure
- src/ layout: `src/mdc_encyclopedia/`
- Feature modules (flat, one per concern): cli.py, db.py, and future modules created when their phase starts
- All subcommands registered in Phase 1 as stubs printing "not yet implemented": pull, enrich, audit, diff, export, serve, stats
- CLI framework: Click (with rich-click for Rich-formatted help output)
- Build backend: Hatchling with pyproject.toml
- Entry point: `mdc-encyclopedia` console script

### Schema flexibility
- Hybrid approach: core columns + JSON extras (`metadata_json` TEXT column)
- Broad column set for datasets table: id, source_portal, source_url, title, description, category, publisher, format, created_at, updated_at, row_count, tags, license, api_endpoint, bbox/geometry, download_url
- Columns table: dataset_id (FK), name, data_type, description
- Enrichments table: one row per dataset (latest only) — dataset_id (FK), description, use_cases, keywords, department, update_freq, civic_relevance, prompt_version, enriched_at
- Audit_scores table: dataset_id (FK), composite_score, staleness, completeness, documentation, audited_at
- Changes table: dataset_id, change_type, details, detected_at
- Schema version tracking: a schema_version table to track current version, with ALTER TABLE upgrades on startup as needed (no Alembic)

### Claude's Discretion
- Exact Rich formatting and colors for help output
- Click group/command decorator patterns
- Schema version upgrade implementation details
- Test structure and fixtures
- .gitignore contents

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-02-24*
