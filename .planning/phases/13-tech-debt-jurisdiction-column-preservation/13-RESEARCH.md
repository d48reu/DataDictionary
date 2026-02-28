# Phase 13: Tech Debt -- Jurisdiction Wiring & Column Preservation - Research

**Researched:** 2026-02-27
**Domain:** SQLite upsert patterns, CLI argument threading, Python/Click command wiring
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- When a dataset has no jurisdiction set, `enrich` must SKIP that dataset (do not default to Miami-Dade)
- Print inline warning per skipped dataset: `Warning Skipping {dataset}: no jurisdiction set`
- No bulk-set command needed -- jurisdiction was set during Phase 8; missing ones are edge cases
- `get_unenriched_datasets()` returns ALL datasets (including those without jurisdiction) with a `jurisdiction` field; the enrich command handles skip logic
- Preserve ALL `ai_*` prefixed fields during pull, not just `ai_description` -- future-proofs against new AI fields
- New columns from the API get `ai_description = NULL` (shows as unenriched, flagged for future enrichment)
- If the API removes a column that exists locally, DELETE the local record -- match API truth, don't keep orphans
- Preservation is silent -- no log output when ai_* fields are kept during pull
- The `upsert_columns()` fix should mirror the existing `upsert_dataset()` pattern -- success criteria #4 explicitly calls this out
- The inline skip warning should match the existing CLI output style used by other commands

### Claude's Discretion
- Exact SQL pattern for INSERT OR REPLACE with subquery (success criteria specifies the pattern but Claude picks implementation)
- How jurisdiction gets injected into the AI prompt template
- Any internal refactoring needed to thread jurisdiction through the call chain

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

## Summary

This phase closes two cross-phase tech debt items identified in the v1.1 milestone audit. Both are surgical fixes to existing code -- no new modules, no new dependencies, no schema changes.

**Debt item 1 (HIGH):** The `enrich` CLI command in `cli.py` calls `enrich_dataset()` without passing a `jurisdiction` keyword argument. The `get_unenriched_datasets()` query in `db.py` does not SELECT the `jurisdiction` column. As a result, all datasets -- including Broward and City of Miami -- receive Miami-Dade-specific AI prompts with Miami-Dade department lists. The fix requires adding `d.jurisdiction` to the SQL SELECT, loading the jurisdiction registry in the enrich command, resolving the slug to a display name, and passing it to `enrich_dataset()`. The `enrich_fields` path is already correctly wired and serves as the reference pattern.

**Debt item 2 (MEDIUM):** The `upsert_columns()` function in `db.py` (line 414) uses DELETE-then-INSERT, which destroys any `ai_description` values previously set by `enrich-fields`. The fix is to replace the delete-and-reinsert with INSERT OR REPLACE using a subquery to carry forward existing `ai_*` fields, mirroring the pattern already used by `upsert_dataset()` at line 361-368.

**Primary recommendation:** Both fixes are contained within `db.py` and `cli.py`. No new files, no new dependencies, no schema migration. The existing `upsert_dataset()` pattern and `enrich_fields` jurisdiction wiring serve as proven reference implementations.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib | Database operations | Already in use; INSERT OR REPLACE is native SQLite |
| click (rich_click) | current | CLI command wiring | Already the CLI framework |
| anthropic | current | AI enrichment client | Already in use |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyYAML | current | Load jurisdiction registry | Already used via `registry.py` |
| rich | current | Console output for skip warnings | Already used for all CLI output |

### Alternatives Considered
None -- this is internal refactoring using existing libraries only.

**Installation:**
No new dependencies required.

## Architecture Patterns

### Pattern 1: Subquery Preservation on INSERT OR REPLACE (existing `upsert_dataset()` pattern)

**What:** When upserting a record that has AI-generated fields, use a subquery in the VALUES clause to carry forward existing values that would otherwise be lost by the REPLACE.

**When to use:** Any INSERT OR REPLACE where some columns contain expensive-to-regenerate data not present in the incoming record.

