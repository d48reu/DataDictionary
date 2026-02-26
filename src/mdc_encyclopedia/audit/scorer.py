"""Three-dimension quality scoring engine for Miami-Dade open datasets.

Scores each dataset across three dimensions:
- Freshness (staleness): How recently was the dataset updated vs expectations?
- Completeness: How complete is the metadata (description, row count, tags, etc.)?
- Documentation: What percentage of columns have descriptions?

Composite score uses 50/30/20 weighting with N/A dimension weight redistribution.
Letter grades map from composite via A(>=0.90), B(>=0.75), C(>=0.60), D(>=0.40), F(<0.40).
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class DimensionResult:
    """Result from scoring one quality dimension."""

    score: float  # 0.0 (worst) to 1.0 (best)
    findings: list[str] = field(default_factory=list)  # Human-readable findings
    scored: bool = True  # False if dimension couldn't be scored (N/A)


# Maps lowercase frequency strings to expected day intervals between updates.
# Positive int = expected days. -1 = auto-exempt (static/one-time). None = use fallback tiers.
FREQUENCY_DAYS: dict[str, int | None] = {
    "daily": 2,
    "weekly": 14,
    "biweekly": 21,
    "monthly": 45,
    "quarterly": 120,
    "biannually": 210,
    "annually": 400,
    "as needed": None,
    "static": -1,
    "one-time": -1,
}

# Letter grade thresholds: (minimum_score, grade)
GRADE_THRESHOLDS: list[tuple[float, str]] = [
    (0.90, "A"),
    (0.75, "B"),
    (0.60, "C"),
    (0.40, "D"),
    (0.0, "F"),
]


def normalize_frequency(freq_str: str | None) -> int | None:
    """Convert enrichment update_freq string to expected days between updates.

    Tries case-insensitive exact match first, then substring fallback for
    free-text variants like "Updated weekly" or "Every 2 weeks".

    Returns:
        Positive int: expected days between updates.
        -1: auto-exempt from staleness scoring (static/one-time).
        None: no enrichment or unrecognized frequency (use fallback tiers).
    """
    if not freq_str:
        return None

    key = freq_str.strip().lower()

    # Exact match first
    if key in FREQUENCY_DAYS:
        return FREQUENCY_DAYS[key]

    # Substring fallback for free-text variants
    if "daily" in key:
        return FREQUENCY_DAYS["daily"]
    if "week" in key:
        return FREQUENCY_DAYS["weekly"]
    if "biweek" in key or "bi-week" in key:
        return FREQUENCY_DAYS["biweekly"]
    if "month" in key:
        return FREQUENCY_DAYS["monthly"]
    if "quarter" in key:
        return FREQUENCY_DAYS["quarterly"]
    if "biannual" in key or "semi-annual" in key or "semiannual" in key:
        return FREQUENCY_DAYS["biannually"]
    if "annual" in key or "year" in key:
        return FREQUENCY_DAYS["annually"]
    if "static" in key or "one-time" in key or "one time" in key:
        return -1
    if "as needed" in key or "irregular" in key:
        return None

    # Unrecognized -- fall back to fixed tiers
    return None


def score_freshness(
    updated_at: str | None,
    update_freq: str | None,
    now: datetime,
) -> DimensionResult:
    """Score dataset freshness based on update recency vs expected frequency.

    Uses AI-inferred update frequency when available from enrichment.
    Falls back to fixed tiers (90/180/365 days) when no frequency data exists.
    Static/one-time datasets are auto-exempt from staleness scoring.

    Args:
        updated_at: ISO 8601 timestamp of last update, or None.
        update_freq: Enrichment-inferred update frequency string, or None.
        now: Current datetime (injected for testability).

    Returns:
        DimensionResult with freshness score and findings.
    """
    if not updated_at:
        return DimensionResult(
            score=0.0,
            findings=["No last-updated date available"],
            scored=True,
        )

    try:
        last_updated = datetime.fromisoformat(updated_at)
    except ValueError:
        return DimensionResult(
            score=0.0,
            findings=["Invalid date format in updated_at"],
            scored=True,
        )

    # Ensure timezone-aware comparison (assume UTC for naive timestamps)
    if last_updated.tzinfo is None:
        last_updated = last_updated.replace(tzinfo=timezone.utc)

    days_since = (now - last_updated).days
    findings: list[str] = []

    # Check for enrichment-based frequency
    expected_days = normalize_frequency(update_freq)

    if expected_days == -1:
        # Static/one-time: auto-exempt from staleness scoring
        return DimensionResult(
            score=1.0,
            findings=["Static/one-time dataset (exempt)"],
            scored=False,
        )

    if expected_days is not None:
        # AI-inferred frequency available -- ratio-based scoring
        ratio = days_since / expected_days
        if ratio <= 1.0:
            score = 1.0
        elif ratio <= 2.0:
            score = 0.7
            findings.append(
                f"Possibly stale: {days_since} days since update "
                f"(expected every {expected_days} days)"
            )
        elif ratio <= 3.0:
            score = 0.4
            findings.append(
                f"Stale: {days_since} days since update "
                f"(expected every {expected_days} days)"
            )
        else:
            score = 0.1
            findings.append(
                f"Very stale: {days_since} days since update "
                f"(expected every {expected_days} days)"
            )
    else:
        # Fixed fallback tiers (no enrichment frequency available)
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


def score_completeness(dataset: dict) -> DimensionResult:
    """Score metadata completeness across five fields.

    Checks: description quality, row_count availability, tags, category, publisher.
    Each field contributes 0-1 with partial credit for marginal values.

    Args:
        dataset: Dict with dataset metadata fields.

    Returns:
        DimensionResult with completeness score and findings.
    """
    findings: list[str] = []
    passed = 0.0

    # Description check (AUDIT-03)
    desc = dataset.get("description") or ""
    if len(desc) == 0:
        findings.append("Missing description")
    elif len(desc) < 50:
        findings.append(f"Very short description ({len(desc)} chars)")
        passed += 0.3
    elif len(desc) < 100:
        findings.append(f"Brief description ({len(desc)} chars)")
        passed += 0.7
    else:
        passed += 1.0

    # Row count check (AUDIT-02)
    row_count = dataset.get("row_count")
    if row_count is None:
        findings.append("Row count not available")
        passed += 0.3  # Minor penalty -- unavailable is not as bad as 0
    elif row_count == 0:
        findings.append("Empty dataset (0 rows)")
        passed += 0.0
    else:
        passed += 1.0

    # Tags check
    tags = dataset.get("tags")
    if tags and tags != "[]":
        passed += 1.0
    else:
        findings.append("No tags assigned")

    # Category check
    if dataset.get("category"):
        passed += 1.0
    else:
        findings.append("No category assigned")

    # Publisher check
    if dataset.get("publisher"):
        passed += 1.0
    else:
        findings.append("No publisher listed")

    score = passed / 5.0
    return DimensionResult(score=score, findings=findings, scored=True)


def score_documentation(
    column_count: int, documented_count: int
) -> DimensionResult:
    """Score column documentation coverage.

    Measures what ratio of columns have non-empty descriptions.

    Args:
        column_count: Total number of columns for the dataset.
        documented_count: Number of columns with non-empty descriptions.

    Returns:
        DimensionResult with documentation score and findings.
    """
    if column_count == 0:
        return DimensionResult(
            score=0.0,
            findings=["No column metadata available"],
            scored=False,
        )

    ratio = documented_count / column_count

    findings: list[str] = []
    if ratio < 0.25:
        findings.append(
            f"Poor column documentation: {documented_count}/{column_count} "
            f"columns documented ({ratio:.0%})"
        )
    elif ratio < 0.75:
        findings.append(
            f"Partial column documentation: {documented_count}/{column_count} "
            f"columns documented ({ratio:.0%})"
        )

    return DimensionResult(score=ratio, findings=findings, scored=True)


def score_to_grade(score: float) -> str:
    """Convert a 0.0-1.0 composite score to a letter grade.

    Uses GRADE_THRESHOLDS: A(>=0.90), B(>=0.75), C(>=0.60), D(>=0.40), F(<0.40).

    Args:
        score: Composite quality score between 0.0 and 1.0.

    Returns:
        Single letter grade string (A, B, C, D, or F).
    """
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def compute_composite(
    freshness: DimensionResult,
    completeness: DimensionResult,
    documentation: DimensionResult,
) -> tuple[float, str]:
    """Compute weighted composite score with N/A dimension redistribution.

    Base weights: freshness=0.50, completeness=0.30, documentation=0.20.
    Only dimensions where scored=True participate. Weight is redistributed
    proportionally among scored dimensions.

    Args:
        freshness: Freshness dimension result.
        completeness: Completeness dimension result.
        documentation: Documentation dimension result.

    Returns:
        Tuple of (composite_score, letter_grade).
    """
    dimensions = [
        (freshness, 0.50),
        (completeness, 0.30),
        (documentation, 0.20),
    ]

    scored_dims = [(dim, weight) for dim, weight in dimensions if dim.scored]

    if not scored_dims:
        return (0.0, "F")

    # Redistribute weight proportionally among scored dimensions
    total_weight = sum(w for _, w in scored_dims)
    composite = sum(
        dim.score * (weight / total_weight) for dim, weight in scored_dims
    )

    return (composite, score_to_grade(composite))


def audit_dataset(dataset_row: dict, now: datetime) -> dict:
    """Convenience function to fully audit a single dataset.

    Takes a dict from get_all_datasets_for_audit() and produces a complete
    audit result dict ready for upsert_audit_score().

    Args:
        dataset_row: Dict with all dataset fields plus update_freq,
                     column_count, and documented_column_count.
        now: Current datetime (injected for testability).

    Returns:
        Dict with keys: composite_score, letter_grade, staleness,
        completeness, documentation, findings (list of strings).
    """
    freshness_result = score_freshness(
        dataset_row.get("updated_at"),
        dataset_row.get("update_freq"),
        now,
    )

    completeness_result = score_completeness(dataset_row)

    documentation_result = score_documentation(
        dataset_row.get("column_count", 0),
        dataset_row.get("documented_column_count", 0),
    )

    composite_score, letter_grade = compute_composite(
        freshness_result, completeness_result, documentation_result
    )

    # Collect all findings from all dimensions
    all_findings = (
        freshness_result.findings
        + completeness_result.findings
        + documentation_result.findings
    )

    return {
        "composite_score": composite_score,
        "letter_grade": letter_grade,
        "staleness": freshness_result.score,
        "completeness": completeness_result.score,
        "documentation": documentation_result.score,
        "findings": all_findings,
    }
