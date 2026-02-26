# Phase 4: Quality Audit - Research

**Researched:** 2026-02-25
**Domain:** Data quality scoring, SQLite schema extension, CLI audit/stats commands with Rich formatting
**Confidence:** HIGH

## Summary

Phase 4 adds a quality audit system that evaluates every dataset across three dimensions: freshness (staleness), metadata completeness, and column documentation coverage. Each dataset receives a composite quality score mapped to a letter grade (A-F) plus individual audit findings stored as structured data. Two new CLI commands get wired up: `audit` (runs the scoring engine and writes to SQLite) and `stats` (displays a Rich-formatted database summary).

The implementation is entirely local -- no API calls, no external dependencies beyond what's already installed. The audit reads data from the existing `datasets`, `columns`, and `enrichments` tables, computes scores using pure Python logic, and writes results to the existing `audit_scores` table (which needs a schema migration to add `letter_grade TEXT` and a new `audit_findings` table for per-dataset findings). The staleness dimension uses the AI-inferred `update_freq` from the enrichments table when available, falling back to fixed tiers (90/180/365 days) per the user's locked decision.

**Primary recommendation:** Build a single `audit/` module with a `scorer.py` that computes per-dimension scores (0.0-1.0) and a composite weighted score, mapping to letter grades with configurable thresholds. The `stats` command queries aggregate data across all three source tables plus audit results and renders with Rich tables and panels. Schema migration bumps `PRAGMA user_version` to 2.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Letter grades (A-F) for composite quality score
- Freshness-heavy weighting: ~50% freshness, ~30% metadata completeness, ~20% column documentation coverage
- Store both the letter grade AND individual findings per dataset (e.g., "missing description", "stale by 6 months")
- Findings stored in SQLite alongside the score for downstream use by static site (Phase 6)
- When a dimension can't be scored (e.g., no enrichment data for expected frequency), score what's available and note gaps as "N/A" in findings -- do not penalize or assume worst case
- Primary staleness: Use AI-inferred expected update frequency from enrichment (ENRICH-05) when available -- compare last_updated against that expectation
- Fallback staleness (no enrichment): Fixed tiers -- >90 days = possibly stale, >180 days = stale, >365 days = abandoned
- Datasets with AI-inferred frequency of "static" or "one-time" are auto-exempt from staleness scoring
- Empty dataset definition: zero rows reported in metadata OR missing row count entirely -- both flagged
- Government data updates can be slow -- the more lenient 90/180/365 day tiers reflect that reality vs aggressive 30/90/365
- The scoring model should be transparent enough that a resident could understand WHY a dataset got its grade
- Individual findings are important for the static site later (Phase 6 SITE-08 data quality report page)

