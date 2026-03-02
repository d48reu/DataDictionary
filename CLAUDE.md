# DataDictionary (mdc-encyclopedia)

CLI tool + static encyclopedia cataloging every dataset from South Florida's ArcGIS Open Data Hubs with AI-powered enrichment.

**Repo:** https://github.com/d48reu/DataDictionary.git
**Live:** https://d48reu.github.io/DataDictionary (GitHub Pages)
**Status:** v1.1 shipped 2026-02-28, v1.2 in planning

## Architecture

Python CLI (`mdc-encyclopedia`) that:
1. Pulls dataset metadata from 3 ArcGIS Hubs (Miami-Dade, Broward, City of Miami)
2. Enriches with Claude AI (descriptions, use cases, keywords, civic relevance)
3. Audits quality (freshness, completeness, documentation → letter grades A-F)
4. Exports searchable static HTML site with Lunr.js search

## Tech Stack

**Backend:** Python 3.12+, Click + rich-click, httpx (rate-limited 1 req/sec), Anthropic SDK, Jinja2, feedgen (Atom), SQLite
**Frontend:** Vanilla HTML/CSS/JS, Lunr.js client-side search
**CI/CD:** GitHub Actions (weekly cron + manual dispatch) → GitHub Pages
**Package:** pyproject.toml with hatchling build system

## Key Commands

```bash
pip install .                           # Install package
mdc-encyclopedia pull                   # Fetch catalogs from ArcGIS Hubs
mdc-encyclopedia enrich --dry-run       # AI enrichment (cost estimate first)
mdc-encyclopedia enrich-fields          # AI column descriptions
mdc-encyclopedia audit                  # Quality audit (letter grades A-F)
mdc-encyclopedia diff --latest          # Detect changes since last pull
mdc-encyclopedia export -o site --base-url /DataDictionary  # Generate static site
mdc-encyclopedia serve                  # Local dev server
mdc-encyclopedia stats                  # Catalog statistics
```

## Environment Variables

**Required for enrichment:**
- `ANTHROPIC_API_KEY` — Claude API key

**Optional:**
- `MDC_ENCYCLOPEDIA_DB` — Database path (default: `./mdc_encyclopedia.db`)

## Database

SQLite (schema V4), committed to repo for CI persistence. Tables: `datasets` (composite key: jurisdiction + arcgis_id), `columns`, `enrichments`, `audit_scores`, `changes`. Versioned via PRAGMA user_version with automatic backup on upgrade.

## CI/CD Pipeline

GitHub Actions workflow (`.github/workflows/encyclopedia.yml`):
- Weekly Monday 6:00 UTC: pull → audit → diff → export → deploy
- Manual dispatch: optional AI enrichment with 25-dataset cost threshold
- Commits database back to repo with `[skip ci]`

## Cost Controls

- 25-dataset enrichment threshold (creates GitHub issue if exceeded)
- Dry-run cost estimates before any API spend
- Haiku model in CI (cost-optimized)
- Batched API calls (~30 columns per request)

## Planning Docs

See `.planning/` for PROJECT.md, STATE.md, ROADMAP.md, MILESTONES.md. See `v1.2-gsd-prompt.md` for next milestone spec.
