# Phase 9: Atom Feed - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Generate an Atom 1.0 feed during site build so users can subscribe to catalog changes (new datasets, removed datasets, schema changes) via any standard feed reader. Covers FEED-01, FEED-02, FEED-03. Per-jurisdiction feeds and RSS dual format are deferred to v1.2.

</domain>

<decisions>
## Implementation Decisions

### Feed entry content
- Title uses prefix tag format: `[New] Building Permits`, `[Removed] Old Zoning Map`, `[Schema Change] Code Violations`
- Entry body is a 1-2 sentence summary — not full dataset detail, not title-only
- Jurisdiction is mentioned in the summary body (e.g. "A new dataset from Broward County...")
- Each entry links to the encyclopedia's own dataset detail page, not the source portal

### CLI & build integration
- atom.xml is generated as part of the existing site export command — not a separate CLI command
- When `--site-url` is omitted: skip feed generation with a warning, build the rest of the site normally. Feed is optional, not a hard requirement for build success
- atom.xml placed at site root (`/atom.xml`) — standard convention for autodiscovery
- No `--no-feed` flag needed — presence of `--site-url` is the implicit trigger for feed generation

### Claude's Discretion
- Feed metadata (title, subtitle, author fields)
- Number of entries to include in the feed
- How to detect and categorize changes (new vs removed vs schema change)
- Autodiscovery `<link>` tag placement and attributes in HTML head
- Atom XML library or template approach

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. Follow Atom 1.0 spec conventions.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (Per-jurisdiction feeds and RSS 2.0 dual format already tracked as FEED-04/FEED-06 in v1.2 requirements.)

</deferred>

---

*Phase: 09-atom-feed*
*Context gathered: 2026-02-27*
