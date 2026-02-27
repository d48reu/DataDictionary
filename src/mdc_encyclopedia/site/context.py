"""Query helpers that read from SQLite and build template-ready dicts."""

import json
import logging
from datetime import datetime, timezone

from slugify import slugify

logger = logging.getLogger(__name__)


def build_site_data(conn) -> dict:
    """Master function returning all data needed for all pages.

    Performs a LEFT JOIN across datasets, enrichments, and audit_scores
    to get all data in one pass. Also queries columns and changes tables.

    Args:
        conn: An open sqlite3.Connection with row_factory=sqlite3.Row.

    Returns:
        Dict with keys: datasets, categories, stats, changes,
        quality_summary, generated_at.
    """
    # Master query: datasets + enrichments + audit_scores
    rows = conn.execute(
        """
        SELECT d.*,
               e.description AS ai_description,
               e.use_cases,
               e.keywords,
               e.department,
               e.update_freq,
               e.civic_relevance,
               a.composite_score,
               a.letter_grade,
               a.staleness AS freshness_score,
               a.completeness,
               a.documentation,
               a.findings_json
        FROM datasets d
        LEFT JOIN enrichments e ON d.id = e.dataset_id
        LEFT JOIN audit_scores a ON d.id = a.dataset_id
        ORDER BY d.title
        """
    ).fetchall()

    # Build column lookup: dataset_id -> list of column dicts
    col_rows = conn.execute(
        "SELECT dataset_id, name, data_type, description FROM columns"
    ).fetchall()
    columns_by_dataset = {}
    for col in col_rows:
        ds_id = col["dataset_id"]
        if ds_id not in columns_by_dataset:
            columns_by_dataset[ds_id] = []
        columns_by_dataset[ds_id].append(dict(col))

    # Build dataset contexts with slug collision detection
    seen_slugs = {}
    all_datasets = []

    for row in rows:
        ds = _build_dataset_context(row, columns_by_dataset)
        # Slug collision detection
        base_slug = ds["slug"]
        if base_slug in seen_slugs:
            ds_id = ds["id"]
            ds["slug"] = f"{base_slug}-{ds_id[:8]}"
            logger.warning(
                "Slug collision for '%s' -- disambiguated to '%s'",
                base_slug,
                ds["slug"],
            )
        seen_slugs[ds["slug"]] = ds["id"]
        all_datasets.append(ds)

    # Build related datasets for each
    for ds in all_datasets:
        ds["related"] = _build_related_datasets(ds, all_datasets)

    # Group by category
    categories = {}
    for ds in all_datasets:
        cat = ds.get("category") or "Uncategorized"
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(ds)

    # Stats
    total_datasets = len(all_datasets)
    described_count = sum(
        1 for ds in all_datasets if ds.get("ai_description")
    )
    pct_described = (
        round(described_count / total_datasets * 100, 1)
        if total_datasets > 0
        else 0
    )

    # New this week: count of 'added' changes detected in the last 7 days
    now = datetime.now(timezone.utc)
    seven_days_ago = now.strftime("%Y-%m-%d")
    new_this_week_rows = conn.execute(
        "SELECT COUNT(*) as cnt FROM changes "
        "WHERE change_type = 'added' AND detected_at >= date('now', '-7 days')"
    ).fetchone()
    new_this_week = new_this_week_rows["cnt"] if new_this_week_rows else 0

    stats = {
        "total_datasets": total_datasets,
        "pct_described": pct_described,
        "new_this_week": new_this_week,
    }

    # Changes
    change_rows = conn.execute(
        """
        SELECT c.*, d.title AS dataset_title, d.jurisdiction
        FROM changes c
        LEFT JOIN datasets d ON c.dataset_id = d.id
        ORDER BY c.detected_at DESC
        """
    ).fetchall()
    changes = [dict(r) for r in change_rows]

    # Quality summary: grade distribution, findings, dimension averages, counts
    from collections import Counter

    grade_rows = conn.execute(
        "SELECT letter_grade, COUNT(*) as cnt "
        "FROM audit_scores GROUP BY letter_grade ORDER BY letter_grade"
    ).fetchall()
    grade_distribution = {r["letter_grade"]: r["cnt"] for r in grade_rows}

    # Top findings across all audit scores
    findings_rows = conn.execute(
        "SELECT findings_json FROM audit_scores WHERE findings_json IS NOT NULL"
    ).fetchall()

    findings_counter = Counter()
    for fr in findings_rows:
        try:
            findings_list = json.loads(fr["findings_json"])
            for finding in findings_list:
                findings_counter[finding] += 1
        except (json.JSONDecodeError, TypeError):
            pass
    top_findings = findings_counter.most_common(10)

    # Dimension averages and below-threshold counts
    audit_rows = conn.execute(
        "SELECT composite_score, staleness, completeness, documentation "
        "FROM audit_scores"
    ).fetchall()
    audited_count = len(audit_rows)

    if audited_count > 0:
        avg_composite = sum(r["composite_score"] or 0 for r in audit_rows) / audited_count
        avg_score = round(avg_composite * 100)
        avg_freshness = sum(r["staleness"] or 0 for r in audit_rows) / audited_count
        avg_completeness = sum(r["completeness"] or 0 for r in audit_rows) / audited_count
        avg_documentation = sum(r["documentation"] or 0 for r in audit_rows) / audited_count

        # Map score to grade letter
        if avg_score >= 90:
            avg_grade = "A"
        elif avg_score >= 80:
            avg_grade = "B"
        elif avg_score >= 70:
            avg_grade = "C"
        elif avg_score >= 60:
            avg_grade = "D"
        else:
            avg_grade = "F"

        # Count datasets below 0.5 threshold per dimension
        below_freshness = sum(1 for r in audit_rows if (r["staleness"] or 0) < 0.5)
        below_completeness = sum(1 for r in audit_rows if (r["completeness"] or 0) < 0.5)
        below_documentation = sum(1 for r in audit_rows if (r["documentation"] or 0) < 0.5)

        # Stale datasets: freshness below 0.4
        stale_count = sum(1 for r in audit_rows if (r["staleness"] or 0) < 0.4)
    else:
        avg_score = 0
        avg_grade = "N/A"
        avg_freshness = 0
        avg_completeness = 0
        avg_documentation = 0
        below_freshness = 0
        below_completeness = 0
        below_documentation = 0
        stale_count = 0

    quality_summary = {
        "grade_distribution": grade_distribution,
        "top_findings": top_findings,
        "total_datasets": total_datasets,
        "avg_score": avg_score,
        "avg_grade": avg_grade,
        "pct_described": pct_described,
        "stale_count": stale_count,
        "dimension_averages": {
            "freshness": round(avg_freshness, 2),
            "completeness": round(avg_completeness, 2),
            "documentation": round(avg_documentation, 2),
        },
        "below_threshold_freshness": below_freshness,
        "below_threshold_completeness": below_completeness,
        "below_threshold_documentation": below_documentation,
    }

    generated_at = now.strftime("%Y-%m-%d %H:%M UTC")

    return {
        "datasets": all_datasets,
        "categories": categories,
        "stats": stats,
        "changes": changes,
        "quality_summary": quality_summary,
        "generated_at": generated_at,
    }


