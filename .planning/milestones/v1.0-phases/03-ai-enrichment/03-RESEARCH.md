# Phase 3: AI Enrichment - Research

**Researched:** 2026-02-25
**Domain:** LLM API integration (Anthropic Claude), structured output, CLI cost estimation, resumable batch processing
**Confidence:** HIGH

## Summary

Phase 3 adds AI enrichment to the existing CLI pipeline. The core task is calling the Anthropic Claude API for each unenriched dataset in the SQLite database, generating structured metadata (description, use cases, keywords, department, update frequency, civic relevance), and persisting results to the existing `enrichments` table. The enrichment table already exists in the schema (Phase 1), so this phase focuses on the API client, prompt engineering, cost estimation, CLI wiring, and resume/interruption handling.

The Anthropic Python SDK (`anthropic>=0.80`) provides everything needed: synchronous `client.messages.create()` for single-dataset calls, `client.messages.count_tokens()` for pre-flight cost estimation, `messages.parse()` with Pydantic models for structured output with constrained decoding, and built-in retry with exponential backoff. The SDK handles rate limiting via configurable `max_retries` and the API returns `RateLimitError` (429) which the SDK auto-retries.

**Primary recommendation:** Use `anthropic` SDK with `messages.parse()` + Pydantic model for guaranteed JSON schema compliance. Use Claude Haiku 4.5 ($1/$5 per MTok) as the default model for cost efficiency -- the enrichment task is structured extraction, not creative generation, so Haiku is sufficient. Provide `--model` flag for override.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Mixed audience tone: lead with plain English for non-technical residents, include brief technical note for power users (journalists, developers)
- Descriptions are 2-3 sentences per dataset
- Use cases are 2-3 scenario-based examples per dataset (e.g., "A homeowner checking flood risk before buying")
- Keywords should be terms a resident would search for, not technical field names
- Civic relevance scoring: HIGH = directly affects residents (permits, transit, health, housing, public safety); MEDIUM = useful for understanding Miami-Dade (budget, demographics, environmental); LOW = administrative/internal (IT inventory, employee records)
- Show estimated cost before enrichment begins
- Auto-proceed if estimated cost under $5; prompt Y/N if over $5
- No hard budget cap (catalog is finite ~500 datasets)
- `--dry-run` shows what would be enriched and cost estimate without calling API
- Each dataset marked enriched immediately after successful API call
- `--resume` picks up from first unenriched dataset, no re-enrichment
- Safe to Ctrl+C at any point; no partial/corrupt enrichment records

