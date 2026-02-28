# Phase 11: AI Field-Level Descriptions - Research

**Researched:** 2026-02-27
**Domain:** AI enrichment pipeline (field-level), CLI design, static site rendering
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- `--dry-run` output: summary line (datasets, columns, estimated cost) PLUS a table listing each eligible dataset name and column count
- Progress reporting: one line per dataset as it completes -- "Enriching Parks (14 columns)... done [3/12]"
- `--resume` behavior: silently skip already-enriched datasets; end summary shows "skipped N already-enriched"
- Error handling: retry once after short delay on API failure; if still fails, skip that dataset and continue; summary lists all failures at end
- Auto-skip known system columns (OBJECTID, Shape, GlobalID, etc.) -- do not send to AI
- Chunk large datasets into batches of ~30 columns per API call to stay within token limits, then merge results
- Newly eligible datasets (quality upgraded to B+) get enriched on next run; already-enriched datasets keep their descriptions
- Include 3-5 sample data values per column alongside column name and data type in the AI prompt for better description quality

### Claude's Discretion
- Description tone and depth (plain-English balance, length per column)
- AI badge styling and placement on detail pages
- Exact system column skip list
- Batch size tuning (starting point ~30, adjust based on token limits)
- Loading/empty states for field descriptions on detail pages

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FIELD-01 | AI-generated plain-English descriptions for all columns in B+ quality datasets | New Pydantic model `FieldEnrichmentResult`, new `enrich_fields()` function, B+ eligibility query joining audit_scores with letter_grade IN ('A', 'B'), new DB storage for field AI descriptions |
| FIELD-02 | `enrich-fields` CLI command with `--dry-run`, `--limit`, and `--resume` flags | New CLI command modeled on existing `enrich` command pattern; dry-run shows table of eligible datasets + column counts + cost estimate; resume checks existing field enrichments |
| FIELD-03 | Field descriptions displayed inline in dataset detail page columns table with AI badge | Template modification to dataset.html columns table; new `ai_description` column in `columns` table or separate `field_enrichments` table; AI badge CSS class |
| FIELD-04 | Batch all columns per dataset in single API call (not per-column) | Single prompt with all non-system columns per dataset; chunking at ~30 columns for large datasets with result merging |
</phase_requirements>

## Summary

Phase 11 adds AI-generated plain-English descriptions for individual columns (fields) in datasets that score B+ or higher in the quality audit. This is a natural extension of the existing dataset-level AI enrichment pipeline (Phase 3) but operates at a finer granularity -- per-column instead of per-dataset. The implementation touches four layers: database schema (new storage for field descriptions), enrichment pipeline (new Pydantic model, prompt, and client function), CLI (new `enrich-fields` command), and site rendering (template update with AI badge).

The codebase already has all the building blocks. The existing `enrich` command in `cli.py` (lines 314-465) demonstrates the exact pattern for cost estimation, dry-run, progress reporting, and error handling. The `enrichment/client.py` uses `messages.parse()` with Pydantic structured output -- the same approach works for field descriptions with a new model. The `enrichment/prompts.py` has `build_system_prompt()` ready for jurisdiction-aware prompts, but it is not yet wired into `enrich_dataset()` (tech debt item). The `columns` table already exists with `description` (from ArcGIS alias) but needs a new `ai_description` column for AI-generated content.

This phase also closes three tech debt items identified in the v1.0 audit: (1) wire `build_system_prompt()` into `enrich_dataset()` so existing dataset enrichment respects jurisdiction context, (2) add ai_description write-through in `insert_enrichment()` so the denormalized `datasets.ai_description` column stays in sync, and (3) remove the dead `get_datasets_by_jurisdiction()` function from `db.py`.