### Claude's Discretion
- Audit output format and presentation (how `audit` command displays progress and results)
- Stats dashboard layout (how `stats` command organizes the Rich-formatted summary)
- Exact letter grade cutoff thresholds (what numeric score maps to A vs B vs C)
- SQLite schema design for audit_scores and findings tables
- How "poorly described" is defined for AUDIT-03

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUDIT-01 | CLI detects stale datasets (last updated exceeds expected frequency) | Staleness scorer compares `datasets.updated_at` (ISO 8601) against `enrichments.update_freq` when available, else fixed 90/180/365 day tiers. Static/one-time datasets auto-exempt. Uses Python `datetime` diff -- no external deps. |
| AUDIT-02 | CLI flags empty datasets (zero rows or missing data) | Check `datasets.row_count`: if 0 or NULL, flag with finding "empty dataset" or "missing row count". Note: ArcGIS Hub normalizer sets row_count to None, so most datasets will be flagged here -- finding should distinguish "zero rows" from "row count unavailable". |
| AUDIT-03 | CLI flags poorly described datasets (missing or very short descriptions) | Check `datasets.description` length. Recommended threshold: missing/empty = "no description", <50 characters = "very short description", <100 characters = "brief description". These are findings, not automatic failures. |
| AUDIT-04 | Each dataset gets a composite quality score (metadata completeness, freshness, column documentation) | Weighted composite: 50% freshness + 30% completeness + 20% documentation. Each dimension scores 0.0-1.0. Composite maps to letter grade via thresholds. |
| AUDIT-05 | Audit results stored in SQLite audits table | Extend existing `audit_scores` table with `letter_grade TEXT` and `findings_json TEXT`. Schema migration to V2 via existing `PRAGMA user_version` pattern. |
| CLI-04 | `stats` command shows database summary (dataset counts, enrichment status, quality overview) | Rich-formatted output with multiple tables/panels: dataset count per portal, enrichment status (enriched vs pending), quality score distribution (count per letter grade), and aggregate findings summary. |
| CLI-06 | `audit` command runs quality audit | Wire existing `audit` stub in cli.py. Iterate all datasets, compute scores, write to audit_scores table, display Rich progress bar and summary table. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `datetime` | stdlib | Date arithmetic for staleness calculation | No external dependency; ISO 8601 parsing via `datetime.fromisoformat()` (Python 3.7+) handles the existing timestamp format |
| Python `sqlite3` | stdlib | Database access (same as all prior phases) | Existing pattern; row_factory=sqlite3.Row |
| Rich | >=13.0 | Terminal formatting for audit/stats output | Already in project; Table, Panel, Progress, Console |
| rich-click | >=1.8 | CLI framework (same as all prior phases) | Already in project; drop-in Click replacement |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json (stdlib) | stdlib | Serialize/deserialize findings as JSON | Findings stored as JSON text in SQLite column |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom scoring in Python | pandas-based scoring | pandas is a heavy dependency (~50MB) for simple arithmetic that stdlib handles fine |
| JSON findings column | Separate findings table with one row per finding | Normalized table is cleaner for queries but adds schema complexity; JSON column is simpler and findings are always read/written as a batch per dataset |
| PRAGMA user_version migration | Alembic/migration tool | Overkill for single-file SQLite with one schema version jump; existing pattern works |

**Installation:**
```bash
# No new dependencies -- everything already installed
pip install .  # Existing dependencies cover this phase
```

## Architecture Patterns

### Recommended Project Structure
```
src/mdc_encyclopedia/
├── audit/
│   ├── __init__.py
│   └── scorer.py          # Scoring engine: per-dimension scorers, composite, letter grade mapping
├── cli.py                 # Updated: audit command + stats command implementations
├── db.py                  # Updated: schema V2 migration, audit insert/query helpers
├── enrichment/            # Existing (unchanged)
└── ingestion/             # Existing (unchanged)
```

### Pattern 1: Three-Dimension Scoring Engine
**What:** Each quality dimension (freshness, completeness, documentation) has its own scoring function that returns a float 0.0-1.0 plus a list of finding strings. The composite score is a weighted average. The letter grade maps from the composite via threshold cutoffs.
**When to use:** Always -- this is the core of the phase.
**Example:**
```python
# Source: Project architecture patterns
from dataclasses import dataclass

@dataclass
class DimensionResult:
    """Result from scoring one quality dimension."""
    score: float          # 0.0 (worst) to 1.0 (best)
    findings: list[str]   # Human-readable finding strings
    scored: bool          # False if dimension couldn't be scored (N/A)

def score_freshness(dataset: dict, enrichment: dict | None, now: datetime) -> DimensionResult:
    """Score dataset freshness based on update recency vs expected frequency."""
    ...

def score_completeness(dataset: dict) -> DimensionResult:
    """Score metadata completeness: description, row count, tags, category."""
    ...

def score_documentation(dataset: dict, column_count: int, documented_count: int) -> DimensionResult:
    """Score column documentation coverage."""
    ...

def compute_composite(
    freshness: DimensionResult,
    completeness: DimensionResult,
    documentation: DimensionResult,
) -> tuple[float, str]:
    """Weighted composite score and letter grade.

    Weights: freshness=0.50, completeness=0.30, documentation=0.20
    Only scored dimensions participate in weighting (redistributes weight
    when a dimension is N/A).
    """
    ...
```