### Claude's Discretion
- Prompt engineering: exact prompt structure, system message, few-shot examples
- Whether to use one API call per dataset or batch multiple fields
- Rate limiting strategy for Anthropic API
- How to handle datasets with minimal metadata (few columns, no description)
- Progress bar implementation and per-dataset feedback in CLI
- Prompt version tracking schema

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ENRICH-01 | Claude API generates plain-English description for each dataset | Anthropic SDK `messages.parse()` with Pydantic model including `description: str` field; system prompt instructs "county librarian" tone |
| ENRICH-02 | Claude API generates practical use cases | Pydantic model `use_cases: list[str]` field; prompt includes scenario-based example format from locked decisions |
| ENRICH-03 | Claude API generates search keywords a resident would use | Pydantic model `keywords: list[str]` field; prompt constrains to resident-search terms |
| ENRICH-04 | Claude API infers likely owning department | Pydantic model `department: str` field; system prompt includes list of actual MDC departments |
| ENRICH-05 | Claude API infers expected update frequency | Pydantic model `update_frequency: str` field; prompt instructs to use actual data timestamps if available |
| ENRICH-06 | Claude API assigns civic relevance score (HIGH/MEDIUM/LOW) | Pydantic model `civic_relevance: Literal["HIGH", "MEDIUM", "LOW"]` with constrained decoding; criteria from locked decisions |
| ENRICH-07 | `--dry-run` flag shows what would be enriched without API calls | Query unenriched datasets, estimate tokens via `count_tokens()`, compute cost, display table |
| ENRICH-08 | `--resume` flag to continue from where it left off | Default behavior: always query for unenriched datasets; `--resume` is implicit since enriched datasets are marked immediately |
| ENRICH-09 | Cost estimate shown before running, prompts for confirmation | Token counting + model pricing lookup; Rich prompt with `click.confirm()` if over $5 threshold |
| ENRICH-10 | Enrichments stored in separate SQLite table (survives re-pulls) | Already exists: `enrichments` table in schema V1 with `dataset_id UNIQUE`, `prompt_version`, `enriched_at` |
| CLI-05 | `enrich` command runs AI enrichment pipeline | Wire up existing stub in `cli.py` with `--dry-run`, `--resume`, `--model` options |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.80.0 | Anthropic Claude API client | Official SDK; provides `messages.create()`, `messages.parse()`, `messages.count_tokens()`, built-in retry/backoff |
| pydantic | >=2.0 | Structured output schema definition | Required by `messages.parse()` for constrained decoding; already a transitive dependency of anthropic SDK |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | >=1.0 | Load `.env` file for ANTHROPIC_API_KEY | Dev convenience; production uses env vars directly (GitHub Secrets in CI) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `messages.parse()` (structured output) | Raw `messages.create()` + JSON parsing | `parse()` uses constrained decoding (guaranteed schema compliance); raw create requires manual JSON extraction and validation, risks malformed output |
| Claude Haiku 4.5 | Claude Sonnet 4.5 | Sonnet is 3x cost ($3/$15 vs $1/$5 per MTok); enrichment is structured extraction where Haiku quality is sufficient |
| Single call per dataset | Batch API (`messages.batches`) | Batch API gives 50% cost savings but is asynchronous (poll for results); adds complexity for ~500 datasets where serial processing completes in <30 minutes; consider for v2 |
| `anthropic` SDK retry | Custom `tenacity` retry | SDK has built-in retry with configurable `max_retries` (default 2); no need for external retry library on API calls |

**Installation:**
```bash
pip install anthropic>=0.80 python-dotenv>=1.0
```

## Architecture Patterns

### Recommended Project Structure
```
src/mdc_encyclopedia/
├── enrichment/
│   ├── __init__.py
│   ├── client.py         # Anthropic client wrapper, token counting, cost estimation
│   ├── prompts.py         # System prompt, user prompt templates, prompt version constant
│   └── models.py          # Pydantic output model (EnrichmentResult)
├── cli.py                 # Updated: enrich command with --dry-run, --resume, --model
├── db.py                  # Updated: add query/insert helpers for enrichments table
└── ingestion/             # Existing (unchanged)
```

### Pattern 1: Pydantic Structured Output with `messages.parse()`
**What:** Define a Pydantic model for the enrichment output, pass it to `messages.parse()` which uses constrained decoding to guarantee valid JSON matching the schema.
**When to use:** Always for this phase -- every API call should use structured output.
**Example:**
```python
# Source: Anthropic SDK docs, Context7
import pydantic
from typing import Literal

class EnrichmentResult(pydantic.BaseModel):
    """Structured output for dataset enrichment."""
    description: str = pydantic.Field(
        description="2-3 sentence plain-English description of what this dataset contains and why it matters"
    )
    use_cases: list[str] = pydantic.Field(
        description="2-3 scenario-based examples of who would use this and why"
    )
    keywords: list[str] = pydantic.Field(
        description="Search terms a Miami-Dade resident would use to find this dataset"
    )
    department: str = pydantic.Field(
        description="Most likely Miami-Dade County department that owns this dataset"
    )
    update_frequency: str = pydantic.Field(
        description="Expected update frequency (e.g., 'Daily', 'Weekly', 'Monthly', 'Annually', 'As needed')"
    )
    civic_relevance: Literal["HIGH", "MEDIUM", "LOW"] = pydantic.Field(
        description="Civic relevance: HIGH=directly affects residents, MEDIUM=useful for understanding MDC, LOW=administrative/internal"
    )

client = anthropic.Anthropic()
result = client.messages.parse(
    model="claude-haiku-4-5-20241022",
    max_tokens=1024,
    system="You are a helpful Miami-Dade County data librarian...",
    messages=[{"role": "user", "content": prompt}],
    output_format=EnrichmentResult,
)
enrichment = result.parsed_output  # Typed EnrichmentResult
```