**Primary recommendation:** Add `ai_description` column to the `columns` table (Schema V4 migration), create a new `FieldEnrichmentResult` Pydantic model with a list of field descriptions, and build the `enrich-fields` CLI command by following the existing `enrich` command pattern exactly.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.80 | Claude API for structured output via `messages.parse()` | Already in use; `output_format` parameter with Pydantic model for guaranteed schema compliance |
| pydantic | (bundled with anthropic) | Structured output model definition | Already in use for `EnrichmentResult`; same pattern for `FieldEnrichmentResult` |
| rich / rich-click | >=13.0 / >=1.8 | CLI progress bars, tables, panels | Already in use throughout cli.py |
| sqlite3 | stdlib | Database storage | Already in use; Schema V4 migration adds `ai_description` to `columns` table |
| Jinja2 | >=3.1 | Template rendering for AI badge in columns table | Already in use for all site templates |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | >=1.0 | Load ANTHROPIC_API_KEY from .env | Already configured in enrichment client |
| tenacity | >=9.0 | Retry logic for API calls | Already in use for field fetching; use for field enrichment retries |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New `ai_description` column on `columns` table | Separate `field_enrichments` table | Separate table adds JOIN complexity; column is simpler and mirrors the `datasets.ai_description` pattern already established |
| `messages.parse()` structured output | Raw `messages.create()` + JSON parsing | Structured output guarantees schema compliance via constrained decoding; no need for manual JSON parsing or validation |

**Installation:**
No new dependencies needed. All libraries are already in `pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure
No new files needed beyond modifications to existing modules:
```
src/mdc_encyclopedia/
├── db.py                    # Schema V4 migration, new queries (get_b_plus_datasets, get_field_unenriched_datasets, update_column_ai_descriptions)
├── cli.py                   # New enrich-fields command
├── enrichment/
│   ├── client.py            # New enrich_fields() function, wire build_system_prompt() into enrich_dataset()
│   ├── models.py            # New FieldEnrichmentResult Pydantic model
│   └── prompts.py           # New build_field_prompt(), field-specific system prompt section
└── site/
    ├── context.py           # Pass ai_description from columns to template
    └── templates/
        └── dataset.html     # AI badge in columns table, show ai_description
```

### Pattern 1: Pydantic Structured Output for Field Descriptions
**What:** Define a `FieldEnrichmentResult` model that returns a list of `{column_name: str, description: str}` pairs, then use `messages.parse()` to get guaranteed schema compliance.
**When to use:** Every field enrichment API call.
**Example:**
```python
# Based on existing EnrichmentResult pattern in models.py
class FieldDescription(pydantic.BaseModel):
    column_name: str = pydantic.Field(description="Exact column name from the input")
    description: str = pydantic.Field(description="Plain-English description of what this column contains")

class FieldEnrichmentResult(pydantic.BaseModel):
    field_descriptions: list[FieldDescription] = pydantic.Field(
        description="Plain-English description for each column in the dataset"
    )
```

### Pattern 2: B+ Eligibility Query
**What:** Query datasets that have audit grade B or A AND have columns AND have not yet been field-enriched.
**When to use:** Building the list of eligible datasets for `enrich-fields`.
**Example:**
```python
# Join datasets + audit_scores + columns, filter by grade, exclude already-enriched
"""
SELECT d.id, d.title, d.jurisdiction, a.letter_grade,
       COUNT(c.id) as column_count
FROM datasets d
JOIN audit_scores a ON d.id = a.dataset_id
JOIN columns c ON d.id = c.dataset_id
WHERE a.letter_grade IN ('A', 'B')
  AND c.ai_description IS NULL
GROUP BY d.id
HAVING column_count > 0
ORDER BY d.title
"""
```

### Pattern 3: System Column Skip List
**What:** Filter out ArcGIS system columns before sending to AI.
**When to use:** Building the field enrichment prompt.
**Example:**
```python
SYSTEM_COLUMNS = {
    "OBJECTID", "FID", "Shape", "Shape_Length", "Shape_Area",
    "GlobalID", "SHAPE", "SHAPE_Length", "SHAPE_Area",
    "Shape__Length", "Shape__Area",  # Double-underscore variants
    "GDB_GEOMATTR_DATA",
}

def is_system_column(name: str) -> bool:
    return name in SYSTEM_COLUMNS or name.upper() in {c.upper() for c in SYSTEM_COLUMNS}
