# Feature Research

**Domain:** Open data catalog / encyclopedia for government open data portals
**Researched:** 2026-02-24
**Confidence:** MEDIUM-HIGH (based on analysis of CKAN, Socrata, Magda, OpenDataSoft, PortalJS, data.gov, data.gov.au, OpenDataPhilly, and academic research on open data portal usability)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Full-text search** | Every data catalog has search as its primary discovery mechanism. Magda, CKAN, Socrata, and data.gov all lead with a search bar. Users will not manually browse hundreds of datasets. | MEDIUM | CLIENT-SIDE: Lunr.js or Fuse.js built at export time. Pre-built JSON index. Complexity is in tuning relevance, not infrastructure. |
| **Browse by category/theme** | Standard in every portal (CKAN groups/organizations, Socrata categories, OpenDataSoft themes). Users expect to narrow by topic like "Transportation" or "Public Safety." | LOW | Derive from metadata or AI enrichment. Static category pages generated at build time. |
| **Individual dataset detail pages** | Every portal has a dedicated page per dataset showing title, description, publisher, format, license, update frequency, and a link to the source. This is the atomic unit of a data catalog. | MEDIUM | Template-driven. The quality of these pages is where the product lives or dies. Must include all metadata + enrichment + quality score. |
| **Dataset metadata display** | Users expect to see: title, description, publisher/owner, license, format(s), last updated date, temporal coverage, tags/keywords. Missing metadata = "is this data even real?" | LOW | Pulled directly from Socrata Discovery API and ArcGIS Hub API. Display what's available, flag what's missing. |
| **Source portal deep links** | Users must be able to click through to the actual data on the original portal (Socrata/ArcGIS). This is a catalog, not a data host. Broken or missing links destroy trust. | LOW | Store and display canonical URLs from API responses. |
| **Column/field information** | CKAN and Socrata both surface column names and types. Users (especially developers and journalists) need to know what fields exist before deciding to use a dataset. | LOW-MEDIUM | Socrata requires per-dataset API call to `/api/views/{id}.json` for column metadata. ArcGIS field info available via layer definitions. |
| **Responsive/mobile-friendly layout** | Static sites on GitHub Pages must work on phones. Researchers, journalists, and residents all browse on mobile. Non-responsive = instant bounce. | LOW | Standard responsive CSS. No framework needed — vanilla HTML/CSS handles this. |
| **Filtering by format/publisher/tag** | Every major portal (CKAN facets, Socrata filters, OpenDataSoft facets) allows narrowing results. Without filters, search alone is insufficient for large catalogs. | MEDIUM | Client-side filtering on static site. Can use URL parameters + JS to filter pre-rendered index. |
| **Last updated / freshness indicator** | Users need to know if data is current. Stale data without warning erodes trust. Both Socrata and CKAN surface update timestamps prominently. | LOW | Display `metadata_updated_at` from API. Compare against declared update frequency for staleness flag. |
| **"About" / methodology page** | Users need to understand what this tool is, where data comes from, and that it's not an official county product. Transparency is non-negotiable for civic tech. | LOW | Static page. Disclaimer required per PROJECT.md. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **AI-generated plain-English descriptions** | Most open data portals have cryptic, jargon-filled, or outright missing descriptions. Claude-generated summaries in plain language is the #1 differentiator. No existing portal does this well. OpenDataSoft has processors but not LLM-powered narrative descriptions. Magda has metadata enrichment but not plain-English rewriting. | MEDIUM | Requires Anthropic API. Cost-controlled via `--dry-run` and `--resume`. One-time per dataset unless re-run. Core value prop of the project. |
| **AI-generated use cases ("Why you'd care")** | Telling a resident or journalist *why* a dataset matters — not just what it contains. "This dataset could help you find out which neighborhoods have the most code violations." No existing portal does this. | MEDIUM | Bundled with the enrichment prompt. Minimal marginal cost above descriptions. Transforms catalog from reference tool to actionable guide. |
| **Automated data quality scoring** | Toronto's Open Data portal pioneered a public quality score. Most portals lack this. A computed score (metadata completeness, freshness, column documentation) makes the catalog a quality accountability tool. | MEDIUM | Composite score from: % metadata fields filled, days since last update vs declared frequency, column count, description length. Algorithm is simple; the value is in surfacing it. |
| **"What Changed" diff page** | No consumer-facing open data portal surfaces a changelog of catalog-level changes (new datasets added, datasets removed, schema changes). This turns a static catalog into a living accountability tool. | MEDIUM | Requires storing previous pull state and diffing. SQLite makes this straightforward. Weekly cadence from GitHub Actions. |
| **Related datasets** | CKAN has basic "related items" but it's manually curated. AI-inferred relationships ("If you're looking at Building Permits, you might also want Code Violations") add discovery value. | MEDIUM | Can be tag/category based (simple) or AI-inferred (richer). Start with tag overlap, upgrade to AI later. |
| **Civic relevance scoring** | Beyond data quality — how relevant is this dataset to residents? A dataset about internal IT asset inventory scores low; a dataset about transit routes scores high. No portal does this. | LOW-MEDIUM | AI-generated during enrichment. Simple HIGH/MEDIUM/LOW classification. Enables "Most Relevant to Residents" browsing. |
| **Cross-portal unified view** | Miami-Dade has TWO portals (Socrata + ArcGIS Hub). No existing tool unifies them into a single searchable catalog. Residents shouldn't need to know which portal hosts what. | MEDIUM | Core architecture decision. SQLite normalizes both sources. Deduplication needed for datasets that appear on both. |
| **Department attribution** | Many datasets lack clear owning department. AI-inferred department ("Likely: Department of Transportation and Public Works") makes the catalog navigable by government structure. | LOW | AI-generated during enrichment. Enables "Browse by Department" which no Miami-Dade portal currently offers. |
| **Data quality report page** | An aggregate view: "X% of datasets have descriptions. Y datasets haven't been updated in over a year. Z datasets have zero documented columns." Accountability dashboard for the portal itself. | MEDIUM | Computed from audit results. Static HTML page with aggregate stats. Unique among civic tools. |
| **Search keyword enrichment** | AI generates "keywords a resident would search for" — mapping government jargon to plain language. "Right of Way Permits" gets keywords like "sidewalk construction, road work, utility dig." | LOW | Part of enrichment prompt. Feeds into search index for dramatically better recall on non-technical queries. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Data preview (showing actual rows)** | "Let me see the data before I download it." Socrata and CKAN both have this. | Requires per-dataset API calls at build time (hundreds/thousands of extra requests). Dramatically increases build time, storage, and rate-limit risk. Breaks the "catalog, not warehouse" boundary. Data previews go stale faster than metadata. | Deep link to source portal where preview already exists. Dataset page says "View data on [Socrata/ArcGIS]" with a prominent button. |
| **Built-in data visualization (charts/maps)** | "Show me a chart of this data." OpenDataSoft and Socrata embed viz tools. | Massive scope expansion. Requires understanding each dataset's schema to render appropriate visualizations. Maintenance nightmare as schemas change. Static site can't run dynamic viz well. | Link to source portal's visualization tools. Mention in "Use Cases" what kind of analysis is possible. |
| **User accounts / saved searches** | "Let me bookmark datasets and get alerts." | Requires authentication infrastructure, database for user state, session management — all antithetical to a static site on GitHub Pages. Adds GDPR/privacy concerns. | Browser bookmarks work. "What Changed" page serves the alerting use case for the most important changes. |
| **API for programmatic access** | "Let me query the catalog via API." | Building and hosting an API means running a server, which conflicts with the static-site-on-GitHub-Pages architecture. Ongoing maintenance burden. | Export the full catalog as downloadable JSON. Developers can consume the static JSON file directly. The SQLite database is also available for download. |
| **User-submitted dataset requests** | "I want to request a dataset the county should publish." | Requires moderation, backend for submissions, and creates expectations that requests will be fulfilled — which this project has no authority to do. | Link to the county's official feedback channels. Static page explaining how to request data from Miami-Dade directly. |
| **Real-time data freshness checking** | "Check if dataset is currently up on the portal." | Requires runtime API calls from the browser, which means CORS issues, rate limiting from the user's browser, and a fundamentally different architecture. | Weekly pull captures freshness. Staleness flags based on declared update frequency vs actual last update. Good enough for a catalog. |
| **Notifications (email/Slack)** | "Alert me when a dataset changes." | Requires email/notification infrastructure, user accounts, and ongoing compute. Way beyond static site scope. | "What Changed" page serves as a manual check. RSS feed of changes is a v2 low-lift alternative. |
| **Multi-jurisdiction support** | "Add Broward County, City of Miami, etc." | Scope creep. Each jurisdiction has different APIs, metadata schemas, and quality levels. Generalizing before nailing one jurisdiction creates a mediocre product for everyone. | Build for Miami-Dade only. Architecture should be extensible (config-driven portal list) but don't build multi-tenant now. |
| **Comment/discussion on datasets** | "Let users discuss datasets." | Requires moderation, backend, user accounts. Creates liability. Comments go stale and become noise. | Link to relevant civic tech community channels (Code for Miami, etc.) for discussion. |