### Pattern 2: Frequency String Normalization
**What:** The enrichment `update_freq` field contains free-text strings like "Daily", "Weekly", "Monthly", "Annually", "As needed", "Static", "One-time". Normalize these to expected day intervals for staleness comparison.
**When to use:** For AUDIT-01 staleness detection when enrichment data is available.
**Example:**
```python
# Source: Project CONTEXT.md decisions
FREQUENCY_DAYS = {
    "daily": 2,           # 2 day grace period
    "weekly": 14,         # 2 week grace period
    "biweekly": 21,       # 3 week grace period
    "monthly": 45,        # 1.5 month grace period
    "quarterly": 120,     # 4 months grace period
    "biannually": 210,    # 7 months grace period
    "annually": 400,      # ~13 months grace period
    "as needed": None,    # Use fixed fallback tiers
    "static": -1,         # Auto-exempt (sentinel value)
    "one-time": -1,       # Auto-exempt (sentinel value)
}

def normalize_frequency(freq_str: str | None) -> int | None:
    """Convert enrichment update_freq to expected days between updates.

    Returns:
        Positive int: expected days between updates
        -1: auto-exempt from staleness scoring
        None: no enrichment or unrecognized frequency (use fallback tiers)
    """
    if not freq_str:
        return None
    key = freq_str.strip().lower()
    return FREQUENCY_DAYS.get(key)
```

### Pattern 3: Letter Grade Mapping
**What:** Map composite score (0.0-1.0) to letter grade (A-F) using clear cutoff thresholds.
**When to use:** After computing composite score for each dataset.
**Example:**
```python
# Source: Claude's discretion (recommended thresholds)
GRADE_THRESHOLDS = [
    (0.90, "A"),   # Excellent: fresh, complete metadata, documented columns
    (0.75, "B"),   # Good: mostly fresh, decent metadata
    (0.60, "C"),   # Fair: some staleness or gaps
    (0.40, "D"),   # Poor: stale or significant gaps
    (0.0,  "F"),   # Failing: abandoned, empty, or undocumented
]

def score_to_grade(score: float) -> str:
    """Convert a 0.0-1.0 composite score to a letter grade."""
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"
```

### Pattern 4: Schema Migration (V1 -> V2)
**What:** Add `letter_grade` and `findings_json` columns to `audit_scores` table. Use the existing `PRAGMA user_version` pattern for versioning.
**When to use:** Database initialization in `db.py`.
**Example:**
```python
# Source: Existing db.py pattern (01-01-PLAN.md)
SCHEMA_V2_UPGRADE = """
ALTER TABLE audit_scores ADD COLUMN letter_grade TEXT;
ALTER TABLE audit_scores ADD COLUMN findings_json TEXT;
"""

# In init_db():
if version < 2:
    conn.executescript(SCHEMA_V2_UPGRADE)
    conn.execute("PRAGMA user_version=2")
```

### Pattern 5: Stats Command with Rich Dashboard
**What:** Query aggregate statistics from datasets, enrichments, and audit_scores tables. Display using Rich tables and panels.
**When to use:** For the `stats` CLI command.
**Example:**
```python
# Source: Rich docs (Context7), existing cli.py patterns
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns

# Dataset counts per portal
portal_table = Table(title="Datasets by Portal")
portal_table.add_column("Portal", style="bold")
portal_table.add_column("Count", justify="right")
# ... add rows from: SELECT source_portal, COUNT(*) FROM datasets GROUP BY source_portal

# Enrichment status
enrich_table = Table(title="Enrichment Status")
# ... enriched count, pending count

# Quality distribution (if audit has been run)
grade_table = Table(title="Quality Score Distribution")
grade_table.add_column("Grade", style="bold")
grade_table.add_column("Count", justify="right")
grade_table.add_column("Bar")
# ... SELECT letter_grade, COUNT(*) FROM audit_scores GROUP BY letter_grade

console.print(portal_table)
console.print(enrich_table)
console.print(grade_table)
```