### Pattern 2: Pre-flight Cost Estimation with `count_tokens()`
**What:** Before running enrichment, iterate unenriched datasets, build the prompt for each, call `count_tokens()` to sum input tokens, estimate output tokens, compute dollar cost.
**When to use:** For `--dry-run` and pre-confirmation cost display.
**Example:**
```python
# Source: Anthropic SDK docs, Context7
# Note: count_tokens() does NOT call the messages API -- it's a separate lightweight endpoint
count = client.messages.count_tokens(
    model="claude-haiku-4-5-20241022",
    system="You are a helpful Miami-Dade County data librarian...",
    messages=[{"role": "user", "content": prompt_text}],
)
input_tokens = count.input_tokens
# Estimate output tokens based on expected response size (~300-500 tokens per dataset)
estimated_output_tokens = 500
```

### Pattern 3: Atomic Per-Dataset Enrichment (Resume Safety)
**What:** Process one dataset at a time. After a successful API response, immediately INSERT into the enrichments table and COMMIT. This makes Ctrl+C safe -- you either have a complete enrichment or none.
**When to use:** Always. This is the resume mechanism.
**Example:**
```python
# Source: Project architecture decision from CONTEXT.md
for dataset in unenriched_datasets:
    result = call_claude(dataset)     # API call
    insert_enrichment(conn, dataset.id, result)  # INSERT + COMMIT
    # If Ctrl+C happens here, next run skips this dataset (already enriched)
```

### Pattern 4: Prompt Version Tracking
**What:** Store a version string (e.g., "v1.0") with each enrichment record so you can identify which prompt produced which results. Bump version when prompt changes significantly.
**When to use:** Always. The `enrichments.prompt_version` column already exists.
**Example:**
```python
# In prompts.py
PROMPT_VERSION = "v1.0"

# Stored with each enrichment
conn.execute(
    "INSERT INTO enrichments (dataset_id, ..., prompt_version) VALUES (?, ..., ?)",
    (dataset_id, ..., PROMPT_VERSION)
)
```

### Anti-Patterns to Avoid
- **Batching multiple datasets in one prompt:** Each dataset needs its own context (title, description, columns). Stuffing multiple datasets in one prompt makes error handling harder (if one fails, you lose all) and doesn't leverage structured output per-dataset.
- **Async processing for ~500 datasets:** At ~2 seconds per call (rate limit + response time), serial processing takes ~17 minutes. Async adds complexity for marginal time savings given the rate limiting.
- **Caching API responses in memory:** With ~500 datasets, memory is not an issue, but the database IS the cache. If a dataset is in the enrichments table, skip it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON output parsing | Custom regex/string parsing of Claude responses | `messages.parse()` with Pydantic | Constrained decoding guarantees valid JSON; parsing regex is fragile |
| API retry/backoff | Custom retry loops with sleep | `anthropic` SDK built-in retry (`max_retries=5`) | SDK handles 429, 529, connection errors with proper exponential backoff |
| Token counting | Character-based estimation | `client.messages.count_tokens()` | Exact token count from Anthropic's tokenizer; character estimation can be 2-3x off |
| Cost calculation | Hardcoded price constants | Centralized pricing dict with model lookup | Prices change; single source of truth makes updates easy |
| Progress display | Print statements | Rich Progress bar (already in project) | Consistent with Phase 2 CLI patterns; handles terminal width, elapsed time |

**Key insight:** The Anthropic SDK handles the hard parts (retry, token counting, structured output validation). The implementation work is prompt engineering, database queries, and CLI wiring -- all straightforward.

## Common Pitfalls

