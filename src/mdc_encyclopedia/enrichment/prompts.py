"""Prompt templates for AI enrichment of open datasets.

Supports jurisdiction-aware prompts via build_system_prompt(). The Miami-Dade
department list is included only when the jurisdiction is Miami-Dade; other
jurisdictions use a generic government reference to avoid incorrect department
assignments.
"""

import json

# Bump this version when the prompt changes significantly.
# Stored with each enrichment record for traceability.
PROMPT_VERSION = "v1.1"

# Department list used only for Miami-Dade County
_MIAMI_DADE_DEPARTMENTS = """\
Miami-Dade County departments include:
Police, Fire Rescue, Water and Sewer, Transit, Parks and Recreation, Aviation, \
PortMiami, Public Housing, Regulatory and Economic Resources, Internal Services, \
Information Technology, Property Appraiser, Elections, Corrections and Rehabilitation, \
Solid Waste, Office of Management and Budget, Community Action and Human Services, \
Animal Services, Medical Examiner, Public Works, Library System, Cultural Affairs, \
and others.

When inferring the department, pick the most specific match from the list above. \
If none fits well, provide your best guess with a brief reason."""

# Generic department guidance for non-Miami-Dade jurisdictions
_GENERIC_DEPARTMENTS = """\
When inferring the department, identify the most likely {jurisdiction_display_name} \
government department or agency that owns this data based on the dataset subject \
matter. Provide your best guess with a brief reason."""

SYSTEM_PROMPT_TEMPLATE = """\
You are a {jurisdiction_display_name} data librarian helping residents understand open datasets.

Write as if explaining to a neighbor -- clear, helpful, no bureaucratic jargon.

For each dataset, provide:
- A 2-3 sentence description of what this dataset contains and why it matters \
to {jurisdiction_display_name} residents.
- 2-3 practical use cases as specific scenarios (e.g., "A homeowner checking \
flood risk before buying a property").
- Search keywords a resident would actually type to find this data.
- The most likely {jurisdiction_display_name} department that owns this data.
- Expected update frequency based on the data type and any timestamps provided.
- Civic relevance score using these criteria:
  HIGH = directly affects residents (permits, transit, health, housing, public safety)
  MEDIUM = useful for understanding {jurisdiction_display_name} (budget, demographics, environmental data)
  LOW = administrative or internal (IT inventory, employee records, internal workflows)

{department_section}"""


def build_system_prompt(jurisdiction_display_name: str = "Miami-Dade County") -> str:
    """Build a jurisdiction-specific system prompt for AI enrichment.

    Uses the Miami-Dade department list when the jurisdiction is Miami-Dade
    County; for all other jurisdictions, uses a generic department inference
    instruction to avoid incorrect department assignments.

    Args:
        jurisdiction_display_name: Human-readable jurisdiction name
            (e.g., 'Miami-Dade County', 'Broward County', 'City of Miami').

    Returns:
        Formatted system prompt string.
    """
    if jurisdiction_display_name == "Miami-Dade County":
        department_section = _MIAMI_DADE_DEPARTMENTS
    else:
        department_section = _GENERIC_DEPARTMENTS.format(
            jurisdiction_display_name=jurisdiction_display_name
        )

    return SYSTEM_PROMPT_TEMPLATE.format(
        jurisdiction_display_name=jurisdiction_display_name,
        department_section=department_section,
    )


# Backward compatibility: existing code that references SYSTEM_PROMPT directly
# still gets the Miami-Dade version.
SYSTEM_PROMPT = build_system_prompt("Miami-Dade County")