### Anti-Patterns to Avoid
- **Penalizing N/A dimensions:** When enrichment data is unavailable (no update_freq), DO NOT give freshness score 0.0. Instead, redistribute weight to scored dimensions and note "freshness: N/A" in findings.
- **Hardcoding "today" in scoring:** Always accept `now` as a parameter to the scoring functions for testability. Use `datetime.now(timezone.utc)` only at the CLI entry point.
- **Storing findings as free-text blob:** Use JSON array of strings in `findings_json`, not a comma-separated string. This preserves structure for Phase 6 site rendering.
- **Running audit without data:** If the database has 0 datasets, the audit command should print a helpful message ("No datasets found. Run `mdc-encyclopedia pull` first.") and exit cleanly, not error.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Date arithmetic | Manual day counting with month/year logic | `datetime.fromisoformat()` + `timedelta` | ISO 8601 parsing and date diff are stdlib and handle leap years, timezone edge cases |
| Terminal dashboard layout | Custom print statements with manual padding | Rich Table + Panel + Console | Already in project; handles terminal width, color, alignment automatically |
| JSON serialization for findings | Custom string concatenation | `json.dumps()` / `json.loads()` | Stdlib; ensures valid JSON, handles escaping |
| Schema migration tracking | Custom migration table | `PRAGMA user_version` | Already established pattern from Phase 1; simple integer versioning |

**Key insight:** This phase has zero external dependencies to add. Everything needed -- date arithmetic, JSON handling, SQLite access, terminal formatting -- is already in the project via stdlib or existing Rich/Click dependencies. The complexity is in the scoring logic design, not the technology.

## Common Pitfalls

### Pitfall 1: ArcGIS Hub row_count Is Always NULL
**What goes wrong:** The normalizer sets `row_count = None` for all ArcGIS Hub datasets because the Hub search API doesn't return record counts. If AUDIT-02 treats NULL as "empty", every dataset gets flagged.
**Why it happens:** The `normalize_hub_dataset()` function in `normalizer.py` hardcodes `"row_count": None` (line 106).
**How to avoid:** Distinguish between "zero rows" (`row_count == 0`) and "row count unavailable" (`row_count IS NULL`). Both get flagged per the user's decision, but with different finding messages: "Empty dataset (0 rows)" vs "Row count not available in metadata". The completeness score should treat NULL row_count as a minor gap, not a zero score.
**Warning signs:** Every dataset gets a "AUDIT-02: empty" flag.

### Pitfall 2: ISO 8601 Timestamp Parsing with Timezone
**What goes wrong:** `datetime.fromisoformat()` on `updated_at` values that include timezone info (e.g., `2024-03-15T10:30:00+00:00`) works in Python 3.11+, but may fail on Python 3.10 for certain formats.
**Why it happens:** Python 3.10 `fromisoformat()` is less forgiving than 3.11+. The project requires `>=3.10`.
**How to avoid:** The normalizer produces timestamps via `datetime.fromtimestamp(...).isoformat()` which gives `2024-03-15T10:30:00+00:00` format. Python 3.11+ handles this fine in `fromisoformat()`. For 3.10 safety, strip the `+00:00` or use a simple regex/replace before parsing if needed. Test on 3.10 if targeting it.
**Warning signs:** `ValueError: Invalid isoformat string` during audit on Python 3.10.

### Pitfall 3: Free-Text Frequency Normalization
**What goes wrong:** The enrichment `update_freq` field is free-text generated by Claude. Values like "Every 2 weeks", "Bi-monthly", "Updated irregularly" don't match the expected normalization keys.
**Why it happens:** Claude's structured output constrains to a `str` type but not to an enum. The model may use varied phrasing.
**How to avoid:** Use case-insensitive substring matching as a fallback: if `"daily"` is in the string, treat as daily; if `"week"` is in the string, treat as weekly; etc. Log unrecognized frequencies as findings and fall back to the fixed-tier staleness check. Consider adding the top unrecognized frequencies to the mapping over time.
**Warning signs:** Many datasets fall through to the fixed-tier fallback despite having enrichment data.

### Pitfall 4: Division by Zero in Composite Score
**What goes wrong:** If all three dimensions return `scored=False` (theoretically possible for a dataset with no enrichment, no description, and no columns), the weighted average has a zero denominator.
**Why it happens:** Extreme edge case: a dataset pulled from the API with essentially no metadata at all.
**How to avoid:** If no dimensions are scorable, assign a default grade of "F" with a finding "Insufficient metadata to score quality" and composite_score 0.0.
**Warning signs:** `ZeroDivisionError` during audit run.