### Pitfall 1: Missing or Invalid API Key
**What goes wrong:** `AuthenticationError` (401) on first API call; user has no `.env` or `ANTHROPIC_API_KEY` not set.
**Why it happens:** Key is required but easy to forget, especially in a CLI tool that's mostly offline (pull doesn't need it).
**How to avoid:** Check for API key at `enrich` command start, before any work. Print a clear error message with instructions. Use `python-dotenv` to auto-load `.env` file.
**Warning signs:** Error on first dataset, not on subsequent ones.

### Pitfall 2: Enrichment Table Survives Re-Pull but References May Break
**What goes wrong:** After a metadata re-pull, dataset IDs could theoretically change (if the portal reassigns them), orphaning enrichment records.
**Why it happens:** The `enrichments` table uses `dataset_id REFERENCES datasets(id)` but the pull uses `INSERT OR REPLACE` which preserves IDs.
**How to avoid:** ArcGIS Hub dataset IDs are stable UUIDs. The current schema is correct. No action needed, but document the assumption.
**Warning signs:** Enrichment count higher than dataset count after a re-pull.

### Pitfall 3: Token Estimation Inaccuracy for Cost Display
**What goes wrong:** Cost estimate is significantly off because output tokens are estimated, not counted.
**Why it happens:** `count_tokens()` only counts INPUT tokens. Output tokens depend on model response length.
**How to avoid:** Use a conservative output estimate (~500 tokens per dataset based on the expected response structure). Clearly label the estimate as approximate. After enrichment, show actual cost based on `message.usage`.
**Warning signs:** Actual cost is 2x+ the estimate.

### Pitfall 4: Datasets with Minimal Metadata Produce Poor Enrichments
**What goes wrong:** Datasets with only a title and no description/columns get vague, unhelpful AI descriptions.
**Why it happens:** The model has nothing to work with beyond a title like "Table_123".
**How to avoid:** Include column names and types in the prompt (available from the `columns` table). For datasets with truly minimal metadata, include a flag in the prompt asking the model to note that the description is "inferred from limited metadata." Consider a separate `--skip-minimal` flag or quality indicator.
**Warning signs:** All enrichments for sparse datasets say the same generic thing.

### Pitfall 5: Rate Limiting Under Tier 1
**What goes wrong:** Hitting rate limits despite per-request delays, causing retries to cascade.
**Why it happens:** Tier 1 API accounts have lower RPM/TPM limits. The SDK retries on 429 but if you're consistently over the limit, retries pile up.
**How to avoid:** Use a 1-2 second delay between requests (consistent with existing project pattern in `hub_client.py`). Set `max_retries=5` on the client. The serial processing pattern naturally rate-limits.
**Warning signs:** Many 429 errors in logs, enrichment taking much longer than expected.

### Pitfall 6: Structured Output First-Request Latency
**What goes wrong:** First API call with a new schema takes 100-300ms longer than expected.
**Why it happens:** Anthropic compiles the JSON schema into a grammar on the first request; cached for 24 hours after that.
**How to avoid:** Not a real problem -- just be aware. The first call will be slightly slower. Subsequent calls use the cached grammar.
**Warning signs:** First dataset takes noticeably longer than the rest.

## Code Examples

### Complete Enrichment Client Pattern
```python
# Source: Anthropic SDK docs (Context7) + project conventions
import os
import anthropic
import pydantic
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

PROMPT_VERSION = "v1.0"

# Model pricing (USD per million tokens)
MODEL_PRICING = {
    "claude-haiku-4-5-20241022": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
}
DEFAULT_MODEL = "claude-haiku-4-5-20241022"
ESTIMATED_OUTPUT_TOKENS = 500  # Conservative estimate per dataset


class EnrichmentResult(pydantic.BaseModel):
    description: str
    use_cases: list[str]
    keywords: list[str]
    department: str
    update_frequency: str
    civic_relevance: Literal["HIGH", "MEDIUM", "LOW"]


def create_enrichment_client(model: str = DEFAULT_MODEL, max_retries: int = 5):
    """Create Anthropic client configured for enrichment."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not set. Add it to .env or export it."
        )
    return anthropic.Anthropic(api_key=api_key, max_retries=max_retries)


def estimate_cost(client, model, system_prompt, prompts):
    """Estimate total cost for a list of prompts using count_tokens()."""
    total_input = 0
    for prompt_text in prompts:
        count = client.messages.count_tokens(
            model=model,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt_text}],
        )
        total_input += count.input_tokens

    total_output = ESTIMATED_OUTPUT_TOKENS * len(prompts)
    pricing = MODEL_PRICING.get(model, MODEL_PRICING[DEFAULT_MODEL])
    input_cost = (total_input / 1_000_000) * pricing["input"]
    output_cost = (total_output / 1_000_000) * pricing["output"]
    return {
        "input_tokens": total_input,
        "output_tokens_est": total_output,
        "input_cost": input_cost,
        "output_cost_est": output_cost,
        "total_est": input_cost + output_cost,
        "dataset_count": len(prompts),
    }
```