## Feature Dependencies

```
[Metadata Pull (Socrata + ArcGIS)]
    ├──requires──> [SQLite Storage Schema]
    │                  └──enables──> [AI Enrichment]
    │                  │                 ├──enables──> [Plain-English Descriptions]
    │                  │                 ├──enables──> [Use Cases]
    │                  │                 ├──enables──> [Department Attribution]
    │                  │                 ├──enables──> [Civic Relevance Score]
    │                  │                 └──enables──> [Search Keyword Enrichment]
    │                  └──enables──> [Quality Audit]
    │                                    ├──enables──> [Quality Scores per Dataset]
    │                                    └──enables──> [Data Quality Report Page]
    ├──enables──> [Diff Detection]
    │                  └──enables──> ["What Changed" Page]
    └──enables──> [Static Site Export]
                       ├──requires──> [Search Index Build (Lunr/Fuse)]
                       ├──requires──> [Dataset Detail Page Templates]
                       ├──requires──> [Category Browse Pages]
                       ├──requires──> [Filter UI]
                       └──requires──> [About / Disclaimer Page]

[Search Keyword Enrichment] ──enhances──> [Full-text Search Quality]

[Related Datasets] ──requires──> [Category/Tag Data from Metadata Pull]
                   ──enhanced-by──> [AI Enrichment] (optional upgrade)
```

