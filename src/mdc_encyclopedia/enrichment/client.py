"""Anthropic client wrapper for AI enrichment of Miami-Dade datasets."""

import os
import time

import anthropic
from dotenv import load_dotenv

from .models import (
    DEFAULT_MODEL,
    ESTIMATED_OUTPUT_TOKENS,
    MODEL_PRICING,
    EnrichmentResult,
)
from .prompts import SYSTEM_PROMPT, build_dataset_prompt


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

    Returns:
        An EnrichmentResult with all 6 enrichment fields populated.
    """
    prompt = build_dataset_prompt(dataset, columns)
    result = client.messages.parse(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
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
