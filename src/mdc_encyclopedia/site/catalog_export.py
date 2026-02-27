"""Catalog export: DCAT-US v1.1 JSON and Excel-compatible CSV generation."""

import csv
import json
import os


def generate_catalog_json(site_data, output_dir):
    """Generate a DCAT-US v1.1 aligned catalog.json file.

    Builds a root catalog object with conformsTo URI and dataset array,
    mapping each dataset to DCAT-US fields with ext_ prefixed AI enrichments.

    Args:
        site_data: Complete site data dict from build_site_data.
        output_dir: Output directory for the generated file.

    Returns:
        Dict with dataset_count and file_size (bytes).
    """
    datasets = site_data.get("datasets", [])

    catalog = {
        "conformsTo": "https://project-open-data.cio.gov/v1.1/schema",
        "@type": "dcat:Catalog",
        "dataset": [_dataset_to_dcat(ds) for ds in datasets],
    }

    output_path = os.path.join(output_dir, "catalog.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    file_size = os.path.getsize(output_path)

    return {
        "dataset_count": len(datasets),
        "file_size": file_size,
    }


def _dataset_to_dcat(ds):
    """Map a dataset dict to a DCAT-US v1.1 entry.

    Required fields are always included. Optional fields and AI enrichment
    extensions are included only when a non-empty value exists (no nulls).

    Args:
        ds: A single dataset dict from site_data["datasets"].

    Returns:
        Dict representing a DCAT-US dataset entry.
    """
    # Required DCAT fields
    entry = {
        "@type": "dcat:Dataset",
        "title": ds.get("title") or "",
        "description": ds.get("ai_description") or ds.get("description") or "",
        "keyword": ds.get("keywords_list") or ds.get("tags_list") or [],
        "modified": ds.get("updated_at") or "",
        "publisher": {
            "@type": "org:Organization",
            "name": ds.get("publisher") or "",
        },
        "identifier": ds.get("id") or "",
    }

    # Optional DCAT fields -- only include when value exists
    _set_if(entry, "license", ds.get("license"))
    _set_if(entry, "spatial", ds.get("bbox"))
    _set_if(entry, "issued", ds.get("created_at"))
    _set_if(entry, "landingPage", ds.get("source_url"))

    category = ds.get("category")
    if category:
        entry["theme"] = [category]

    _set_if(entry, "accrualPeriodicity", ds.get("update_freq"))

    # Distribution array
    distributions = []
    download_url = ds.get("download_url")
    if download_url:
        distributions.append({
            "@type": "dcat:Distribution",
            "downloadURL": download_url,
            "mediaType": "text/csv",
            "format": "CSV",
        })

    api_endpoint = ds.get("api_endpoint")
    if api_endpoint:
        distributions.append({
            "@type": "dcat:Distribution",
            "accessURL": api_endpoint,
            "format": "API",
        })

    if distributions:
        entry["distribution"] = distributions

    # Non-DCAT extension: jurisdiction
    _set_if(entry, "jurisdiction", ds.get("jurisdiction"))

    # AI enrichment extensions with ext_ prefix
    _set_if(entry, "ext_aiDescription", ds.get("ai_description"))
    _set_if(entry, "ext_qualityGrade", ds.get("letter_grade"))
    _set_if(entry, "ext_qualityScore", ds.get("composite_score"))
    _set_if(entry, "ext_civicRelevance", ds.get("civic_relevance"))
    _set_if(entry, "ext_department", ds.get("department"))

    use_cases = ds.get("use_cases_list")
    if use_cases:
        entry["ext_useCases"] = use_cases

    return entry


def _set_if(d, key, value):
    """Set key in dict only if value is truthy (not None, empty string, etc)."""
    if value:
        d[key] = value


# CSV column definitions: (header_name, dataset_key)
CSV_COLUMNS = [
    "ID",
    "Title",
    "Description",
    "Jurisdiction",
    "Category",
    "Publisher",
    "Keywords",
    "Last Modified",
    "Created",
    "Quality Grade",
    "Quality Score",
    "AI Description",
    "Civic Relevance",
    "Department",
    "Use Cases",
    "Format",
    "Source URL",
    "Download URL",
    "API Endpoint",
    "License",
]


def generate_catalog_csv(site_data, output_dir):
    """Generate an Excel-compatible CSV catalog file with UTF-8 BOM.

    Uses explicit column ordering with human-friendly headers.
    Multi-value fields are semicolon-separated.

    Args:
        site_data: Complete site data dict from build_site_data.
        output_dir: Output directory for the generated file.

    Returns:
        Dict with dataset_count and file_size (bytes).
    """
    datasets = site_data.get("datasets", [])

    output_path = os.path.join(output_dir, "catalog.csv")
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for ds in datasets:
            writer.writerow(_flatten_for_csv(ds))

    file_size = os.path.getsize(output_path)

    return {
        "dataset_count": len(datasets),
        "file_size": file_size,
    }


def _flatten_for_csv(ds):
    """Map a dataset dict to a flat row dict with CSV-friendly headers.

    Multi-value fields (keywords, use cases) are joined with semicolons.

    Args:
        ds: A single dataset dict from site_data["datasets"].

    Returns:
        Dict keyed by CSV_COLUMNS header names.
    """
    keywords = ds.get("keywords_list") or ds.get("tags_list") or []
    use_cases = ds.get("use_cases_list") or []

    return {
        "ID": ds.get("id") or "",
        "Title": ds.get("title") or "",
        "Description": ds.get("description") or "",
        "Jurisdiction": ds.get("jurisdiction") or "",
        "Category": ds.get("category") or "",
        "Publisher": ds.get("publisher") or "",
        "Keywords": "; ".join(keywords),
        "Last Modified": ds.get("updated_at") or "",
        "Created": ds.get("created_at") or "",
        "Quality Grade": ds.get("letter_grade") or "",
        "Quality Score": ds.get("composite_score") if ds.get("composite_score") is not None else "",
        "AI Description": ds.get("ai_description") or "",
        "Civic Relevance": ds.get("civic_relevance") or "",
        "Department": ds.get("department") or "",
        "Use Cases": "; ".join(use_cases),
        "Format": ds.get("format") or "",
        "Source URL": ds.get("source_url") or "",
        "Download URL": ds.get("download_url") or "",
        "API Endpoint": ds.get("api_endpoint") or "",
        "License": ds.get("license") or "",
    }