### Dependency Notes

- **AI Enrichment requires SQLite Storage:** Enrichment reads raw metadata from the database and writes enrichment results back. Must have schema and data before enrichment runs.
- **Quality Audit requires SQLite Storage:** Audit queries metadata fields to compute completeness, freshness, and coverage scores.
- **Diff Detection requires previous pull state:** The diff compares current pull against stored previous state. First run has no diff. Requires at least two pulls.
- **Static Site Export requires Search Index + Templates:** Export generates both HTML pages and the JSON search index consumed by Lunr.js/Fuse.js.
- **Search Keyword Enrichment enhances Full-text Search:** Without enriched keywords, search only hits raw metadata terms. With them, residents searching "road construction" find "Right of Way Permits."
- **Related Datasets can work without AI:** Tag/category overlap is a simple first pass. AI enrichment can upgrade to semantic similarity later.

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the core value proposition: "Every Miami-Dade open dataset is discoverable and understandable by a non-technical resident."

- [ ] **Metadata pull from both portals** — Without data, nothing else works
- [ ] **SQLite storage** — Foundation for everything downstream
- [ ] **AI enrichment (descriptions + use cases + keywords)** — This IS the product. Without it, this is just a worse version of the existing portals
- [ ] **Quality audit** — Low marginal cost, high accountability value
- [ ] **Static site with search + browse + dataset pages** — Delivery mechanism for the enriched catalog
- [ ] **GitHub Pages deployment** — Free, automated, zero-maintenance hosting
- [ ] **CLI tool (`mdc-encyclopedia`)** — Developer interface for all operations

### Add After Validation (v1.x)

Features to add once core is working and feedback is gathered.

