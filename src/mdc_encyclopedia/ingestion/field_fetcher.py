"""ArcGIS REST field metadata fetcher with retry and multi-layer support.

Fetches field definitions from ArcGIS REST Feature Service endpoints for
each dataset in the catalog. Handles multi-layer Feature Services, single
layer endpoints, and gracefully skips File Geodatabases (null service URL).
"""

import logging
import time

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from mdc_encyclopedia.ingestion.normalizer import normalize_field

logger = logging.getLogger(__name__)

RATE_LIMIT_SECONDS = 1.0


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    reraise=True,
)
def fetch_service_info(client: httpx.Client, service_url: str) -> dict:
    """Fetch service metadata from an ArcGIS REST endpoint.

    Calls the service root URL with ?f=json to get service info including
    layer list and/or field definitions. Rate-limited and retried.

    Args:
        client: An httpx.Client instance.
        service_url: The ArcGIS REST Feature Service URL.

    Returns:
        Parsed JSON response from the service endpoint.

    Raises:
        httpx.HTTPStatusError: If the request fails after retries.
        ValueError: If the response is not valid JSON (e.g., HTML error page).
    """
    time.sleep(RATE_LIMIT_SECONDS)
    response = client.get(f"{service_url}?f=json")
    response.raise_for_status()

    # ArcGIS sometimes returns HTML error pages instead of JSON
    content_type = response.headers.get("content-type", "")
    if "html" in content_type.lower() and "json" not in content_type.lower():
        raise ValueError(
            f"Expected JSON but got HTML response from {service_url}"
        )

    try:
        return response.json()
    except Exception as exc:
        raise ValueError(
            f"Failed to parse JSON from {service_url}: {exc}"
        ) from exc


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    reraise=True,
)
def fetch_layer_fields(client: httpx.Client, layer_url: str) -> list[dict]:
    """Fetch field definitions from a specific ArcGIS REST layer endpoint.

    Calls the layer URL with ?f=json to get layer info including field
    definitions. Rate-limited and retried.

    Args:
        client: An httpx.Client instance.
        layer_url: URL to a specific layer (e.g., .../FeatureServer/0).

    Returns:
        List of field dicts from the layer, or empty list if no fields key.
    """
    time.sleep(RATE_LIMIT_SECONDS)
    response = client.get(f"{layer_url}?f=json")
    response.raise_for_status()
    data = response.json()
    return data.get("fields", [])


def fetch_fields_for_dataset(
    client: httpx.Client, dataset_id: str, service_url: str | None
) -> list[dict]:
    """Fetch and normalize all field metadata for a dataset.

    Main entry point for field fetching. Handles three cases:
    1. Null/empty service URL (File Geodatabase) -- returns empty list
    2. URL points to a specific layer (has 'fields' key) -- normalize those
    3. URL points to a service root (has 'layers' key) -- fetch each layer

    Args:
        client: An httpx.Client instance.
        dataset_id: The dataset ID these fields belong to.
        service_url: The ArcGIS REST endpoint URL, or None for File Geodatabases.

    Returns:
        List of normalized field dicts ready for upsert_columns.
        Returns empty list on any error (never crashes the pull).
    """
    if not service_url:
        return []

    try:
        service_info = fetch_service_info(client, service_url)

        # Case 1: URL points directly to a layer (has fields key)
        if "fields" in service_info:
            return [
                normalize_field(field, dataset_id)
                for field in service_info["fields"]
            ]

        # Case 2: URL points to service root with layers list
        all_fields = []
        for layer in service_info.get("layers", []):
            layer_id = layer.get("id")
            layer_name = layer.get("name", "")
            layer_url = f"{service_url}/{layer_id}"
            raw_fields = fetch_layer_fields(client, layer_url)
            for field in raw_fields:
                all_fields.append(
                    normalize_field(field, dataset_id, layer_name)
                )

        return all_fields

    except Exception:
        logger.warning(
            "Failed to fetch fields for dataset %s from %s",
            dataset_id,
            service_url,
            exc_info=True,
        )
        return []