```

### Pattern 4: Chunked Enrichment for Large Datasets
**What:** Split datasets with >30 non-system columns into batches, enrich each batch separately, merge results.
**When to use:** Datasets with many columns (e.g., 311 service requests with 248 columns).
**Example:**
```python
def enrich_fields_for_dataset(client, model, dataset, columns):
    non_system = [c for c in columns if not is_system_column(c["name"])]

    if len(non_system) <= 30:
        # Single API call
        return _call_field_enrichment(client, model, dataset, non_system)

    # Chunk into batches of ~30
    all_descriptions = []
    for i in range(0, len(non_system), 30):
        batch = non_system[i:i+30]
        result = _call_field_enrichment(client, model, dataset, batch)
        all_descriptions.extend(result.field_descriptions)

    return FieldEnrichmentResult(field_descriptions=all_descriptions)
```

### Pattern 5: Write-Through on insert_enrichment (Tech Debt Fix)
**What:** When `insert_enrichment()` writes to the `enrichments` table, also update `datasets.ai_description` so the denormalized column stays in sync.
**When to use:** Every dataset enrichment (existing `enrich` command and future runs).
**Example:**
```python
def insert_enrichment(conn, dataset_id, result, prompt_version):
    # Existing INSERT OR REPLACE into enrichments
    conn.execute(...)

    # Write-through: sync datasets.ai_description
    conn.execute(
        "UPDATE datasets SET ai_description = ? WHERE id = ?",
        (result["description"], dataset_id),
    )
    conn.commit()
```

### Pattern 6: Schema V4 Migration
**What:** Add `ai_description` column to the `columns` table.
**When to use:** Database initialization/upgrade.
**Example:**
```python
SCHEMA_V4_UPGRADE = """
ALTER TABLE columns ADD COLUMN ai_description TEXT;
"""
# In init_db():
if version < 4:
    conn.execute("ALTER TABLE columns ADD COLUMN ai_description TEXT")
    conn.execute("PRAGMA user_version=4")
    conn.commit()
