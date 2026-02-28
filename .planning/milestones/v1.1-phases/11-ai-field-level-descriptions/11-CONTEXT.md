# Phase 11: AI Field-Level Descriptions - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Generate AI plain-English descriptions for every column in B+ quality datasets. Provide a CLI command (`enrich-fields`) with dry-run, limit, and resume capabilities. Display descriptions inline on dataset detail pages with AI transparency badges. Also closes tech debt gaps: jurisdiction-aware prompts, ai_description write-through, dead code removal.

</domain>

<decisions>
## Implementation Decisions

### CLI behavior & cost control
- `--dry-run` output: summary line (datasets, columns, estimated cost) PLUS a table listing each eligible dataset name and column count
- Progress reporting: one line per dataset as it completes — "Enriching Parks (14 columns)... done [3/12]"
- `--resume` behavior: silently skip already-enriched datasets; end summary shows "skipped N already-enriched"
- Error handling: retry once after short delay on API failure; if still fails, skip that dataset and continue; summary lists all failures at end

### Enrichment eligibility & edge cases
- Auto-skip known system columns (OBJECTID, Shape, GlobalID, etc.) — do not send to AI
- Chunk large datasets into batches of ~30 columns per API call to stay within token limits, then merge results
- Newly eligible datasets (quality upgraded to B+) get enriched on next run; already-enriched datasets keep their descriptions
- Include 3-5 sample data values per column alongside column name and data type in the AI prompt for better description quality

### Claude's Discretion
- Description tone and depth (plain-English balance, length per column)
- AI badge styling and placement on detail pages
- Exact system column skip list
- Batch size tuning (starting point ~30, adjust based on token limits)
- Loading/empty states for field descriptions on detail pages

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches for description tone, badge styling, and display layout.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 11-ai-field-level-descriptions*
*Context gathered: 2026-02-27*
