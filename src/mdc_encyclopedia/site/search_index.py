"""Build Lunr.js-compatible search index from dataset dicts."""

import json
import logging
import os

from lunr import lunr

logger = logging.getLogger(__name__)


def build_search_index(datasets: list[dict], output_dir: str, base_url: str = "") -> dict:
    """Build Lunr.js-compatible search index and write JSON files.

    Creates two files:
      - search-index.json: Serialized Lunr index for client-side search.
      - search-data.json: Metadata keyed by slug for result display.

    Args:
        datasets: List of dataset dicts from build_site_data.
        output_dir: Root output directory for the generated site.

    Returns:
        Dict with index_size (bytes) and data_size (bytes).
    """
    if not datasets:
        # Write empty index files for graceful handling
        index_path = os.path.join(output_dir, "search-index.json")
        data_path = os.path.join(output_dir, "search-data.json")
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump({}, f)
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump({}, f)
        logger.info("No datasets -- wrote empty search index files")
        return {"index_size": 2, "data_size": 2}

    # Build documents list for lunr indexing
    documents = []
    search_data = {}

    for ds in datasets:
        slug = ds.get("slug", "")
        title = ds.get("title", "")
        ai_desc = ds.get("ai_description") or ds.get("description") or ""
        description = ai_desc[:200]
        keywords = " ".join(ds.get("keywords_list", []))
        department = ds.get("department") or ""
        category = ds.get("category") or ""
        jurisdiction = ds.get("jurisdiction_display_name") or ds.get("jurisdiction") or ""

        documents.append(
            {
                "id": slug,
                "title": title,
                "description": description,
                "keywords": keywords,
                "jurisdiction": jurisdiction,
                "department": department,
                "category": category,
            }
        )

        # Build search data for result display
        snippet = ai_desc[:120] or (ds.get("description") or "")[:120]
        search_data[slug] = {
            "title": title,
            "snippet": snippet,
            "department": department,
            "jurisdiction": jurisdiction,
            "url": f"{base_url}/dataset/{slug}/",
            "grade": ds.get("letter_grade") or "",
        }

    # Build lunr index with field boosts
    idx = lunr(
        ref="id",
        fields=[
            {"field_name": "title", "boost": 10},
            {"field_name": "keywords", "boost": 8},
            {"field_name": "jurisdiction", "boost": 5},
            {"field_name": "description", "boost": 5},
            {"field_name": "department", "boost": 3},
            {"field_name": "category", "boost": 3},
        ],
        documents=documents,
    )

    # Serialize and write
    serialized_index = idx.serialize()
    index_json = json.dumps(serialized_index, separators=(",", ":"))
    data_json = json.dumps(search_data, separators=(",", ":"))

    index_path = os.path.join(output_dir, "search-index.json")
    data_path = os.path.join(output_dir, "search-data.json")

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_json)

    with open(data_path, "w", encoding="utf-8") as f:
        f.write(data_json)

    index_size = len(index_json.encode("utf-8"))
    data_size = len(data_json.encode("utf-8"))

    logger.info(
        "Search index: %d docs, index=%dKB, data=%dKB",
        len(documents),
        index_size // 1024,
        data_size // 1024,
    )

    return {"index_size": index_size, "data_size": data_size}