### Pitfall 5: Audit Overwrites vs Appends
**What goes wrong:** Running `audit` twice creates duplicate rows in `audit_scores` because the schema has no UNIQUE constraint on `dataset_id`.
**Why it happens:** The current `audit_scores` table schema uses `id INTEGER PRIMARY KEY AUTOINCREMENT` without a `UNIQUE(dataset_id)` constraint.
**How to avoid:** Use `INSERT OR REPLACE` with a UNIQUE constraint on `dataset_id` (added in schema V2 migration), or `DELETE FROM audit_scores` before each audit run. Recommended: add UNIQUE constraint so the table always holds the latest audit per dataset.
**Warning signs:** `stats` command shows double-counted quality distribution.

## Code Examples

### Freshness Scoring with Enrichment Frequency
```python
# Source: Project decisions from CONTEXT.md + stdlib datetime
from datetime import datetime, timezone, timedelta

def score_freshness(
    updated_at: str | None,
    update_freq: str | None,
    now: datetime,
) -> DimensionResult:
    """Score dataset freshness.

    Uses AI-inferred update frequency when available.
    Falls back to fixed tiers (90/180/365 days).
    Static/one-time datasets are auto-exempt.
    """
    findings = []

    if not updated_at:
        return DimensionResult(score=0.0, findings=["No last-updated date available"], scored=True)

    try:
        last_updated = datetime.fromisoformat(updated_at)
    except ValueError:
        return DimensionResult(score=0.0, findings=["Invalid date format in updated_at"], scored=True)

    # Ensure timezone-aware comparison
    if last_updated.tzinfo is None:
        last_updated = last_updated.replace(tzinfo=timezone.utc)

    days_since = (now - last_updated).days

    # Check for enrichment-based frequency
    expected_days = normalize_frequency(update_freq)

    if expected_days == -1:
        # Static/one-time: auto-exempt
        return DimensionResult(score=1.0, findings=["Static/one-time dataset (exempt from staleness)"], scored=False)

    if expected_days is not None:
        # AI-inferred frequency available
        ratio = days_since / expected_days
        if ratio <= 1.0:
            score = 1.0
        elif ratio <= 2.0:
            score = 0.7
            findings.append(f"Possibly stale: {days_since} days since update (expected every {expected_days} days)")
        elif ratio <= 3.0:
            score = 0.4
            findings.append(f"Stale: {days_since} days since update (expected every {expected_days} days)")
        else:
            score = 0.1
            findings.append(f"Very stale: {days_since} days since update (expected every {expected_days} days)")
    else:
        # Fixed fallback tiers
        if days_since <= 90:
            score = 1.0
        elif days_since <= 180:
            score = 0.6
            findings.append(f"Possibly stale: not updated in {days_since} days")
        elif days_since <= 365:
            score = 0.3
            findings.append(f"Stale: not updated in {days_since} days")
        else:
            score = 0.1
            findings.append(f"Abandoned: not updated in {days_since} days")

    return DimensionResult(score=score, findings=findings, scored=True)
```

### Completeness Scoring
```python
# Source: Project requirements AUDIT-02, AUDIT-03
def score_completeness(dataset: dict) -> DimensionResult:
    """Score metadata completeness: description, row count, tags, category, publisher."""
    findings = []
    checks = 0
    passed = 0

    # Description check (AUDIT-03)
    desc = dataset.get("description") or ""
    checks += 1
    if len(desc) == 0:
        findings.append("Missing description")
    elif len(desc) < 50:
        findings.append(f"Very short description ({len(desc)} chars)")
        passed += 0.3
    elif len(desc) < 100:
        findings.append(f"Brief description ({len(desc)} chars)")
        passed += 0.7
    else:
        passed += 1

    # Row count check (AUDIT-02)
    row_count = dataset.get("row_count")
    checks += 1
    if row_count is None:
        findings.append("Row count not available in metadata")
        passed += 0.3  # Minor penalty -- unavailable is not as bad as 0
    elif row_count == 0:
        findings.append("Empty dataset (0 rows)")
        passed += 0.0
    else:
        passed += 1

    # Tags check
    checks += 1
    tags = dataset.get("tags")
    if tags and tags != "[]":
        passed += 1
    else:
        findings.append("No tags assigned")

    # Category check
    checks += 1
    if dataset.get("category"):
        passed += 1
    else:
        findings.append("No category assigned")

    # Publisher check
    checks += 1
    if dataset.get("publisher"):
        passed += 1
    else:
        findings.append("No publisher listed")

    score = passed / checks if checks > 0 else 0.0
    return DimensionResult(score=score, findings=findings, scored=True)
```

