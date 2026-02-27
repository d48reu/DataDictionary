# Phase 10: Enriched Catalog Export - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Downloadable JSON and CSV files of the full enriched catalog, with DCAT-US v1.1 field alignment and download links on the About page. Developers and data users can use these files in their own tools. This phase does NOT include per-jurisdiction filtering, API endpoints, or streaming downloads.

</domain>

<decisions>
## Implementation Decisions

### DCAT-US field mapping
- Practical subset alignment — map the DCAT-US v1.1 fields we can actually populate from our data, skip fields we can't
- JSON structure follows the federal data.json convention: root object with `conformsTo` and `dataset` array
- Use standard DCAT-US property names (title, description, publisher, keyword, modified, distribution, etc.)
- Omit unpopulated fields entirely — no nulls or placeholders for fields like contactPoint or accessLevel

### Export content scope
- Include AI enrichment data (summaries, quality grades) as extra fields beyond standard DCAT — this is the unique value-add
- Single combined file across all jurisdictions, with a jurisdiction field on each record
- Current snapshot only — no change history (Atom feed covers change tracking)
- Multi-value fields in CSV (tags, themes) use semicolon separation within a single column

### Claude's Discretion
- About page download link styling and placement
- CSV column ordering
- CSV column header naming (DCAT names vs human-friendly — can differ from JSON)
- File naming convention for generated exports
- Whether to include a dataset count or generation timestamp in the JSON metadata

</decisions>

<specifics>
## Specific Ideas

- JSON should feel like a data.gov catalog file — familiar to anyone in the open data ecosystem
- CSV must open correctly in Excel on Windows (UTF-8 BOM requirement from success criteria)
- Enrichments as extra fields means the file is useful even for consumers who don't know about DCAT

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-enriched-catalog-export*
*Context gathered: 2026-02-27*
