# Phase 3: AI Enrichment - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Claude API generates plain-English metadata for every dataset in the catalog — descriptions, use cases, keywords, department attribution, update frequency, and civic relevance scoring. Users run `mdc-encyclopedia enrich` as a CLI command with dry-run, resume, and cost estimation. Prompt design, output quality, and storage are in scope. Site generation and display of enrichments are Phase 6.

</domain>

<decisions>
## Implementation Decisions

### Enrichment tone & depth
- Mixed audience: lead with plain English for non-technical residents, include a brief technical note for power users (journalists, developers)
- Descriptions are 2-3 sentences per dataset — enough to understand what it is and why it matters
- Use cases are 2-3 scenario-based examples per dataset (e.g., "A homeowner checking flood risk before buying", "A journalist investigating permit delays")
- Keywords should be terms a resident would search for, not technical field names

### Civic relevance scoring
- Impact-based criteria for HIGH/MEDIUM/LOW:
  - HIGH = directly affects residents (permits, transit, health, housing, public safety)
  - MEDIUM = useful for understanding Miami-Dade (budget, demographics, environmental data)
  - LOW = administrative or internal (IT inventory, employee records, internal workflows)

### Cost control & confirmation
- Show estimated cost before enrichment begins
- Auto-proceed if estimated cost is under $5 (typical for incremental runs of 50-100 new datasets)
- Prompt for Y/N confirmation if estimated cost exceeds $5
- No hard budget cap — the catalog is finite (~500 datasets), so approve and let it finish
- `--dry-run` flag shows what would be enriched and cost estimate without calling API

### Resume & interruption handling
- Each dataset marked as enriched in the database immediately after successful API call
- `--resume` picks up from the first unenriched dataset — no re-enrichment of completed records
- Safe to Ctrl+C at any point; no partial/corrupt enrichment records

### Claude's Discretion
- Prompt engineering — exact prompt structure, system message, few-shot examples
- Whether to use one API call per dataset or batch multiple fields
- Rate limiting strategy for Anthropic API
- How to handle datasets with minimal metadata (few columns, no description)
- Progress bar implementation and per-dataset feedback in CLI
- Prompt version tracking schema

</decisions>

<specifics>
## Specific Ideas

- Descriptions should feel like something a county librarian would write — helpful, clear, no bureaucratic jargon
- Department attribution should map to actual Miami-Dade County departments when possible (not generic categories)
- Update frequency inference should be based on actual data timestamps if available, not just guessing

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-ai-enrichment*
*Context gathered: 2026-02-25*