- [ ] **Diff detection + "What Changed" page** — Add after second weekly pull establishes baseline for comparison
- [ ] **Related datasets** — Add once category/tag data quality is understood from v1 audit
- [ ] **Civic relevance scoring** — Add once enrichment quality is validated; refine prompt based on v1 results
- [ ] **Department attribution browsing** — Add once AI-inferred departments are spot-checked for accuracy
- [ ] **Data quality report page** — Add once audit methodology is validated against manual review

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **RSS feed for changes** — Low-effort alerting without full notification infrastructure
- [ ] **Downloadable catalog JSON/CSV** — For developers who want bulk access
- [ ] **Embeddable widgets** — Let other civic sites embed dataset cards
- [ ] **Multi-jurisdiction support** — Only after Miami-Dade is solid and there's demand

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Full-text search | HIGH | MEDIUM | P1 |
| Browse by category | HIGH | LOW | P1 |
| Dataset detail pages | HIGH | MEDIUM | P1 |
| Metadata display | HIGH | LOW | P1 |
| Source portal links | HIGH | LOW | P1 |
| Column/field info | MEDIUM | LOW-MEDIUM | P1 |
| AI plain-English descriptions | HIGH | MEDIUM | P1 |
| AI use cases | HIGH | LOW (bundled w/ descriptions) | P1 |
| Search keyword enrichment | HIGH | LOW (bundled w/ enrichment) | P1 |
| Quality scoring | MEDIUM | MEDIUM | P1 |
| Responsive layout | MEDIUM | LOW | P1 |
| Freshness indicator | MEDIUM | LOW | P1 |
| About/disclaimer page | MEDIUM | LOW | P1 |
| Filtering (format/publisher/tag) | MEDIUM | MEDIUM | P1 |
| Cross-portal unified view | HIGH | MEDIUM | P1 |
| Diff detection / "What Changed" | MEDIUM | MEDIUM | P2 |
| Related datasets | MEDIUM | MEDIUM | P2 |
| Department attribution browse | MEDIUM | LOW | P2 |
| Civic relevance scoring | MEDIUM | LOW | P2 |
| Data quality report page | MEDIUM | MEDIUM | P2 |
| RSS feed for changes | LOW | LOW | P3 |
| Downloadable catalog export | LOW | LOW | P3 |
| Embeddable widgets | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | CKAN (data.gov) | Socrata (Miami-Dade) | ArcGIS Hub (Miami-Dade) | Magda (data.gov.au) | OpenDataSoft | **Our Approach** |
|---------|-----------------|---------------------|------------------------|--------------------|--------------|--------------------|
| Search | Solr-powered, faceted | Keyword + filters | Keyword + spatial | Elasticsearch, synonym-aware | AI-powered NLP | Client-side Lunr.js/Fuse with AI-enriched keywords |
| Dataset pages | Basic metadata + preview | Rich metadata + viz | Map-focused + metadata | Clean metadata layout | Rich metadata + viz | Metadata + AI enrichment + quality score + use cases |
| Plain-English descriptions | No (raw metadata only) | No (publisher-written) | No (publisher-written) | No (auto-derived partial) | No (processor-based) | **YES — Claude-generated, resident-focused** |
| Data quality score | No | No | No | Planned (roadmap) | No public score | **YES — Automated composite score** |
| Change tracking | Revision history per dataset | Activity log (admin only) | No | No public changelog | No public changelog | **YES — Public "What Changed" page** |
| Cross-portal | Single source | Single source | Single source | Federated harvesting | Single or hub | **YES — Socrata + ArcGIS unified** |
| Civic use cases | No | No | No | No | No | **YES — AI-generated per dataset** |
| Column documentation | Available via API | Available via API | Available via layer def | Available | Available | Display prominently on dataset page |
| Department browsing | Organization pages | No (tags only) | No | Organization pages | Producer facet | **AI-inferred department + browse pages** |
| Resident-friendly language | No (technical audience) | Minimal | Minimal | No (technical audience) | Better than most | **Core mission — every element in plain English** |

## Sources

- CKAN features: https://ckan.org/features/search, https://ckan.org/features/metadata/, https://ckan.org/features/api
- Socrata catalog UX: https://support.socrata.com/hc/en-us/articles/202949778-Navigating-the-dataset-catalog
- Magda (data.gov.au): https://magda.io/, https://github.com/magda-io/magda, https://atlan.com/magda-data-catalog/
- PortalJS / Datopian: https://www.portaljs.com/, https://github.com/datopian/portaljs
- OpenDataSoft features: https://opendatasoft.com/en/data-catalog-2, https://www.opendatasoft.com/en/processing-enriching/
- Open data portal usability research: https://www.sciencedirect.com/science/article/abs/pii/S0736585320301982, https://www.sciencedirect.com/science/article/abs/pii/S0736585325000462
- Data quality scoring (Toronto): https://medium.com/open-data-toronto/towards-a-data-quality-score-in-open-data-part-1-525e59f729e9, https://open.toronto.ca/towards-an-updated-data-quality-score-in-open-data/
- Metadata quality frameworks: https://dl.acm.org/doi/10.1145/2964909
- Portal metadata enrichment: https://www.portaljs.com/blog/how-rich-metadata-powers-data-discovery-in-modern-data-catalogs
- CKAN vs Socrata comparison: https://publicsectornetwork.com/insight/government-open-data-portals-a-look-at-ckan-and-socrata
- Open data portal criticism: https://civic.io/2015/04/01/i-hate-open-data-portals/
- AI metadata enrichment: https://datahub.com/blog/ai-assisted-data-catalogs-an-llm-powered-by-knowledge-graphs-for-metadata-discovery/
- LLM dataset enrichment research: https://link.springer.com/chapter/10.1007/978-3-032-08366-1_5
- AWS Glue AI enrichment: https://aws.amazon.com/blogs/big-data/enrich-your-aws-glue-data-catalog-with-generative-ai-metadata-using-amazon-bedrock/
- datHere 2026 open data trends: https://dathere.com/2026/01/2025-the-year-opening-data-was-great-again/
- Gartner government open data platforms: https://www.gartner.com/reviews/market/government-open-data-management-platforms
- World Bank Open Data Toolkit: https://opendatatoolkit.worldbank.org/en/data/opendatatoolkit/technology
- Awesome data catalogs list: https://github.com/opendatadiscovery/awesome-data-catalogs

---
*Feature research for: Miami-Dade County Open Data Encyclopedia*
*Researched: 2026-02-24*