### Building the Dataset Prompt
```python
# Source: Project CONTEXT.md decisions + existing normalizer patterns
import json

SYSTEM_PROMPT = """You are a Miami-Dade County data librarian helping residents understand open datasets.
Write as if explaining to a neighbor — clear, helpful, no bureaucratic jargon.

For each dataset, provide:
- A 2-3 sentence description of what this dataset contains and why it matters to Miami-Dade residents
- 2-3 practical use cases as specific scenarios (e.g., "A homeowner checking flood risk before buying")
- Search keywords a resident would actually type
- The most likely Miami-Dade County department that owns this data
- Expected update frequency based on the data type and any timestamps
- Civic relevance: HIGH (directly affects residents), MEDIUM (useful for understanding MDC), LOW (administrative/internal)

Miami-Dade County departments include: Police, Fire Rescue, Water and Sewer, Transit, Parks and Recreation, Aviation, PortMiami, Public Housing, Regulatory and Economic Resources, Internal Services, Information Technology, Property Appraiser, Elections, Corrections and Rehabilitation, Solid Waste, and others."""


def build_dataset_prompt(dataset: dict, columns: list[dict]) -> str:
    """Build the user prompt for a single dataset."""
    parts = [f"Dataset: {dataset['title']}"]

    if dataset.get("description"):
        parts.append(f"Original description: {dataset['description']}")

    if dataset.get("category"):
        parts.append(f"Category: {dataset['category']}")

    if dataset.get("publisher"):
        parts.append(f"Publisher: {dataset['publisher']}")

    if dataset.get("tags"):
        try:
            tags = json.loads(dataset["tags"])
            if tags:
                parts.append(f"Tags: {', '.join(tags)}")
        except (json.JSONDecodeError, TypeError):
            pass

    if dataset.get("updated_at"):
        parts.append(f"Last updated: {dataset['updated_at']}")

    if dataset.get("created_at"):
        parts.append(f"Created: {dataset['created_at']}")

    if columns:
        col_names = [f"{c['name']} ({c['data_type']})" for c in columns[:30]]
        parts.append(f"Columns ({len(columns)} total): {', '.join(col_names)}")

    return "\n".join(parts)
```

