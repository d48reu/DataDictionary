# Roadmap: Miami-Dade County Open Data Encyclopedia

## Overview

This roadmap delivers a pipeline-of-commands CLI tool that ingests metadata from two Miami-Dade open data portals, enriches it with AI-generated plain-English descriptions, audits data quality, detects changes between pulls, and exports a fully static searchable website deployed to GitHub Pages. The dependency chain is strict: storage schema before API clients, real data before enrichment, all upstream outputs before site export, and working commands before CI automation. Each phase delivers a testable, independent capability.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Python package skeleton with SQLite schema, CLI entry point, and Rich output
- [x] **Phase 2: Data Ingestion** - Pull full catalog metadata from Socrata and ArcGIS Hub into SQLite
- [x] **Phase 3: AI Enrichment** - Claude-powered plain-English descriptions, use cases, keywords, and civic relevance for every dataset
- [x] **Phase 4: Quality Audit** - Staleness detection, completeness scoring, and quality grades for every dataset
- [ ] **Phase 5: Change Detection** - Diff between pulls identifying new, removed, and schema-changed datasets
- [ ] **Phase 6: Static Site** - Searchable, browsable HTML encyclopedia with dataset pages, quality reports, and change history
- [ ] **Phase 7: Deployment** - GitHub Actions weekly refresh and GitHub Pages hosting

## Phase Details

### Phase 1: Foundation
**Goal**: A working installable Python package with the complete SQLite schema that all downstream phases build on
**Depends on**: Nothing (first phase)
**Requirements**: CLI-01, CLI-02, CLI-10, INGEST-04
**Success Criteria** (what must be TRUE):
  1. Running `pip install .` in the project directory installs the package and makes `mdc-encyclopedia` available as a command
  2. Running `mdc-encyclopedia` prints a help message listing available subcommands with Rich-formatted output
  3. Running `mdc-encyclopedia` for the first time creates a SQLite database file with the correct table schema (datasets, columns, enrichments, audit_scores, changes)
  4. The database schema includes a separate enrichments table that will not be overwritten by future metadata pulls
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md — Package skeleton with Hatchling config and SQLite database module
- [ ] 01-02-PLAN.md — CLI entry point with Rich-formatted stub commands and install verification

### Phase 2: Data Ingestion
**Goal**: Users can pull the complete Miami-Dade open data catalog from both portals into the local database with a single command
**Depends on**: Phase 1
**Requirements**: INGEST-01, INGEST-02, INGEST-03, INGEST-05, INGEST-06, CLI-03
**Success Criteria** (what must be TRUE):
  1. Running `mdc-encyclopedia pull` fetches all datasets from Socrata Discovery API (paginating correctly) and ArcGIS Hub API, displaying a Rich progress bar
  2. After pull completes, the SQLite database contains dataset records from both portals with normalized metadata fields
  3. Column/field metadata is stored for Socrata datasets (fetched via per-dataset Views API calls)
  4. Datasets appearing on both portals are detected and deduplicated (single record with both source links)
  5. All API calls are rate-limited to 1 request/second (observable via progress bar timing)
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — Hub API client, normalizer, and database upserts (ingestion foundation)
- [x] 02-02-PLAN.md — Field metadata fetcher and CLI pull command with Rich progress/summary
- [x] 02-03-PLAN.md — Gap closure: fix relative DB path causing 0-record UAT failure

### Phase 3: AI Enrichment
**Goal**: Every dataset in the catalog has AI-generated plain-English descriptions, use cases, keywords, department attribution, and civic relevance that make it understandable by a non-technical resident
**Depends on**: Phase 2
**Requirements**: ENRICH-01, ENRICH-02, ENRICH-03, ENRICH-04, ENRICH-05, ENRICH-06, ENRICH-07, ENRICH-08, ENRICH-09, ENRICH-10, CLI-05
**Success Criteria** (what must be TRUE):
  1. Running `mdc-encyclopedia enrich --dry-run` lists datasets that would be enriched and shows a cost estimate, without calling the Anthropic API
  2. Running `mdc-encyclopedia enrich` prompts with a cost estimate and, after confirmation, generates plain-English description, use cases, keywords, owning department, update frequency, and civic relevance score for each unenriched dataset
  3. Enrichment can be interrupted and resumed with `--resume` (picks up where it left off, does not re-enrich already-enriched datasets)
  4. Enrichment results are stored in a separate SQLite table that survives metadata re-pulls, with prompt version tracking
**Plans**: 2 plans

Plans:
- [x] 03-01-PLAN.md — Enrichment core module: Pydantic model, prompt templates, Anthropic client wrapper, DB helpers
- [x] 03-02-PLAN.md — CLI enrich command with --dry-run, --resume, --model, cost estimation, and Rich progress

