"""Prompt templates for AI enrichment of Miami-Dade datasets."""

import json

# Bump this version when the prompt changes significantly.
# Stored with each enrichment record for traceability.
PROMPT_VERSION = "v1.0"

SYSTEM_PROMPT = """\
You are a Miami-Dade County data librarian helping residents understand open datasets.

Write as if explaining to a neighbor -- clear, helpful, no bureaucratic jargon.

For each dataset, provide:
- A 2-3 sentence description of what this dataset contains and why it matters \
to Miami-Dade residents.
- 2-3 practical use cases as specific scenarios (e.g., "A homeowner checking \
flood risk before buying a property").
- Search keywords a resident would actually type to find this data.
- The most likely Miami-Dade County department that owns this data.
- Expected update frequency based on the data type and any timestamps provided.
- Civic relevance score using these criteria:
  HIGH = directly affects residents (permits, transit, health, housing, public safety)
  MEDIUM = useful for understanding Miami-Dade (budget, demographics, environmental data)
  LOW = administrative or internal (IT inventory, employee records, internal workflows)

Miami-Dade County departments include:
Police, Fire Rescue, Water and Sewer, Transit, Parks and Recreation, Aviation, \
PortMiami, Public Housing, Regulatory and Economic Resources, Internal Services, \
Information Technology, Property Appraiser, Elections, Corrections and Rehabilitation, \
Solid Waste, Office of Management and Budget, Community Action and Human Services, \
Animal Services, Medical Examiner, Public Works, Library System, Cultural Affairs, \
and others.

When inferring the department, pick the most specific match from the list above. \
If none fits well, provide your best guess with a brief reason."""


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