### Documentation Scoring
```python
# Source: Project requirements AUDIT-04 (column documentation)
def score_documentation(column_count: int, documented_count: int) -> DimensionResult:
    """Score column documentation coverage.

    documented_count = columns where description IS NOT NULL AND description != ''
    """
    findings = []

    if column_count == 0:
        findings.append("No column metadata available")
        return DimensionResult(score=0.0, findings=findings, scored=False)

    ratio = documented_count / column_count

    if ratio < 0.25:
        findings.append(f"Poor column documentation: {documented_count}/{column_count} columns documented ({ratio:.0%})")
    elif ratio < 0.75:
        findings.append(f"Partial column documentation: {documented_count}/{column_count} columns documented ({ratio:.0%})")
    # Full documentation: no negative finding

    return DimensionResult(score=ratio, findings=findings, scored=True)
```

### Schema V2 Migration
```python
# Source: Existing db.py pattern from Phase 1
SCHEMA_V2_UPGRADE = """
-- Make audit_scores hold latest audit per dataset (not history)
CREATE TABLE IF NOT EXISTS audit_scores_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL UNIQUE REFERENCES datasets(id),
    composite_score REAL,
    letter_grade TEXT,
    staleness REAL,
    completeness REAL,
    documentation REAL,
    findings_json TEXT,
    audited_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Migrate existing data (if any)
INSERT OR IGNORE INTO audit_scores_new (id, dataset_id, composite_score, staleness, completeness, documentation, audited_at)
    SELECT id, dataset_id, composite_score, staleness, completeness, documentation, audited_at
    FROM audit_scores;

DROP TABLE audit_scores;
ALTER TABLE audit_scores_new RENAME TO audit_scores;
"""
```

