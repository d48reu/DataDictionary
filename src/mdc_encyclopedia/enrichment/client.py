"""Anthropic client wrapper for AI enrichment of Miami-Dade datasets."""

import logging
import os
import time

import anthropic
import httpx
from dotenv import load_dotenv

from .models import (
    DEFAULT_MODEL,
    ESTIMATED_OUTPUT_TOKENS,
    MODEL_PRICING,
    EnrichmentResult,
    FieldEnrichmentResult,
)
from .prompts import (
    SYSTEM_PROMPT,
    build_dataset_prompt,
    build_field_prompt,
    build_field_system_prompt,
    build_system_prompt,
    is_system_column,
)

logger = logging.getLogger(__name__)


def create_enrichment_client(
    model: str = DEFAULT_MODEL, max_retries: int = 5
) -> anthropic.Anthropic:
    """Create an Anthropic client configured for enrichment.

    Loads environment variables from a .env file, then checks for
    ANTHROPIC_API_KEY. Raises ValueError with a clear message if missing.

    Args:
        model: Model identifier (unused here but available for future use).
        max_retries: Maximum retry attempts for rate-limited requests.

    Returns:
        A configured anthropic.Anthropic client.

    Raises:
        ValueError: If ANTHROPIC_API_KEY is not set.
    """
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not set. "
            "Set it in your environment or add it to a .env file."
        )
    return anthropic.Anthropic(api_key=api_key, max_retries=max_retries)


def enrich_dataset(
    client: anthropic.Anthropic,
    model: str,
    dataset: dict,
    columns: list[dict],
    jurisdiction: str = "Miami-Dade County",
) -> EnrichmentResult:
    """Enrich a single dataset using Claude structured output.

    Builds the user prompt from dataset metadata and columns, then calls
    messages.parse() with the EnrichmentResult Pydantic model for
    guaranteed schema compliance via constrained decoding.

    Args:
        client: An authenticated Anthropic client.
        model: Model identifier (e.g., "claude-haiku-4-5-20241022").
        dataset: Dataset dict with keys: title, description, category, etc.
        columns: List of column dicts with keys: name, data_type, description.
        jurisdiction: Human-readable jurisdiction name for prompt context.

    Returns:
        An EnrichmentResult with all 6 enrichment fields populated.
    """
    prompt = build_dataset_prompt(dataset, columns)
    system_prompt = build_system_prompt(jurisdiction)
    result = client.messages.parse(
        model=model,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
        output_format=EnrichmentResult,
    )
    return result.parsed_output


