# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** Every Miami-Dade open dataset is discoverable and understandable by a non-technical resident.
**Current focus:** Phase 6: Static Site (In Progress)

## Current Position

Phase: 6 of 7 (Static Site)
Plan: 2 of 4 in current phase
Status: In Progress
Last activity: 2026-02-26 -- Completed 06-02-PLAN.md (homepage & search)

Progress: [█████████░] 87%

## Performance Metrics

**Velocity:**
- Total plans completed: 13
- Average duration: 2.6min
- Total execution time: 0.57 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Foundation | 2 | 4min | 2min |
| 2. Data Ingestion | 3 | 8min | 2.7min |
| 3. AI Enrichment | 2 | 5min | 2.5min |
| 4. Quality Audit | 2 | 5min | 2.5min |
| 5. Change Detection | 2 | 4min | 2min |
| 6. Static Site | 2 | 8min | 4min |

**Recent Trend:**
- Last 5 plans: 05-01 (2min), 05-02 (2min), 06-01 (4min), 06-02 (4min)
- Trend: Consistent

*Updated after each plan completion*
| Phase 02 P01 | 3min | 2 tasks | 5 files |
| Phase 02 P02 | 3min | 2 tasks | 2 files |
| Phase 02 P03 | 2min | 2 tasks | 2 files |
| Phase 03 P01 | 3min | 2 tasks | 6 files |
| Phase 03 P02 | 2min | 1 tasks | 1 files |
| Phase 04 P01 | 3min | 2 tasks | 3 files |
| Phase 04 P02 | 2min | 2 tasks | 1 files |
| Phase 05 P01 | 2min | 2 tasks | 3 files |
| Phase 05 P02 | 2min | 2 tasks | 1 files |
| Phase 06 P01 | 4min | 2 tasks | 14 files |
| Phase 06 P02 | 4min | 2 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 7-phase pipeline architecture following strict dependency chain (storage -> ingestion -> enrichment/audit/diff -> site -> deploy)
- [Roadmap]: Phases 3, 4, 5 all depend on Phase 2 but are sequenced linearly for solo developer execution
- [01-01]: Used PRAGMA user_version for schema versioning instead of a schema_version table
- [01-01]: Added json_valid CHECK fallback for Python builds without JSON1 extension
- [01-02]: Used rich_click as drop-in replacement for click for automatic Rich formatting
- [01-02]: Database path configurable via MDC_ENCYCLOPEDIA_DB env var, defaulting to mdc_encyclopedia.db
- [02-01]: Used synchronous httpx (not async) since rate limiting at 1 req/s makes async pointless
- [02-01]: Within-catalog dedup uses normalized title exact match per locked decision (no fuzzy matching)
- [02-01]: Download URL constructed for Feature Services only; None for File Geodatabases
- [02-01]: Rate limiting via time.sleep before each request ensures compliance regardless of retry state
- [02-02]: Single ArcGIS Hub progress stage (no Socrata) since research confirmed no Socrata portal exists for Miami-Dade
- [02-02]: Field fetch errors return empty list instead of raising -- individual dataset failures never crash the pull
- [02-02]: Dedup panel shown by default with summary counts; --verbose shows per-pair detail
- [02-03]: Used os.path.expanduser + os.path.join for XDG path instead of platformdirs dependency
- [02-03]: Default DB at ~/.local/share/mdc-encyclopedia/mdc_encyclopedia.db follows XDG Base Directory Spec
- [02-03]: Parent dir guard uses if parent: to avoid empty-string makedirs for bare filenames
- [03-01]: Column metadata in prompts truncated at 30 entries for prompt size control
- [03-01]: Tags field handled as both JSON array and plain string for robustness
- [03-01]: 0.1s delay between count_tokens calls to avoid rate limiting
- [03-02]: Resume flag is UX-only -- query always returns unenriched datasets via LEFT JOIN
- [03-02]: Cost confirmation auto-proceeds under $5, prompts above $5 threshold
- [03-02]: API key validated before column lookup to fail fast on missing credentials
- [03-02]: 1-second delay between enrichment API calls matching project rate limiting pattern
- [04-01]: FREQUENCY_DAYS uses generous grace periods (weekly=14d, monthly=45d, annually=400d) for government data
- [04-01]: Static/one-time datasets score 1.0 but scored=False for N/A weight redistribution
- [04-01]: Completeness gives 0.3 partial credit for unavailable row_count (not as bad as 0 rows)
- [04-01]: normalize_frequency uses substring fallback for free-text variants from Claude enrichment
- [04-02]: Grade distribution queried from DB after all upserts for consistency (not accumulated in memory)
- [04-02]: Stats command sections are conditional: quality distribution and top findings only shown when audit data exists
- [04-02]: Top findings aggregated from findings_json across all audit_scores using Counter.most_common(5)
- [05-01]: Shared detected_at timestamp generated once per compute_changes call ensures batch grouping
- [05-01]: Removed dataset title stored in details JSON as defensive measure against future cleanup
- [05-01]: First-pull returns zeros immediately without inserting records (caller handles messaging)
- [05-01]: insert_change does NOT commit; compute_changes commits once after all batch inserts
- [05-02]: defaultdict import moved to top-level alongside existing Counter from collections
- [05-02]: Default diff is --latest (most recent pull only) for day-to-day usability
- [05-02]: Removed dataset title resolved from details JSON first, then LEFT JOIN, then dataset_id fallback
- [05-02]: Hint about --all shown only when more batches exist beyond the displayed one
- [06-01]: Used python-slugify for URL slug generation with collision detection via dataset ID suffix
- [06-01]: Pure CSS hamburger menu (checkbox hack) to avoid JavaScript dependency for navigation
- [06-01]: Related datasets scored by category match (3 pts) plus shared keywords (1 pt each)
- [06-01]: Added force-include in pyproject.toml to ensure templates and static files ship in wheel
- [06-02]: Lunr.js CDN (jsdelivr v2.3.9) loaded globally; field boosts title(10) > keywords(8) > description(5) > dept/cat(3)
- [06-02]: Wildcard suffix on search queries for as-you-type; try-catch fallback for Lunr syntax errors
- [06-02]: Homepage category grid caps at 15 categories; recently updated section conditionally rendered

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 2]: Socrata SODA3 migration status for Miami-Dade is uncertain -- need live API discovery spike before writing client code
- [Phase 2]: ArcGIS Hub API v3 docs are from a 2019 unofficial gist -- validate response shape with live requests
- [Phase 3]: Enrichment prompt structure needs iteration on 15-20 real datasets before full-catalog run
- [Phase 6]: Lunr.js search index size needs measurement after first full export -- target under 500KB

## Session Continuity

Last session: 2026-02-26
Stopped at: Completed 06-02-PLAN.md (homepage & search)
Resume file: None