### Stats Command Rich Output
```python
# Source: Rich docs (Context7), existing cli.py patterns
from rich.table import Table
from rich.panel import Panel

def render_stats(conn, console):
    """Render database statistics as Rich tables."""
    # Portal counts
    portal_rows = conn.execute(
        "SELECT source_portal, COUNT(*) as cnt FROM datasets GROUP BY source_portal"
    ).fetchall()

    total = conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]

    portal_table = Table(title="Datasets by Portal")
    portal_table.add_column("Portal", style="bold")
    portal_table.add_column("Count", justify="right")
    for row in portal_rows:
        portal_table.add_row(row["source_portal"], str(row["cnt"]))
    portal_table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")

    # Enrichment status
    enriched = conn.execute("SELECT COUNT(*) FROM enrichments").fetchone()[0]
    pending = total - enriched

    enrich_table = Table(title="Enrichment Status")
    enrich_table.add_column("Status", style="bold")
    enrich_table.add_column("Count", justify="right")
    enrich_table.add_row("[green]Enriched[/green]", str(enriched))
    enrich_table.add_row("[yellow]Pending[/yellow]", str(pending))

    # Quality distribution (only if audit has been run)
    audited = conn.execute("SELECT COUNT(*) FROM audit_scores").fetchone()[0]
    if audited > 0:
        grade_rows = conn.execute(
            "SELECT letter_grade, COUNT(*) as cnt FROM audit_scores GROUP BY letter_grade ORDER BY letter_grade"
        ).fetchall()

        grade_table = Table(title="Quality Score Distribution")
        grade_table.add_column("Grade", style="bold")
        grade_table.add_column("Count", justify="right")
        grade_table.add_column("Percentage", justify="right")
        for row in grade_rows:
            pct = f"{row['cnt'] / audited * 100:.1f}%"
            grade_table.add_row(row["letter_grade"], str(row["cnt"]), pct)

    console.print(portal_table)
    console.print(enrich_table)
    if audited > 0:
        console.print(grade_table)
    else:
        console.print(Panel("[yellow]No audit data. Run `mdc-encyclopedia audit` first.[/yellow]", title="Quality Scores"))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom quality frameworks (Great Expectations, dbt tests) | Simple scoring logic in pure Python | N/A | Those tools are for data pipeline testing, not metadata quality scoring -- wrong tool for the job |
| Storing quality scores in separate JSON files | SQLite table alongside source data | Project decision | Single-file database keeps everything queryable together |
| Binary pass/fail quality checks | Graduated 0.0-1.0 scoring with letter grades | Project decision | More nuanced; a dataset can be "mostly good" (B) rather than pass/fail |

**Deprecated/outdated:**
- Great Expectations / dbt tests: Designed for data content validation (column value ranges, null checks on actual data rows). This phase scores metadata quality, not data content -- fundamentally different concern.
- Pandas-based quality profiling (ydata-profiling, etc.): Again targets data content profiling. Massive dependency for a task that's pure metadata arithmetic.

## Open Questions

1. **Exact `update_freq` values from Claude enrichment**
   - What we know: The `EnrichmentResult.update_frequency` field is a free-text string. The prompt suggests "Daily", "Weekly", "Monthly", "Annually", "As needed" but Claude may produce variants.
   - What's unclear: The exact distribution of frequency strings in production data. Fuzzy matching may be needed.
   - Recommendation: Build a normalization function with exact-match keys and substring fallbacks. Log unrecognized frequencies. After first real audit run, review the unrecognized list and expand the mapping. This is a LOW-risk issue -- fallback tiers are always available.

2. **row_count availability from ArcGIS Hub**
   - What we know: The normalizer always sets `row_count = None` because the Hub search API doesn't include record counts. This means AUDIT-02 will flag essentially every dataset for "row count unavailable."
   - What's unclear: Whether this makes the finding meaningless since it applies universally.
   - Recommendation: Still flag it (the finding is factually correct and useful for transparency), but give it a minor completeness penalty (0.3/1.0 rather than 0.0) since it's a metadata availability issue, not a data quality issue. The user's decision says "both flagged" -- honor that.

3. **Python 3.10 compatibility for `datetime.fromisoformat()`**
   - What we know: The project specifies `requires-python = ">=3.10"`. Python 3.10's `fromisoformat()` is less flexible than 3.11+ (doesn't handle all ISO 8601 variants).
   - What's unclear: Whether the exact format produced by `datetime.fromtimestamp(..., tz=timezone.utc).isoformat()` parses correctly on 3.10.
   - Recommendation: Test on 3.10. The format `2024-03-15T10:30:00+00:00` should work on 3.10 since `fromisoformat()` has handled `+00:00` since 3.7. Only the `Z` suffix is problematic on 3.10 -- and the normalizer doesn't produce `Z`.

## Sources

### Primary (HIGH confidence)
- Python stdlib `datetime` documentation - `fromisoformat()`, `timedelta`, timezone handling
- Rich library documentation (Context7 `/websites/rich_readthedocs_io_en_stable`) - Table, Panel, Console formatting patterns
- Project codebase direct inspection - `db.py` schema, `cli.py` stubs, `normalizer.py` date format, `enrichment/models.py` update_frequency field

### Secondary (MEDIUM confidence)
- Python 3.10 `datetime.fromisoformat()` limitations - Known issue with `Z` suffix; documented in Python changelog 3.11

### Tertiary (LOW confidence)
- None -- this phase requires no external research beyond existing codebase and stdlib docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All stdlib and existing project dependencies; no new packages
- Architecture: HIGH - Follows established project patterns (module per concern, db helpers, CLI wiring with Rich)
- Pitfalls: HIGH - Based on direct code inspection of normalizer (row_count=None), date format, and enrichment model (free-text frequency)
- Scoring logic: MEDIUM - Letter grade thresholds and dimension weights are Claude's discretion; recommended values may need tuning after first real audit run

**Research date:** 2026-02-25
**Valid until:** 2026-06-25 (very stable domain; no external APIs or libraries to go stale)
