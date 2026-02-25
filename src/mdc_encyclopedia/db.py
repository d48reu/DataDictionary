"""Database initialization and schema management for MDC Open Data Encyclopedia."""

import json
import os
import sqlite3

CURRENT_SCHEMA_VERSION = 1

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,
    source_portal TEXT NOT NULL,
    source_url TEXT,
    title TEXT,
    description TEXT,
    category TEXT,
    publisher TEXT,
    format TEXT,
    created_at TEXT,
    updated_at TEXT,
    row_count INTEGER,
    tags TEXT,
    license TEXT,
    api_endpoint TEXT,
    bbox TEXT,
    download_url TEXT,
    metadata_json TEXT CHECK(json_valid(metadata_json) OR metadata_json IS NULL),
    pulled_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS columns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL REFERENCES datasets(id),
    name TEXT NOT NULL,
    data_type TEXT,
    description TEXT,
    UNIQUE(dataset_id, name)
);

CREATE TABLE IF NOT EXISTS enrichments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL UNIQUE REFERENCES datasets(id),
    description TEXT,
    use_cases TEXT,
    keywords TEXT,
    department TEXT,
    update_freq TEXT,
    civic_relevance TEXT,
    prompt_version TEXT,
    enriched_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL REFERENCES datasets(id),
    composite_score REAL,
    staleness REAL,
    completeness REAL,
    documentation REAL,
    audited_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL,
    change_type TEXT NOT NULL,
    details TEXT,
    detected_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Fallback schema without json_valid CHECK constraint for Python builds
# lacking the JSON1 extension.
SCHEMA_V1_NO_JSON_CHECK = SCHEMA_V1.replace(
    "CHECK(json_valid(metadata_json) OR metadata_json IS NULL)",
    "",
)


def init_db(db_path: str) -> bool:
    """Initialize or upgrade the database schema.

    Creates all tables if the database is new or has an older schema version.
    Uses PRAGMA user_version to track schema version.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        True if the database was newly created, False if it already existed.
    """
    is_new = not os.path.exists(db_path)
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    version = conn.execute("PRAGMA user_version").fetchone()[0]

    if version < 1:
        try:
            conn.executescript(SCHEMA_V1)
        except sqlite3.OperationalError:
            # json_valid() not available -- fall back to schema without CHECK
            conn.executescript(SCHEMA_V1_NO_JSON_CHECK)
        conn.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION}")

    # Future upgrades:
    # if version < 2: _upgrade_to_v2(conn)

    conn.commit()
    conn.close()
    return is_new


def get_connection(db_path: str) -> sqlite3.Connection:
    """Get a database connection with foreign keys enabled and Row factory set.

    The caller is responsible for closing the connection.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        A sqlite3.Connection with foreign_keys=ON and row_factory=sqlite3.Row.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def upsert_dataset(conn: sqlite3.Connection, dataset: dict) -> str:
    """Insert or update a dataset record using INSERT OR REPLACE.

    Checks whether the dataset already exists to report 'new' vs 'updated'.
    Sets pulled_at to the current timestamp on every upsert.

    Args:
        conn: An open sqlite3.Connection (caller manages lifecycle).
        dataset: Dict with keys matching datasets table columns
                 (as produced by normalizer.normalize_hub_dataset).

    Returns:
        "new" if this is a first insert, "updated" if replacing existing row.
    """
    existing = conn.execute(
        "SELECT id FROM datasets WHERE id = ?", (dataset["id"],)
    ).fetchone()

    conn.execute(
        """INSERT OR REPLACE INTO datasets
        (id, source_portal, source_url, title, description, category,
         publisher, format, created_at, updated_at, row_count, tags,
         license, api_endpoint, bbox, download_url, metadata_json, pulled_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            dataset["id"],
            dataset["source_portal"],
            dataset["source_url"],
            dataset["title"],
            dataset["description"],
            dataset["category"],
            dataset["publisher"],
            dataset["format"],
            dataset["created_at"],
            dataset["updated_at"],
            dataset["row_count"],
            dataset["tags"],
            dataset["license"],
            dataset["api_endpoint"],
            dataset["bbox"],
            dataset["download_url"],
            dataset["metadata_json"],
        ),
    )
    conn.commit()

    return "updated" if existing else "new"


def upsert_columns(
    conn: sqlite3.Connection, dataset_id: str, columns: list[dict]
) -> int:
    """Replace all column metadata for a dataset.

    Deletes existing columns for the dataset_id first, then inserts the
    new column definitions. This ensures a clean refresh on every pull.

    Args:
        conn: An open sqlite3.Connection (caller manages lifecycle).
        dataset_id: The dataset ID these columns belong to.
        columns: List of dicts with keys: dataset_id, name, data_type, description
                 (as produced by normalizer.normalize_field).

    Returns:
        Number of columns inserted.
    """
    conn.execute("DELETE FROM columns WHERE dataset_id = ?", (dataset_id,))

    for col in columns:
        conn.execute(
            "INSERT INTO columns (dataset_id, name, data_type, description) VALUES (?, ?, ?, ?)",
            (dataset_id, col["name"], col["data_type"], col["description"]),
        )

    conn.commit()
    return len(columns)


def get_unenriched_datasets(conn: sqlite3.Connection) -> list[dict]:
    """Get datasets that have no enrichment record yet.

    Uses a LEFT JOIN with the enrichments table to find datasets
    that haven't been enriched. Results are ordered by title.

    Args:
        conn: An open sqlite3.Connection with row_factory=sqlite3.Row.

    Returns:
        List of dataset dicts with keys: id, title, description,
        category, publisher, tags, updated_at, created_at, format.
    """
    rows = conn.execute(
        """
        SELECT d.id, d.title, d.description, d.category, d.publisher,
               d.tags, d.updated_at, d.created_at, d.format
        FROM datasets d
        LEFT JOIN enrichments e ON d.id = e.dataset_id
        WHERE e.id IS NULL
        ORDER BY d.title
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_columns_for_dataset(
    conn: sqlite3.Connection, dataset_id: str
) -> list[dict]:
    """Get column metadata for a specific dataset.

    Args:
        conn: An open sqlite3.Connection with row_factory=sqlite3.Row.
        dataset_id: The dataset ID to fetch columns for.

    Returns:
        List of column dicts with keys: name, data_type, description.
    """
    rows = conn.execute(
        "SELECT name, data_type, description FROM columns WHERE dataset_id = ?",
        (dataset_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def insert_enrichment(
    conn: sqlite3.Connection,
    dataset_id: str,
    result: dict,
    prompt_version: str,
) -> None:
    """Insert an enrichment record for a dataset.

    Uses INSERT OR REPLACE to handle re-enrichment. The use_cases and
    keywords fields are JSON-serialized. Commits immediately after insert
    for resume safety -- each dataset is marked enriched as soon as the
    API call succeeds.

    Args:
        conn: An open sqlite3.Connection (caller manages lifecycle).
        dataset_id: The dataset ID this enrichment belongs to.
        result: Dict with keys: description, use_cases, keywords,
                department, update_frequency, civic_relevance.
        prompt_version: Version string of the prompt that produced this result.
    """
    conn.execute(
        """INSERT OR REPLACE INTO enrichments
        (dataset_id, description, use_cases, keywords, department,
         update_freq, civic_relevance, prompt_version, enriched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            dataset_id,
            result["description"],
            json.dumps(result["use_cases"]),
            json.dumps(result["keywords"]),
            result["department"],
            result["update_frequency"],
            result["civic_relevance"],
            prompt_version,
        ),
    )
    conn.commit()
