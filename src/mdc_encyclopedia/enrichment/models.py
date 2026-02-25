"""Pydantic models and constants for AI enrichment of Miami-Dade datasets."""

from typing import Literal

import pydantic


class EnrichmentResult(pydantic.BaseModel):
    """Structured output for dataset enrichment via Claude API."""

    description: str = pydantic.Field(
        description=(
            "2-3 sentence plain-English description of what this dataset "
            "contains and why it matters to Miami-Dade residents"
        )
    )
    use_cases: list[str] = pydantic.Field(
        description=(
            "2-3 scenario-based examples of who would use this and why"
        )
    )
    keywords: list[str] = pydantic.Field(
        description=(
            "Search terms a Miami-Dade resident would use to find this dataset"
        )
    )
    department: str = pydantic.Field(
        description=(
            "Most likely Miami-Dade County department that owns this dataset"
        )
    )
    update_frequency: str = pydantic.Field(
        description=(
            "Expected update frequency "
            "(e.g., 'Daily', 'Weekly', 'Monthly', 'Annually', 'As needed')"
        )
    )
    civic_relevance: Literal["HIGH", "MEDIUM", "LOW"] = pydantic.Field(
        description=(
            "Civic relevance: HIGH=directly affects residents, "
            "MEDIUM=useful for understanding MDC, LOW=administrative/internal"
        )
    )


# Model pricing in USD per million tokens
MODEL_PRICING = {
    "claude-haiku-4-5-20241022": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
}

# Default model for enrichment (Haiku 4.5 for cost efficiency)
DEFAULT_MODEL = "claude-haiku-4-5-20241022"

# Conservative estimate of output tokens per dataset enrichment
ESTIMATED_OUTPUT_TOKENS = 500
