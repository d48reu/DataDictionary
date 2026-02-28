# Phase 8: Multi-Jurisdiction Foundation - Context

**Gathered:** 2026-02-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Expand the single-portal encyclopedia to pull and store datasets from multiple South Florida jurisdictions (Miami-Dade County, Broward County, City of Miami) in a unified catalog. Requires jurisdiction registry, parameterized hub client, Schema V3 migration with composite keys, and per-jurisdiction CLI pull. Site UI changes (filters, badges, search) belong in Phase 12.

</domain>

<decisions>
## Implementation Decisions

### Jurisdiction lineup
- Include three jurisdictions in v1.1: Miami-Dade County, Broward County, City of Miami
- City of Miami included if it has a compatible ArcGIS Hub portal (researcher should verify)
- Short CLI slugs: `miami-dade`, `broward`, `miami`
- Full display names: "Miami-Dade County", "Broward County", "City of Miami"

### Jurisdiction registry
- External config file (YAML or JSON), not hardcoded in Python
- Users can add new ArcGIS Hub jurisdictions by editing the config file without code changes
- Registry maps slug to base URL, display name, and portal type

### AI enrichment prompts
- Jurisdiction-specific prompts — swap jurisdiction name into system prompt
- e.g., "Broward County data librarian" instead of generic "South Florida" prompt
- More contextually accurate descriptions per jurisdiction

### Migration safety
- Auto-backup the database file before running V3 migration (timestamped copy)
- No dry-run mode — auto-backup provides the safety net
- Auto-assign `jurisdiction='miami-dade'` to all existing datasets (deterministic — they all came from opendata.miamidade.gov)
- Auto-migrate on first CLI run after upgrade (same seamless pattern as V1→V2 migration)

### Claude's Discretion
- Composite key design (synthetic PK vs composite TEXT key)
- Config file format choice (YAML vs JSON)
- Hub client refactoring approach
- Pull sequential vs parallel execution
- Progress reporting format for multi-jurisdiction pulls
- Stats command output format and jurisdiction breakdown layout
- Error handling when one jurisdiction's portal is unavailable

</decisions>

<specifics>
## Specific Ideas

- Registry should be a standalone config file that's easy to edit — think of it as an extensibility point for adding more jurisdictions later
- Migration should feel invisible to existing users — auto-backup, auto-migrate, no manual steps
- AI prompts should reference the specific jurisdiction so enrichment descriptions mention the right county/city context

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 08-multi-jurisdiction-foundation*
*Context gathered: 2026-02-26*
