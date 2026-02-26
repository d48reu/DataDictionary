# Phase 5: Change Detection - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

CLI command (`mdc-encyclopedia diff`) that shows what changed between catalog pulls — newly added datasets, removed datasets, and column additions/removals. Results stored in SQLite changes table for the static site export. Also integrates diff computation into the `pull` command for automatic change tracking.

</domain>

<decisions>
## Implementation Decisions

### Change granularity
- Structural changes only: dataset added, dataset removed, columns added/removed on existing datasets
- No metadata change tracking (description, tags, row_count changes are ignored)
- Column changes limited to additions and removals — no type change or rename detection
- Removed datasets reported honestly as removed; no soft-delete grace period or API-flakiness handling
- If a dataset disappears then reappears, it shows as "removed" then "added" in successive diffs

### Change storage
- Append-only changelog: each pull appends new change records with timestamps
- Enables "history of changes over time" on the static site
- Running `diff` displays stored results; it does not recompute

### Pull integration
- `pull` automatically computes and stores the diff after ingestion completes
- Pull prints a one-liner count summary: "3 added, 1 removed, 5 with column changes. Run `diff` for details."
- First pull (no previous state): print "First pull — {N} datasets cataloged. Future pulls will show changes."
- `diff` command displays the full detailed breakdown of stored change records

### Claude's Discretion
- Diff output formatting and Rich table layout
- Snapshot mechanism (how "previous state" is captured for comparison)
- Schema design for the changes table
- How `diff` groups and sorts the output (by change type, by dataset, etc.)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-change-detection*
*Context gathered: 2026-02-25*