**Reference implementation** (`db.py` lines 361-368):
```python
conn.execute(
    """INSERT OR REPLACE INTO datasets
    (id, jurisdiction, arcgis_id, source_portal, source_url, title,
     description, category, publisher, format, created_at, updated_at,
     row_count, tags, license, api_endpoint, bbox, download_url,
     metadata_json, pulled_at, ai_description)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            datetime('now'),
            (SELECT ai_description FROM datasets WHERE id = ?))""",
    (
        dataset["id"],
        # ... other fields ...
        dataset["id"],  # <-- repeated for subquery
    ),
)
```

**Key insight:** The subquery `(SELECT ai_description FROM datasets WHERE id = ?)` runs before the REPLACE deletes the old row, so the value is preserved. SQLite evaluates the full VALUES expression before performing the delete-insert that REPLACE entails.

### Pattern 2: Jurisdiction Display Name Resolution (existing `enrich_fields` pattern)

**What:** Look up the jurisdiction slug in the registry to get the human-readable `display_name`, then pass it to the prompt builder.

**When to use:** Any enrichment call that needs jurisdiction-specific prompt content.

**Reference implementation** (`client.py` line 251-252):
```python
jurisdiction = dataset.get("jurisdiction", "Miami-Dade County")
system_prompt = build_field_system_prompt(jurisdiction)
```

**Important difference for `enrich` command:** The `enrich_fields` function reads `jurisdiction` directly from the dataset dict, but that field contains the slug (e.g., `"broward"`), not the display name (e.g., `"Broward County"`). The `enrich` command needs to resolve the slug to a display name via the registry. The `enrich_fields` path works because `build_field_system_prompt()` receives a slug and the prompt template just formats it. But `build_system_prompt()` uses the display name for department logic (the `if jurisdiction_display_name == "Miami-Dade County"` check at `prompts.py` line 69).

### Pattern 3: Column Orphan Deletion (user decision)

**What:** When the API no longer returns a column that exists locally, remove the local record entirely.

**When to use:** During `upsert_columns()` -- after upserting all incoming columns, delete any local columns not present in the incoming set.

**Implementation approach:** After the INSERT OR REPLACE loop, execute a DELETE for `dataset_id = ? AND name NOT IN (...)` using the incoming column names. This matches API truth without keeping stale orphan records.

### Anti-Patterns to Avoid

- **DELETE-then-INSERT for upsert:** This is the current bug. It destroys data in columns not present in the incoming record. Use INSERT OR REPLACE with subquery instead.
- **Hardcoded jurisdiction fallback:** Do not default missing jurisdictions to "Miami-Dade County". The user decision is to SKIP datasets with no jurisdiction set.
- **Logging on preservation:** The user explicitly decided that ai_* field preservation should be silent. Do not add log lines for "preserved ai_description for column X".

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Jurisdiction slug-to-display resolution | Custom lookup dict | `load_registry()` + `registry[slug]["display_name"]` | Registry already exists and is the single source of truth |
| SQL upsert with selective preservation | Custom merge logic | `INSERT OR REPLACE` with `SELECT` subquery | SQLite-native, proven pattern already in codebase |

**Key insight:** Both fixes have reference implementations already in the codebase. The `upsert_dataset()` function shows the exact SQL pattern for column preservation. The `enrich_fields` function shows how jurisdiction flows through to prompt building. Copy these patterns, don't invent new ones.

## Common Pitfalls

### Pitfall 1: INSERT OR REPLACE Subquery Timing
**What goes wrong:** Developer assumes the subquery runs after the REPLACE deletes the row, returning NULL.
**Why it happens:** Misunderstanding of SQLite's INSERT OR REPLACE execution order.
**How to avoid:** SQLite evaluates the entire VALUES clause (including subqueries) before performing the delete-insert. The existing `upsert_dataset()` proves this works. Test by round-tripping: insert a column with ai_description, upsert without ai_description, verify preservation.
**Warning signs:** ai_description values becoming NULL after pull.

