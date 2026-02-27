"""ArcGIS Hub Search API client with pagination, rate limiting, and retry.

Fetches dataset metadata from any ArcGIS Hub portal using the
OGC-compliant Search API. The base URL is parameterized so callers
can target any registered jurisdiction's hub.
"""

import time
from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

DEFAULT_HUB_URL = "https://opendata.miamidade.gov"
SEARCH_ENDPOINT = "/api/search/v1/collections/dataset/items"
PAGE_SIZE = 100
RATE_LIMIT_SECONDS = 1.0


def create_client(base_url: str | None = None) -> httpx.Client:
    """Create an httpx.Client configured for Hub API requests.

    Args:
        base_url: The ArcGIS Hub portal base URL (e.g.,
            'https://opendata.miamidade.gov'). If None, falls back to
            DEFAULT_HUB_URL for backward compatibility.

    Returns:
        A client with a 30-second timeout and standard User-Agent header.
        The caller is responsible for closing the client.
    """
    url = base_url or DEFAULT_HUB_URL
    return httpx.Client(
        base_url=url,
        timeout=30.0,
        headers={"User-Agent": "mdc-encyclopedia/0.1.0"},
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    reraise=True,
)
def fetch_catalog_page(client: httpx.Client, start_index: int = 1) -> dict:
    """Fetch a single page of dataset results from the Hub Search API.

    Rate-limits by sleeping before each request. Retries up to 3 times
    with exponential backoff (2s, 4s, 8s) on failure.

    Args:
        client: An httpx.Client instance (from create_client).
        start_index: 1-based index for pagination.

    Returns:
        Parsed JSON response (GeoJSON FeatureCollection).
    """
    time.sleep(RATE_LIMIT_SECONDS)
    response = client.get(
        SEARCH_ENDPOINT,
        params={"limit": PAGE_SIZE, "startindex": start_index},
    )
    response.raise_for_status()
    return response.json()


def fetch_all_datasets(
    client: httpx.Client,
) -> Iterator[tuple[dict, int, int]]:
    """Paginate through the entire Hub catalog, yielding each dataset feature.

    Follows rel=next links from API responses to get the next page's
    startindex. Stops when no rel=next link is found or features list is empty.

    Yields:
        Tuples of (feature_dict, current_index, total_count) where
        current_index is the 1-based position of this feature in the catalog.
    """
    # First page to get total count
    data = fetch_catalog_page(client, start_index=1)
    total_count = data.get("numberMatched", 0)
    current_index = 0

    while True:
        features = data.get("features", [])
        if not features:
            break

        for feature in features:
            current_index += 1
            yield (feature, current_index, total_count)

        # Follow rel=next link for pagination
        next_start = None
        for link in data.get("links", []):
            if link.get("rel") == "next":
                parsed = urlparse(link["href"])
                qs = parse_qs(parsed.query)
                start_values = qs.get("startindex")
                if start_values:
                    next_start = int(start_values[0])
                break

        if next_start is None:
            break

        data = fetch_catalog_page(client, start_index=next_start)


def detect_duplicate_titles(
    datasets: list[dict],
) -> list[tuple[str, list[str]]]:
    """Detect datasets sharing the same normalized title within the catalog.

    Uses exact match on lowercase stripped titles (per locked decision:
    normalized title matching, no fuzzy). This handles within-catalog
    deduplication since Miami-Dade has only one portal (ArcGIS Hub).

    Args:
        datasets: List of normalized dataset dicts (must have 'title' and 'id').

    Returns:
        List of (normalized_title, [dataset_ids]) for titles appearing more
        than once. Empty list if no duplicates found.
    """
    title_groups: dict[str, list[str]] = {}

    for ds in datasets:
        title = ds.get("title")
        if not title or not title.strip():
            continue
        normalized = title.strip().lower()
        ds_id = ds.get("id", "unknown")
        if normalized not in title_groups:
            title_groups[normalized] = []
        title_groups[normalized].append(ds_id)

    return [
        (title, ids)
        for title, ids in sorted(title_groups.items())
        if len(ids) > 1
    ]