def _build_dataset_context(row, columns_by_dataset) -> dict:
    """Convert a DB row into a template-ready dict.

    Parses JSON fields (tags, keywords, use_cases, findings_json) into
    Python lists. Computes relative_time, staleness_color, grade_class,
    and slug.

    Args:
        row: A sqlite3.Row from the master JOIN query.
        columns_by_dataset: Dict mapping dataset_id to list of column dicts.

    Returns:
        Template-ready dict with all display fields.
    """
    ds = dict(row)

    # Parse JSON fields
    ds["tags_list"] = _parse_json_field(ds.get("tags"), [])
    ds["keywords_list"] = _parse_json_field(ds.get("keywords"), [])
    ds["use_cases_list"] = _parse_json_field(ds.get("use_cases"), [])
    ds["findings_list"] = _parse_json_field(ds.get("findings_json"), [])

    # Computed display fields
    ds["relative_time"] = _relative_time(ds.get("updated_at"))
    ds["staleness_color"] = _staleness_color(ds.get("freshness_score"))
    ds["grade_css"] = _grade_class(ds.get("letter_grade"))

    # Generate slug from title
    title = ds.get("title") or ds.get("id", "unknown")
    ds["slug"] = slugify(title, max_length=80)

    # Category slug for browse page links
    cat = ds.get("category") or "Uncategorized"
    ds["category_slug"] = slugify(cat)

    # Tags as comma-separated text for browse page data attributes
    ds["tags_text"] = ",".join(ds.get("tags_list", []))

    # Audit dict for quality breakdown section on dataset detail page
    if ds.get("composite_score") is not None:
        ds["audit"] = {
            "freshness_score": ds.get("freshness_score"),
            "completeness_score": ds.get("completeness"),
            "documentation_score": ds.get("documentation"),
            "composite_score": ds.get("composite_score"),
            "letter_grade": ds.get("letter_grade"),
            "findings": ds.get("findings_list", []),
        }
    else:
        ds["audit"] = None

    # Attach columns
    ds["columns"] = columns_by_dataset.get(ds["id"], [])
    ds["column_count"] = len(ds["columns"])

    return ds