### Phase 4: Quality Audit
**Goal**: Every dataset has a quality score based on staleness, completeness, and documentation that enables residents to judge data reliability
**Depends on**: Phase 2
**Requirements**: AUDIT-01, AUDIT-02, AUDIT-03, AUDIT-04, AUDIT-05, CLI-04, CLI-06
**Success Criteria** (what must be TRUE):
  1. Running `mdc-encyclopedia audit` analyzes all datasets and writes quality scores to the audit_scores table
  2. Running `mdc-encyclopedia stats` displays a Rich-formatted summary: dataset count per portal, enrichment status counts, and quality score distribution
  3. Stale datasets (last updated exceeds expected frequency), empty datasets, and poorly described datasets are each flagged with specific audit findings
  4. Each dataset receives a composite quality score reflecting metadata completeness, freshness, and column documentation coverage
**Plans**: 2 plans

Plans:
- [x] 04-01-PLAN.md — Schema V2 migration and three-dimension scoring engine (audit/scorer.py, db.py)
- [x] 04-02-PLAN.md — CLI audit and stats commands with Rich output (cli.py)

### Phase 5: Change Detection
**Goal**: Users can see what changed between catalog pulls -- new datasets, removed datasets, and schema changes
**Depends on**: Phase 2
**Requirements**: DIFF-01, DIFF-02, DIFF-03, DIFF-04, DIFF-05, CLI-07
**Success Criteria** (what must be TRUE):
  1. Running `mdc-encyclopedia diff` after a second pull shows newly added datasets, removed datasets, and schema changes (column additions/removals) in Rich-formatted output
  2. Diff results are stored in the SQLite changes table for consumption by the static site export
  3. Running diff after the first-ever pull produces a clean "no previous state" message (not an error)
**Plans**: 2 plans

Plans:
- [x] 05-01-PLAN.md — Diff detection engine: snapshot capture, set-based comparison, and change record storage
- [ ] 05-02-PLAN.md — CLI integration: pull command diff tracking and diff display command

### Phase 6: Static Site
**Goal**: A fully static, searchable HTML encyclopedia where residents can browse, search, and understand every Miami-Dade dataset
**Depends on**: Phase 3, Phase 4, Phase 5
**Requirements**: SITE-01, SITE-02, SITE-03, SITE-04, SITE-05, SITE-06, SITE-07, SITE-08, SITE-09, SITE-10, SITE-11, SITE-12, SITE-13, CLI-08, CLI-09
**Success Criteria** (what must be TRUE):
  1. Running `mdc-encyclopedia export` generates a complete static site in the site/ directory with no server-side dependencies
  2. Running `mdc-encyclopedia serve` starts a local preview server where the full site is browsable
  3. The site homepage has a working search bar (Lunr.js/Fuse.js) that finds datasets by title, AI keywords, department, and category
  4. Category browse pages list datasets with filtering by format, publisher, and tag, plus freshness indicators
  5. Individual dataset pages display metadata, AI-generated enrichment (description, use cases, keywords, civic relevance), column info, quality score, related datasets, and a link to the source portal
  6. A "What Changed" page shows diff results from the most recent pull comparison
  7. A data quality report page shows aggregate stats (percent described, stale count, quality distribution)
  8. Every page has the MDC branding (#003366, white, amber), responsive mobile layout, disclaimer footer, and works as a pure static file
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD
- [ ] 06-03: TBD

### Phase 7: Deployment
**Goal**: The encyclopedia auto-refreshes weekly and is publicly accessible on GitHub Pages without manual intervention
**Depends on**: Phase 6
**Requirements**: DEPLOY-01, DEPLOY-02, DEPLOY-03
**Success Criteria** (what must be TRUE):
  1. The static site deploys to GitHub Pages and is accessible at the project's GitHub Pages URL
  2. A GitHub Actions workflow runs weekly on a cron schedule, executing: pull, audit, diff, optional enrich (if ANTHROPIC_API_KEY secret is set), export, and deploy
  3. The workflow completes successfully even without ANTHROPIC_API_KEY (skipping enrichment gracefully)
**Plans**: TBD

Plans:
- [ ] 07-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7
Note: Phases 3, 4, and 5 can proceed in parallel after Phase 2 but are sequenced for solo execution.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 2/2 | Complete | 2026-02-25 |
| 2. Data Ingestion | 3/3 | Complete | 2026-02-25 |
| 3. AI Enrichment | 2/2 | Complete | 2026-02-25 |
| 4. Quality Audit | 2/2 | Complete | 2026-02-26 |
| 5. Change Detection | 1/2 | In Progress | - |
| 6. Static Site | 0/TBD | Not started | - |
| 7. Deployment | 0/TBD | Not started | - |
