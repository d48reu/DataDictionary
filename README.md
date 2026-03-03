# MDC Encyclopedia (DataDictionary)

Searchable encyclopedia cataloging every dataset from South Florida's ArcGIS Open Data Hubs with AI-powered enrichment and quality auditing.

**Live:** [d48reu.github.io/DataDictionary](https://d48reu.github.io/DataDictionary)

## What It Does

- Pulls dataset metadata from 3 ArcGIS Hubs (Miami-Dade, Broward, City of Miami)
- Enriches with Claude AI (descriptions, use cases, keywords, civic relevance)
- Audits data quality (freshness, completeness, documentation — letter grades A-F)
- Generates a searchable static HTML site with Lunr.js client-side search
- Weekly automated refresh via GitHub Actions CI/CD

## Tech Stack

- **Backend:** Python 3.12+, Click CLI, httpx, Anthropic SDK, Jinja2
- **Frontend:** Vanilla HTML/CSS/JS, Lunr.js search
- **Database:** SQLite
- **CI/CD:** GitHub Actions → GitHub Pages

## Quick Start

```bash
pip install .
mdc-encyclopedia pull        # Fetch catalogs
mdc-encyclopedia audit       # Quality audit
mdc-encyclopedia export -o site --base-url /DataDictionary
mdc-encyclopedia serve       # Local dev server
```

## Environment Variables

- `ANTHROPIC_API_KEY` — Required for AI enrichment

## License

All rights reserved. Abreu Data Works LLC.