def _parse_json_field(value, default):
    """Parse a JSON string field into a Python object, with fallback."""
    if not value:
        return default
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
        return default
    except (json.JSONDecodeError, TypeError):
        # Might be a plain string (e.g., tags as comma-separated)
        if isinstance(value, str) and "," in value:
            return [t.strip() for t in value.split(",") if t.strip()]
        return default


def _build_related_datasets(dataset, all_datasets) -> list:
    """Return top 5 related datasets by category and keyword overlap.

    Scoring: same category = 3 points, each shared keyword = 1 point.

    Args:
        dataset: The target dataset dict.
        all_datasets: List of all dataset dicts.

    Returns:
        List of {title, slug, department, grade} dicts for top 5 related.
    """
    target_cat = dataset.get("category") or ""
    target_keywords = set(dataset.get("keywords_list", []))
    target_id = dataset["id"]

    scored = []
    for other in all_datasets:
        if other["id"] == target_id:
            continue
        score = 0
        other_cat = other.get("category") or ""
        if target_cat and other_cat == target_cat:
            score += 3
        other_keywords = set(other.get("keywords_list", []))
        shared = target_keywords & other_keywords
        score += len(shared)

        if score > 0:
            scored.append((score, other))

    scored.sort(key=lambda x: x[0], reverse=True)
    top5 = scored[:5]

    return [
        {
            "title": ds["title"],
            "slug": ds["slug"],
            "department": ds.get("department"),
            "grade": ds.get("letter_grade"),
            "grade_class": _grade_class(ds.get("letter_grade")),
        }
        for _, ds in top5
    ]


def _relative_time(dt_str) -> str:
    """Convert a datetime string to 'Updated X days ago' format.

    Args:
        dt_str: ISO-format datetime string, or None.

    Returns:
        Human-readable relative time string.
    """
    if not dt_str:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        days = diff.days

        if days < 0:
            return "Updated recently"
        elif days == 0:
            return "Updated today"
        elif days == 1:
            return "Updated yesterday"
        elif days < 30:
            return f"Updated {days} days ago"
        elif days < 365:
            months = days // 30
            return f"Updated {months} month{'s' if months > 1 else ''} ago"
        else:
            years = days // 365
            return f"Updated {years} year{'s' if years > 1 else ''} ago"
    except (ValueError, AttributeError):
        return "Unknown"


def _staleness_color(freshness_score) -> str:
    """Map a freshness score to a color indicator.

    Args:
        freshness_score: Float 0.0-1.0, or None.

    Returns:
        Color string: green, yellow, red, or gray.
    """
    if freshness_score is None:
        return "gray"
    if freshness_score >= 0.7:
        return "green"
    if freshness_score >= 0.4:
        return "yellow"
    return "red"


def _grade_class(letter_grade) -> str:
    """Map a letter grade to a CSS class name.

    Args:
        letter_grade: String A-F, or None.

    Returns:
        CSS class string like 'grade-a'.
    """
    if not letter_grade:
        return "grade-none"
    return f"grade-{letter_grade.lower()}"