### Pitfall 2: UNIQUE Constraint Requirement for INSERT OR REPLACE
**What goes wrong:** INSERT OR REPLACE silently becomes INSERT-only if there's no UNIQUE constraint violation to trigger the REPLACE behavior.
**Why it happens:** INSERT OR REPLACE only replaces when it would violate a UNIQUE or PRIMARY KEY constraint.
**How to avoid:** The `columns` table already has `UNIQUE(dataset_id, name)` (schema line 47). This is the trigger for REPLACE. Verify this constraint exists before implementing.
**Warning signs:** Duplicate rows appearing in the columns table.

### Pitfall 3: Jurisdiction Slug vs Display Name Confusion
**What goes wrong:** Passing the slug "broward" where the display name "Broward County" is expected, or vice versa.
**Why it happens:** The dataset's `jurisdiction` field stores the slug. The prompt builder expects the display name. These are different strings.
**How to avoid:** Always resolve through the registry: `registry[slug]["display_name"]`. The `build_system_prompt()` function has an equality check `if jurisdiction_display_name == "Miami-Dade County"` that requires the exact display name string, not the slug.
**Warning signs:** All datasets getting generic department guidance instead of Miami-Dade-specific departments.

### Pitfall 4: Missing Jurisdiction Edge Case
**What goes wrong:** A dataset exists in the DB with `jurisdiction` as NULL or empty string (theoretically impossible per schema `NOT NULL`, but edge cases exist).
**Why it happens:** Migration artifacts or manual DB edits.
**How to avoid:** The user decision is clear: `get_unenriched_datasets()` returns ALL datasets including those without jurisdiction. The `enrich` command checks for jurisdiction and SKIPs with a warning. Guard with `if not ds.get("jurisdiction"):`.
**Warning signs:** Enrichment producing wrong-jurisdiction summaries for edge-case datasets.

### Pitfall 5: Orphan Deletion Order
**What goes wrong:** Deleting orphan columns before upserting new ones causes FK or logic issues.
**Why it happens:** Incorrect ordering of operations.
**How to avoid:** Upsert all incoming columns first (INSERT OR REPLACE), then delete orphans. This ensures the column set matches the API at the end.
**Warning signs:** Columns appearing and disappearing unexpectedly.

## Code Examples

### Fix 1: `get_unenriched_datasets()` -- Add jurisdiction to SELECT

Current code (`db.py` lines 439-449):
```python
rows = conn.execute(
    """
    SELECT d.id, d.title, d.description, d.category, d.publisher,
           d.tags, d.updated_at, d.created_at, d.format
    FROM datasets d
    LEFT JOIN enrichments e ON d.id = e.dataset_id
    WHERE e.id IS NULL
    ORDER BY d.title
    """
).fetchall()
```

Fixed code:
```python
rows = conn.execute(
    """
    SELECT d.id, d.title, d.description, d.category, d.publisher,
           d.tags, d.updated_at, d.created_at, d.format, d.jurisdiction
    FROM datasets d
    LEFT JOIN enrichments e ON d.id = e.dataset_id
    WHERE e.id IS NULL
    ORDER BY d.title
    """
).fetchall()
```

Change: Add `d.jurisdiction` to the SELECT list. One field, one line.

### Fix 2: `upsert_columns()` -- INSERT OR REPLACE with ai_* preservation

Current code (`db.py` lines 413-423):
```python
conn.execute("DELETE FROM columns WHERE dataset_id = ?", (dataset_id,))

for col in columns:
    conn.execute(
        "INSERT INTO columns (dataset_id, name, data_type, description) VALUES (?, ?, ?, ?)",
        (dataset_id, col["name"], col["data_type"], col["description"]),
    )
```