def build_dataset_prompt(dataset: dict, columns: list[dict]) -> str:
    """Build the user prompt for enriching a single dataset.

    Assembles all available metadata fields into a structured prompt.
    Handles missing/None fields gracefully by omitting them.
    Truncates columns at 30 entries but notes the total count.

    Args:
        dataset: Dict with keys: title, description, category, publisher,
                 tags, updated_at, created_at, format.
        columns: List of dicts with keys: name, data_type, description.

    Returns:
        A formatted prompt string for the user message.
    """
    parts = [f"Dataset: {dataset.get('title', 'Unknown')}"]

    if dataset.get("description"):
        parts.append(f"Original description: {dataset['description']}")

    if dataset.get("category"):
        parts.append(f"Category: {dataset['category']}")

    if dataset.get("publisher"):
        parts.append(f"Publisher: {dataset['publisher']}")

    if dataset.get("format"):
        parts.append(f"Format: {dataset['format']}")

    if dataset.get("tags"):
        try:
            tags = json.loads(dataset["tags"])
            if isinstance(tags, list) and tags:
                parts.append(f"Tags: {', '.join(str(t) for t in tags)}")
        except (json.JSONDecodeError, TypeError):
            # Tags might be a plain string or malformed JSON
            parts.append(f"Tags: {dataset['tags']}")

    if dataset.get("updated_at"):
        parts.append(f"Last updated: {dataset['updated_at']}")

    if dataset.get("created_at"):
        parts.append(f"Created: {dataset['created_at']}")

    if columns:
        total = len(columns)
        display_cols = columns[:30]
        col_lines = []
        for c in display_cols:
            name = c.get("name", "unknown")
            dtype = c.get("data_type", "unknown")
            desc = c.get("description")
            if desc:
                col_lines.append(f"  - {name} ({dtype}): {desc}")
            else:
                col_lines.append(f"  - {name} ({dtype})")

        header = f"Columns ({total} total)"
        if total > 30:
            header += f" -- showing first 30 of {total}"
        header += ":"
        parts.append(header)
        parts.extend(col_lines)

    return "\n".join(parts)


# ── Field-level enrichment ────────────────────────────────────────────

# ArcGIS system columns that should be excluded from enrichment prompts.
# These are auto-generated by the platform and carry no domain meaning.
SYSTEM_COLUMNS = {
    "OBJECTID", "FID", "Shape", "Shape_Length", "Shape_Area",
    "GlobalID", "SHAPE", "SHAPE_Length", "SHAPE_Area",
    "Shape__Length", "Shape__Area", "GDB_GEOMATTR_DATA",
    "OBJECTID_1", "Shape_Leng",
}

# Pre-compute lowercase set for case-insensitive matching
_SYSTEM_COLUMNS_LOWER = {c.lower() for c in SYSTEM_COLUMNS}


def is_system_column(name: str) -> bool:
    """Check whether a column name is a known ArcGIS system column.

    Matching is case-insensitive so that 'objectid', 'OBJECTID', and
    'ObjectId' all return True.

    Args:
        name: Column name to check.

    Returns:
        True if the column is a system column that should be skipped.
    """
    return name.lower() in _SYSTEM_COLUMNS_LOWER


FIELD_SYSTEM_PROMPT_TEMPLATE = """\
You are a {jurisdiction_display_name} data librarian helping residents \
understand what each column in a dataset means.

For each column, write a plain-English description (1-2 sentences) that:
- Explains what data the column contains in everyday language
- Notes the unit of measurement if applicable (feet, dollars, dates, etc.)
- Mentions any known coding scheme (e.g., "Y/N", status codes)

Return the EXACT column name as provided -- do not modify capitalization \
or spacing."""


def build_field_system_prompt(
    jurisdiction_display_name: str = "Miami-Dade County",
) -> str:
    """Build a jurisdiction-specific system prompt for field enrichment.

    Args:
        jurisdiction_display_name: Human-readable jurisdiction name
            (e.g., 'Miami-Dade County', 'Broward County').

    Returns:
        Formatted system prompt string for field-level enrichment.
    """
    return FIELD_SYSTEM_PROMPT_TEMPLATE.format(
        jurisdiction_display_name=jurisdiction_display_name,
    )


def build_field_prompt(dataset: dict, columns: list[dict]) -> str:
    """Build the user prompt for field-level enrichment of a dataset.

    Includes dataset context (title, truncated description) and a list of
    columns with their type, alias (description field), and sample values
    when available.

    Args:
        dataset: Dict with at least 'title' and optionally 'description'.
        columns: List of dicts with keys: name, data_type; optional keys:
                 description (alias), sample_values (list of values).

    Returns:
        A formatted prompt string for the user message.
    """
    parts = [f"Dataset: {dataset.get('title', 'Unknown')}"]

    desc = dataset.get("description", "")
    if desc:
        # Truncate long descriptions to keep prompt focused
        if len(desc) > 200:
            desc = desc[:200] + "..."
        parts.append(f"Description: {desc}")

    parts.append("")
    parts.append("Columns to describe:")

    for col in columns:
        name = col.get("name", "unknown")
        dtype = col.get("data_type", "unknown")

        line = f"  - {name} ({dtype})"

        alias = col.get("description")
        if alias:
            line += f" [alias: {alias}]"

        samples = col.get("sample_values")
        if samples:
            sample_str = ", ".join(str(s) for s in samples[:5])
            line += f" [samples: {sample_str}]"

        parts.append(line)

    return "\n".join(parts)