```

### Anti-Patterns to Avoid
- **One API call per column:** The user explicitly decided all columns for a dataset go in one call (or chunked batches). Never call the API once per column -- it wastes tokens on repeated system prompts and costs 10-50x more.
- **Storing field descriptions in a separate table:** The `columns` table already exists with the right granularity. Adding a `field_enrichments` table would duplicate the dataset_id+column_name key and require an extra JOIN everywhere. Use `columns.ai_description` instead.
- **Hardcoding Miami-Dade in field enrichment prompts:** The whole point of the tech debt fix is to wire `build_system_prompt()` with the dataset's actual jurisdiction. The field enrichment must follow the same pattern.
- **Re-enriching already-enriched columns on every run:** The `--resume` flag must check `columns.ai_description IS NOT NULL` at the dataset level (if ANY column has an ai_description, the dataset has been field-enriched).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured JSON from LLM | JSON parsing + validation | `messages.parse()` with Pydantic `output_format` | Constrained decoding guarantees valid schema; no brittle regex or JSON.loads() |
| Retry with backoff | Manual retry loops | `tenacity` library (already installed) OR single-retry pattern from user decision | Edge cases around jitter, max wait, exception filtering |
| Progress reporting | Print statements | Rich `Progress` bars + `Console` (already in cli.py) | Consistent UX with existing commands |
| Cost estimation | Manual token counting | `client.messages.count_tokens()` API (already used in `estimate_cost()`) | Exact token count from the tokenizer, not approximation |

**Key insight:** This phase is an extension of existing patterns, not a greenfield build. Every architectural decision has a direct precedent in the codebase.

## Common Pitfalls

### Pitfall 1: Token Limit Exceeded on Large Datasets
**What goes wrong:** Datasets with 200+ columns (like the 248-column datasets in the current DB) will exceed the model's context window if all columns are sent in one prompt.
**Why it happens:** The user prompt includes column name, data type, and 3-5 sample values per column. At ~20 tokens per column, 248 columns = ~5000 tokens just for columns, plus system prompt.
**How to avoid:** Implement chunking at ~30 columns per batch as specified in user decisions. Test with the largest datasets first.
**Warning signs:** `anthropic.BadRequestError` with "prompt is too long" message.

### Pitfall 2: Column Name Mismatch Between Prompt and Response
**What goes wrong:** The AI returns field descriptions with slightly different column names (e.g., "Shape_Area" vs "SHAPE_Area"), making it impossible to match descriptions back to columns.
**Why it happens:** LLMs may normalize casing or spacing in column names.
**How to avoid:** Include explicit instructions in the prompt: "Return the EXACT column name as provided." Also match by normalized lowercase name as a fallback.
**Warning signs:** Enrichment completes but some columns have no AI description in the database.

### Pitfall 3: Sample Data Not Available
**What goes wrong:** The user decided to include 3-5 sample values per column, but sample data is not currently stored in the `columns` table or fetched during pull.
**Why it happens:** The current field fetcher (`field_fetcher.py`) only gets field metadata (name, type, alias), not sample values. Getting sample data requires querying the actual feature layer data endpoint.
**How to avoid:** Either (a) fetch sample values at enrichment time by querying `{api_endpoint}/query?where=1=1&outFields={field}&resultRecordCount=5&f=json`, or (b) defer sample data to a pre-enrichment step, or (c) treat sample data as best-effort -- include when available, omit when not.
**Warning signs:** Missing `api_endpoint` for some datasets (File Geodatabases return null).

### Pitfall 4: Resume Logic False Positives
**What goes wrong:** A dataset was partially enriched (some columns have ai_description, others don't) due to a chunking failure, but resume logic marks the entire dataset as "already enriched."
**Why it happens:** Checking `ANY column has ai_description` is simpler but misses partial enrichments.
**How to avoid:** Check whether ALL non-system columns have ai_description. If some are missing, re-enrich the missing ones.
**Warning signs:** Datasets with partial field descriptions that never get completed.

### Pitfall 5: upsert_dataset Overwrites ai_description
**What goes wrong:** The `upsert_dataset()` function uses `INSERT OR REPLACE` which replaces the entire row. If `ai_description` is not included in the INSERT, it gets set to NULL.
**Why it happens:** The current `upsert_dataset()` in db.py (line 350-381) does NOT include `ai_description` in its column list.
**How to avoid:** This is actually fine -- `INSERT OR REPLACE` only sets columns listed in the INSERT. Since `ai_description` is NOT in the INSERT column list, SQLite will set it to its DEFAULT (NULL) on replace. This means a re-pull would wipe out `ai_description`. Fix: add `ai_description` preservation logic, either by adding it to the INSERT with a subquery to preserve the existing value, or by switching to an UPDATE for existing rows.
**Warning signs:** Running `pull` after `enrich` causes `ai_description` to disappear.

## Code Examples

### Example 1: New FieldEnrichmentResult Model
```python
# In enrichment/models.py
class FieldDescription(pydantic.BaseModel):
    """AI-generated description for a single dataset column."""
    column_name: str = pydantic.Field(
        description="Exact column name as provided in the input"
    )
    description: str = pydantic.Field(
        description=(
            "Plain-English description of what this column contains, "
            "1-2 sentences, understandable by a non-technical resident"
        )
    )

class FieldEnrichmentResult(pydantic.BaseModel):
    """Structured output for field-level enrichment via Claude API."""
    field_descriptions: list[FieldDescription] = pydantic.Field(
        description="One description per column provided in the input"
    )
```

### Example 2: Field Enrichment Prompt
```python
# In enrichment/prompts.py
FIELD_SYSTEM_PROMPT_TEMPLATE = """\
You are a {jurisdiction_display_name} data librarian helping residents understand \
what each column in a dataset means.

For each column, write a plain-English description (1-2 sentences) that:
- Explains what data the column contains in everyday language
- Notes the unit of measurement if applicable (feet, dollars, dates, etc.)
- Mentions any known coding scheme (e.g., "Y/N", status codes)

Return the EXACT column name as provided -- do not modify capitalization or spacing.

Skip system/infrastructure columns -- they should not appear in your output."""

def build_field_prompt(dataset: dict, columns: list[dict]) -> str:
    """Build the user prompt for field-level enrichment."""
    parts = [f"Dataset: {dataset.get('title', 'Unknown')}"]
    if dataset.get("description"):
        parts.append(f"Dataset description: {dataset['description'][:200]}")
    parts.append("")
    parts.append("Columns to describe:")
    for col in columns:
        line = f"  - {col['name']} ({col.get('data_type', 'unknown')})"
        if col.get("description"):
            line += f" [alias: {col['description']}]"
        # Sample values would go here if available
        if col.get("sample_values"):
            samples = ", ".join(str(v) for v in col["sample_values"][:5])
            line += f" [samples: {samples}]"
        parts.append(line)
    return "\n".join(parts)