def estimate_cost(
    client: anthropic.Anthropic,
    model: str,
    datasets: list[dict],
    columns_by_dataset: dict[str, list[dict]],
) -> dict:
    """Estimate the cost of enriching a set of datasets.

    For each dataset, builds the prompt and calls count_tokens() to get
    exact input token counts. Output tokens are estimated at a fixed
    rate per dataset.

    Args:
        client: An authenticated Anthropic client.
        model: Model identifier for pricing lookup.
        datasets: List of dataset dicts (must include "id" key).
        columns_by_dataset: Mapping of dataset_id to column list.

    Returns:
        Dict with keys: input_tokens, output_tokens_est, input_cost,
        output_cost_est, total_est, dataset_count.
    """
    total_input = 0

    for dataset in datasets:
        prompt = build_dataset_prompt(
            dataset, columns_by_dataset.get(dataset["id"], [])
        )
        count = client.messages.count_tokens(
            model=model,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        total_input += count.input_tokens
        # Small delay to avoid rate limiting the token counting endpoint
        time.sleep(0.1)

    total_output = ESTIMATED_OUTPUT_TOKENS * len(datasets)
    pricing = MODEL_PRICING.get(model, MODEL_PRICING[DEFAULT_MODEL])
    input_cost = (total_input / 1_000_000) * pricing["input"]
    output_cost = (total_output / 1_000_000) * pricing["output"]

    return {
        "input_tokens": total_input,
        "output_tokens_est": total_output,
        "input_cost": input_cost,
        "output_cost_est": output_cost,
        "total_est": input_cost + output_cost,
        "dataset_count": len(datasets),
    }


def _fetch_sample_values(
    api_endpoint: str | None, field_names: list[str], count: int = 5
) -> dict[str, list]:
    """Fetch sample values from an ArcGIS REST endpoint (best-effort).

    Queries the feature service for a small number of records and extracts
    attribute values for each requested field.

    Args:
        api_endpoint: Full URL to the ArcGIS feature layer (e.g.,
            'https://services.arcgis.com/.../FeatureServer/0').
            If None, returns empty dict.
        field_names: List of field names to fetch sample values for.
        count: Number of sample records to request (default 5).

    Returns:
        Dict mapping field_name to list of sample values. On any error,
        returns an empty dict.
    """
    if not api_endpoint:
        return {}

    try:
        url = f"{api_endpoint}/query"
        params = {
            "where": "1=1",
            "outFields": ",".join(field_names),
            "resultRecordCount": count,
            "f": "json",
        }
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()

        features = data.get("features", [])
        result: dict[str, list] = {name: [] for name in field_names}
        for feature in features:
            attrs = feature.get("attributes", {})
            for name in field_names:
                val = attrs.get(name)
                if val is not None and val != "":
                    result[name].append(val)

        # Deduplicate and limit to count
        return {
            name: list(dict.fromkeys(vals))[:count]
            for name, vals in result.items()
        }
    except Exception:
        logger.warning(
            "Failed to fetch sample values from %s (best-effort, continuing)",
            api_endpoint,
        )
        return {}


def enrich_fields(
    client: anthropic.Anthropic,
    model: str,
    dataset: dict,
    columns: list[dict],
    batch_size: int = 30,
) -> FieldEnrichmentResult:
    """Enrich field-level descriptions for a dataset using Claude structured output.

    Filters out known ArcGIS system columns, fetches sample values from the
    API endpoint (best-effort), then calls Claude with structured output to
    generate plain-English descriptions for each column.

    If there are more columns than batch_size, the request is chunked into
    multiple API calls and the results are merged.

    Args:
        client: An authenticated Anthropic client.
        model: Model identifier (e.g., "claude-haiku-4-5-20251001").
        dataset: Dataset dict with at least 'title', optionally 'description',
                 'api_endpoint', and 'jurisdiction'.
        columns: List of column dicts with keys: name, data_type; optional:
                 description.
        batch_size: Maximum columns per API call (default 30).

    Returns:
        A FieldEnrichmentResult with descriptions for all non-system columns.
    """
    # Filter out system columns
    non_system_columns = [
        col for col in columns if not is_system_column(col.get("name", ""))
    ]

    if not non_system_columns:
        return FieldEnrichmentResult(field_descriptions=[])

    # Fetch sample values (best-effort)
    field_names = [c["name"] for c in non_system_columns]
    samples = _fetch_sample_values(
        dataset.get("api_endpoint"), field_names
    )

    # Attach sample values to column dicts (copy to avoid mutating originals)
    enriched_columns = []
    for col in non_system_columns:
        col_copy = dict(col)
        col_copy["sample_values"] = samples.get(col["name"], [])
        enriched_columns.append(col_copy)

    # Build system prompt
    jurisdiction = dataset.get("jurisdiction", "Miami-Dade County")
    system_prompt = build_field_system_prompt(jurisdiction)

    # Single call or chunked batches
    if len(enriched_columns) <= batch_size:
        prompt = build_field_prompt(dataset, enriched_columns)
        result = client.messages.parse(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
            output_format=FieldEnrichmentResult,
        )
        return result.parsed_output
    else:
        # Chunk into batches and merge results
        all_descriptions = []
        for i in range(0, len(enriched_columns), batch_size):
            batch = enriched_columns[i : i + batch_size]
            prompt = build_field_prompt(dataset, batch)
            result = client.messages.parse(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                output_format=FieldEnrichmentResult,
            )
            all_descriptions.extend(result.parsed_output.field_descriptions)

        return FieldEnrichmentResult(field_descriptions=all_descriptions)
