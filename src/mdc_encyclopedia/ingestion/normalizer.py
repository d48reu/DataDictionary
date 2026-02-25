"""Data normalization for ArcGIS Hub Search API responses.

Converts raw Hub API feature dicts to the schema expected by the datasets
and columns tables. Handles HTML stripping, timestamp conversion, category
parsing, and ArcGIS field type mapping.
"""

import html
import json
import re
from datetime import datetime, timezone

# Map ArcGIS field types to simplified type names for the columns table.
ESRI_TYPE_MAP = {
    "esriFieldTypeOID": "integer",
    "esriFieldTypeInteger": "integer",
    "esriFieldTypeSmallInteger": "integer",
    "esriFieldTypeDouble": "number",
    "esriFieldTypeSingle": "number",
    "esriFieldTypeString": "text",
    "esriFieldTypeDate": "date",
    "esriFieldTypeGeometry": "geometry",
    "esriFieldTypeGlobalID": "text",
    "esriFieldTypeGUID": "text",
    "esriFieldTypeBlob": "binary",
    "esriFieldTypeXML": "text",
}


def strip_html(text: str | None) -> str:
    """Strip HTML tags and decode HTML entities from text.

    Args:
        text: Input string that may contain HTML tags and entities.

    Returns:
        Clean plain text with tags removed and entities decoded.
        Empty string if input is None or empty.
    """
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", "", text)
    cleaned = html.unescape(cleaned)
    return cleaned.strip()


def ms_to_iso(ms_timestamp: int | None) -> str | None:
    """Convert a millisecond Unix timestamp to an ISO 8601 string.

    Args:
        ms_timestamp: Unix timestamp in milliseconds (e.g., 1614732032000).

    Returns:
        ISO 8601 formatted string in UTC, or None if input is None.
    """
    if ms_timestamp is None:
        return None
    return datetime.fromtimestamp(ms_timestamp / 1000, tz=timezone.utc).isoformat()


def normalize_hub_dataset(feature: dict) -> dict:
    """Convert an ArcGIS Hub Search API feature to a datasets table row.

    Maps Hub API response fields to the normalized schema, stripping HTML
    from descriptions, converting timestamps from milliseconds to ISO 8601,
    parsing categories, and serializing lists/dicts as JSON strings.

    Args:
        feature: A single feature dict from the Hub Search API response
                 (element of the 'features' array in the GeoJSON FeatureCollection).

    Returns:
        Dict matching the datasets table columns, ready for upsert_dataset.
    """
    props = feature.get("properties", {})

    # Parse categories: "/Categories/Source Department/Police" -> "Police"
    category = None
    for cat in props.get("categories", []):
        parts = cat.split("/")
        if len(parts) >= 3 and parts[1] == "Categories":
            category = parts[-1]
            break

    # Determine download URL based on dataset type
    ds_type = props.get("type", "")
    feature_id = feature.get("id", "")
    if ds_type == "Feature Service":
        download_url = (
            f"https://opendata.miamidade.gov/api/download/v1/items/{feature_id}/csv?layers=0"
        )
    else:
        download_url = None

    return {
        "id": feature_id,
        "source_portal": "arcgis_hub",
        "source_url": f"https://opendata.miamidade.gov/datasets/{feature_id}",
        "title": props.get("title"),
        "description": strip_html(props.get("description", "")),
        "category": category,
        "publisher": props.get("source", props.get("owner", "")),
        "format": ds_type,
        "created_at": ms_to_iso(props.get("created")),
        "updated_at": ms_to_iso(props.get("modified")),
        "row_count": None,  # Not available from search API
        "tags": json.dumps(props.get("tags", [])),
        "license": strip_html(props.get("licenseInfo", "")),
        "api_endpoint": props.get("url"),
        "bbox": json.dumps(feature.get("geometry")) if feature.get("geometry") else None,
        "download_url": download_url,
        "metadata_json": json.dumps(props),
    }


def normalize_field(
    field: dict, dataset_id: str, layer_name: str = ""
) -> dict:
    """Convert an ArcGIS REST field definition to a columns table row.

    Maps ArcGIS field types to simplified type names via ESRI_TYPE_MAP.
    Falls back to the raw type string if no mapping exists.

    Args:
        field: A field dict from the ArcGIS REST layer endpoint
               (element of the 'fields' array).
        dataset_id: The dataset ID this field belongs to.
        layer_name: Optional layer name to prepend to the field alias
                    (useful for multi-layer Feature Services).

    Returns:
        Dict matching the columns table schema, ready for upsert_columns.
    """
    raw_type = field.get("type", "")
    data_type = ESRI_TYPE_MAP.get(raw_type, raw_type)

    alias = field.get("alias", "")
    if layer_name and alias:
        description = f"{layer_name}: {alias}"
    else:
        description = alias

    return {
        "dataset_id": dataset_id,
        "name": field.get("name", ""),
        "data_type": data_type,
        "description": description,
    }