```

### Example 3: B+ Eligibility Query
```python
# In db.py
def get_field_eligible_datasets(conn: sqlite3.Connection) -> list[dict]:
    """Get B+ datasets with columns that lack AI descriptions."""
    rows = conn.execute("""
        SELECT d.id, d.title, d.jurisdiction,
               a.letter_grade,
               COUNT(c.id) as total_columns,
               COUNT(CASE WHEN c.ai_description IS NOT NULL THEN 1 END) as enriched_columns
        FROM datasets d
        JOIN audit_scores a ON d.id = a.dataset_id
        JOIN columns c ON d.id = c.dataset_id
        WHERE a.letter_grade IN ('A', 'B')
        GROUP BY d.id
        HAVING COUNT(CASE WHEN c.ai_description IS NULL THEN 1 END) > 0
        ORDER BY d.title
    """).fetchall()
    return [dict(row) for row in rows]
```

### Example 4: Template with AI Badge
```html
<!-- In dataset.html, replacing existing columns table -->
<section class="dataset-section">
    <h2>Columns / Fields</h2>
    {% if dataset.columns %}
    <div class="table-responsive">
        <table class="columns-table">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Description</th>
                </tr>
            </thead>
            <tbody>
                {% for col in dataset.columns %}
                <tr>
                    <td><code>{{ col.name }}</code></td>
                    <td>{{ col.data_type|default('--') }}</td>
                    <td>
                        {% if col.ai_description %}
                        {{ col.ai_description }}
                        <span class="ai-badge" title="AI-generated description">AI</span>
                        {% elif col.description %}
                        {{ col.description }}
                        {% else %}
                        --
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
    <p class="text-muted">Column metadata not available.</p>
    {% endif %}
