"""Database initialization and schema management for MDC Open Data Encyclopedia."""

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