### Database Helpers for Enrichment
```python
# Source: Existing db.py patterns
import sqlite3

def get_unenriched_datasets(conn: sqlite3.Connection) -> list[dict]:
    """Get datasets that have no enrichment record."""
    rows = conn.execute("""
        SELECT d.id, d.title, d.description, d.category, d.publisher,
               d.tags, d.updated_at, d.created_at, d.format
        FROM datasets d
        LEFT JOIN enrichments e ON d.id = e.dataset_id
        WHERE e.id IS NULL
        ORDER BY d.title
    """).fetchall()
    return [dict(row) for row in rows]


def get_columns_for_dataset(conn: sqlite3.Connection, dataset_id: str) -> list[dict]:
    """Get column metadata for a dataset."""
    rows = conn.execute(
        "SELECT name, data_type, description FROM columns WHERE dataset_id = ?",
        (dataset_id,)
    ).fetchall()
    return [dict(row) for row in rows]


def insert_enrichment(
    conn: sqlite3.Connection,
    dataset_id: str,
    result: dict,
    prompt_version: str,
) -> None:
    """Insert an enrichment record. Commits immediately for resume safety."""
    conn.execute(
        """INSERT OR REPLACE INTO enrichments
        (dataset_id, description, use_cases, keywords, department,
         update_freq, civic_relevance, prompt_version, enriched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            dataset_id,
            result["description"],
            json.dumps(result["use_cases"]),
            json.dumps(result["keywords"]),
            result["department"],
            result["update_frequency"],
            result["civic_relevance"],
            prompt_version,
        ),
    )
    conn.commit()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `messages.create()` + manual JSON parsing | `messages.parse()` with Pydantic + constrained decoding | Late 2025 | Guaranteed schema compliance; no more JSON parse failures |
| Character-based token estimation | `messages.count_tokens()` API endpoint | 2025 | Exact input token count from Anthropic tokenizer |
| Instructor library for structured output | Native SDK `messages.parse()` | 2025 | No external dependency needed; native constrained decoding |
| Claude 3.5 Haiku | Claude Haiku 4.5 | October 2024 | Same pricing, better quality for structured tasks |

**Deprecated/outdated:**
- `instructor` library: Was the go-to for structured output before native SDK support. Still works but adds unnecessary dependency now that `messages.parse()` exists natively.
- `response_model` parameter: Some older tutorials reference this; the current SDK uses `output_format`.

## Open Questions

1. **Exact model ID string for Haiku 4.5**
   - What we know: Pricing is $1/$5 per MTok. Context7 examples use `"claude-haiku-4-5-20241022"` but model IDs can change.
   - What's unclear: Whether Anthropic has released a newer Haiku 4.5 snapshot since October 2024.
   - Recommendation: Use `"claude-haiku-4-5-20241022"` as default; the `--model` flag allows override. Verify at implementation time with `anthropic` SDK model list.

2. **`count_tokens()` rate limits**
   - What we know: It's a separate endpoint from messages. It's lightweight.
   - What's unclear: Whether counting tokens for 500 prompts in rapid succession hits rate limits.
   - Recommendation: Add a small delay (0.1s) between count_tokens calls for dry-run. If rate-limited, fall back to character-based estimation (4 chars per token).

3. **Prompt iteration on real data**
   - What we know: STATE.md notes "Enrichment prompt structure needs iteration on 15-20 real datasets before full-catalog run."
   - What's unclear: Exact prompt quality until tested against real Miami-Dade datasets.
   - Recommendation: Implement a `--limit N` flag for test runs on small batches. First run should be `--limit 20` to review quality before full catalog.

## Sources

### Primary (HIGH confidence)
- Context7 `/anthropics/anthropic-sdk-python` - `messages.create()`, `messages.parse()`, `count_tokens()`, error handling, retry configuration (queried 2026-02-25)
- [Anthropic SDK Python on PyPI](https://pypi.org/project/anthropic/) - Version 0.80.0 (latest as of 2026-02-17)
- [Structured outputs - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) - Constrained decoding, Pydantic integration, schema compilation caching

### Secondary (MEDIUM confidence)
- [Anthropic Pricing](https://platform.claude.com/docs/en/about-claude/pricing) - Haiku 4.5: $1/$5, Sonnet 4.5: $3/$15 per MTok (verified via official docs)
- [Rate limits - Claude API Docs](https://docs.anthropic.com/en/api/rate-limits) - Token bucket algorithm, tier-based limits, Retry-After headers

### Tertiary (LOW confidence)
- Schema compilation 100-300ms overhead for first request: reported in multiple web sources, plausible but not measured

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Anthropic SDK is official, well-documented, verified via Context7
- Architecture: HIGH - Patterns follow existing project conventions (serial processing, Rich progress, SQLite persistence)
- Pitfalls: HIGH - Based on SDK documentation for error types and project-specific schema analysis
- Cost estimation: MEDIUM - Token counting API is verified; output token estimation is inherently approximate

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (stable domain; SDK version may update but patterns are stable)