</section>
```

### Example 5: AI Badge CSS
```css
/* In style.css */
.ai-badge {
    display: inline-block;
    font-size: 0.65rem;
    font-weight: 700;
    padding: 0.1rem 0.35rem;
    margin-left: 0.4rem;
    background: var(--mdc-blue);
    color: var(--mdc-white);
    border-radius: 3px;
    vertical-align: middle;
    letter-spacing: 0.5px;
    opacity: 0.8;
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `SYSTEM_PROMPT` constant (hardcoded Miami-Dade) | `build_system_prompt()` function (jurisdiction-aware) | Phase 8 (v1.1) | Function exists but is not wired into `enrich_dataset()` -- this phase fixes that |
| No `ai_description` on `columns` table | Schema V4 adds `ai_description` column | This phase | Enables per-column AI descriptions without a separate table |
| `insert_enrichment()` only writes to `enrichments` table | Write-through also updates `datasets.ai_description` | This phase | Keeps denormalized column in sync |

**Deprecated/outdated:**
- `get_datasets_by_jurisdiction()` in db.py (line 675): Dead code -- never imported or called anywhere. The `stats` command uses inline SQL instead. Safe to remove.
- `SYSTEM_PROMPT` constant in prompts.py (line 84): Backward-compatibility shim. After wiring `build_system_prompt()` into `enrich_dataset()`, this constant becomes unnecessary but harmless. Can keep for backward compatibility.

## Key Technical Details

### Database Scale (Current)
- 476 datasets (all Miami-Dade currently; Broward and Miami registered but not pulled)
- 6,172 total columns across all datasets
- Average 16.2 columns per dataset
- Largest datasets: 248 columns, 247 columns
- All 476 datasets have enrichments (dataset-level)
- Zero audit scores (audit not yet run on current DB -- must run before field enrichment)

### B+ Eligibility Estimate
B+ threshold is composite score >= 0.75, which maps to letter grade "B" or "A". Until `mdc-encyclopedia audit` is run, zero datasets qualify. After audit, eligibility depends on data quality distribution. Based on typical ArcGIS Hub data quality, expect 30-60% of datasets to score B+ (roughly 140-280 datasets, ~2,200-4,500 columns to enrich).

### Cost Estimation
Using claude-haiku-4-5 at $1.00/MTok input, $5.00/MTok output:
- Average prompt per dataset (system + user with ~16 columns): ~800 input tokens
- Average output per dataset (~16 field descriptions): ~400 output tokens
- For 200 eligible datasets: ~160K input tokens ($0.16) + ~80K output tokens ($0.40) = ~$0.56
- Worst case (280 datasets, some chunked): ~$1.00-2.00
- Well within the auto-proceed $5 threshold.

### Sample Data Fetching (Decision Needed at Planning Time)
The user decided to include 3-5 sample values per column. This data is NOT currently available:
- `columns` table has: name, data_type, description (alias)
- No sample values are stored
- Options:
  1. **Fetch at enrichment time** (recommended): Query `{api_endpoint}/query?where=1=1&outFields=*&resultRecordCount=5&f=json` for each dataset before enrichment. This adds one HTTP request per dataset but gives real data.
  2. **Skip sample data for v1.1**: Enrich without samples, add in v1.2. Reduces complexity but produces lower-quality descriptions.
  3. **Store samples in DB**: Add a `sample_values` column to the `columns` table. Increases DB size but enables re-use.

Recommendation: Fetch at enrichment time (option 1) since it requires no schema changes for sample storage and the HTTP call is a one-time cost per dataset. Cache-friendly because we already have `api_endpoint` stored for each dataset.

### System Column Skip List (Recommended)
Based on ArcGIS REST API standard fields:
```
OBJECTID, FID, Shape, Shape_Length, Shape_Area,
GlobalID, SHAPE, SHAPE_Length, SHAPE_Area,
Shape__Length, Shape__Area, GDB_GEOMATTR_DATA,
OBJECTID_1, Shape_Leng
```
These are infrastructure columns that exist on every ArcGIS feature layer and have no semantic meaning for residents.

## Open Questions

1. **Sample data availability for non-API datasets**
   - What we know: Datasets with `api_endpoint = NULL` (File Geodatabases) cannot be queried for sample values.
   - What's unclear: How many B+ datasets have null API endpoints?
   - Recommendation: Skip sample data for those datasets; enrich with name/type/alias only. Log a warning.

2. **upsert_dataset ai_description preservation**
   - What we know: `upsert_dataset()` uses INSERT OR REPLACE which sets all unlisted columns to DEFAULT (NULL). This would wipe `datasets.ai_description` on re-pull.
   - What's unclear: Is this already a problem for the existing dataset-level ai_description? (Answer: yes, it is -- but the V3 migration pre-populated it, and no re-pull has been done since.)
   - Recommendation: Fix `upsert_dataset()` to preserve `ai_description` during re-pull. Either use UPDATE for existing rows or add a subquery to carry forward the existing value.

3. **Field enrichment idempotency across batches**
   - What we know: Large datasets get chunked into ~30-column batches with separate API calls.
   - What's unclear: If a batch fails mid-way, should we save partial results or discard all?
   - Recommendation: Save partial results. Each batch's field descriptions get written to `columns.ai_description` immediately after the API call succeeds (same pattern as `insert_enrichment()` committing per-dataset). Resume will pick up un-enriched columns.

## Sources

### Primary (HIGH confidence)
- `/anthropics/anthropic-sdk-python` via Context7 -- `messages.parse()` structured output with Pydantic models, `count_tokens()` API for cost estimation
- Codebase inspection of all source files in `src/mdc_encyclopedia/` -- architecture patterns, existing enrichment pipeline, database schema, template structure

### Secondary (MEDIUM confidence)
- Database inspection of `~/.local/share/mdc-encyclopedia/mdc_encyclopedia.db` -- scale metrics (476 datasets, 6172 columns, average 16.2 cols/dataset)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new dependencies
- Architecture: HIGH -- direct extension of existing patterns with clear precedents in codebase
- Pitfalls: HIGH -- identified from codebase inspection (token limits with 248-col datasets, column name matching, upsert_dataset preservation)
- Sample data fetching: MEDIUM -- API endpoint availability varies; needs runtime validation

**Research date:** 2026-02-27
**Valid until:** 2026-03-27 (stable domain, no external API changes expected)