Fixed code:
```python
for col in columns:
    conn.execute(
        """INSERT OR REPLACE INTO columns
        (dataset_id, name, data_type, description, ai_description)
        VALUES (?, ?, ?, ?,
                (SELECT ai_description FROM columns
                 WHERE dataset_id = ? AND name = ?))""",
        (
            dataset_id, col["name"], col["data_type"], col["description"],
            dataset_id, col["name"],
        ),
    )

# Delete orphan columns not in the incoming set
if columns:
    placeholders = ",".join("?" for _ in columns)
    incoming_names = [col["name"] for col in columns]
    conn.execute(
        f"DELETE FROM columns WHERE dataset_id = ? AND name NOT IN ({placeholders})",
        [dataset_id] + incoming_names,
    )
else:
    conn.execute("DELETE FROM columns WHERE dataset_id = ?", (dataset_id,))
```

Changes:
1. Remove the blanket DELETE at the top
2. Use INSERT OR REPLACE with subquery to preserve `ai_description`
3. Add orphan cleanup after upsert to delete columns the API no longer reports

### Fix 3: `enrich` command -- Thread jurisdiction through to `enrich_dataset()`

Current code (`cli.py` lines 424-428):
```python
result = enrich_dataset(
    client, model, ds, columns_by_dataset.get(ds["id"], [])
)
```

Fixed code:
```python
# At top of enrich(), after loading registry:
registry = load_registry()

# In the enrichment loop, before calling enrich_dataset:
jurisdiction_slug = ds.get("jurisdiction")
if not jurisdiction_slug:
    console.print(
        f"[yellow]Warning Skipping {ds.get('title', ds['id'])}: "
        f"no jurisdiction set[/yellow]"
    )
    progress.advance(task)
    continue

# Resolve display name from registry
jurisdiction_config = registry.get(jurisdiction_slug, {})
display_name = jurisdiction_config.get(
    "display_name", jurisdiction_slug.replace("-", " ").title()
)

result = enrich_dataset(
    client, model, ds, columns_by_dataset.get(ds["id"], []),
    jurisdiction=display_name,
)
```

Changes:
1. Load registry at the start of the `enrich` command
2. Check for missing jurisdiction and skip with warning
3. Resolve slug to display name via registry
4. Pass `jurisdiction=display_name` to `enrich_dataset()`

Note: The `enrich_dataset()` function already accepts a `jurisdiction` keyword argument (client.py line 63) -- it just defaults to "Miami-Dade County". No changes needed in `client.py`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| DELETE + INSERT for column upsert | INSERT OR REPLACE with subquery | This phase | Preserves ai_* fields across pulls |
| Hardcoded Miami-Dade in enrich | Registry-resolved jurisdiction | This phase | Correct AI prompts for all jurisdictions |

**Deprecated/outdated:**
- The DELETE-then-INSERT pattern in `upsert_columns()` was adequate before field-level AI enrichment existed (pre-Phase 11). After Phase 11 added `ai_description` to columns, it became destructive.

## Open Questions

1. **Future `ai_*` fields beyond `ai_description`**
   - What we know: User decision says preserve ALL `ai_*` prefixed fields, not just `ai_description`. Currently the columns table only has `ai_description`.
   - What's unclear: Whether future schema migrations will add more `ai_*` fields to the columns table.
   - Recommendation: The INSERT OR REPLACE with subquery pattern naturally handles this. If new `ai_*` columns are added to the schema, the upsert SQL must be updated to include them in the subquery. For now, `ai_description` is the only one. Document this in a code comment.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis: `db.py`, `cli.py`, `enrichment/client.py`, `enrichment/prompts.py`, `registry.py`
- `v1.1-MILESTONE-AUDIT.md` -- exact tech debt items with file/line references
- `jurisdictions.yaml` -- registry structure with 3 jurisdictions
- SQLite documentation on INSERT OR REPLACE behavior (well-established, stable behavior)

### Secondary (MEDIUM confidence)
- None needed -- all findings are from direct codebase inspection

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, all existing code patterns
- Architecture: HIGH -- both fixes have reference implementations already in the codebase
- Pitfalls: HIGH -- identified from direct code analysis of the exact functions being modified

**Research date:** 2026-02-27
**Valid until:** Indefinite -- this is internal refactoring of stable code, not dependent on external library versions
