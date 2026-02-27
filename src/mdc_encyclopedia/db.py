"""Database initialization and schema management for MDC Open Data Encyclopedia."""

import json
import os
import shutil
import sqlite3
from datetime import datetime

CURRENT_SCHEMA_VERSION = 3

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,
    jurisdiction TEXT NOT NULL,
    arcgis_id TEXT NOT NULL,
    source_portal TEXT NOT NULL,
    source_url TEXT,
    title TEXT,
    description TEXT,
    ai_description TEXT,
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
    pulled_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(jurisdiction, arcgis_id)
);

CREATE INDEX IF NOT EXISTS idx_datasets_jurisdiction ON datasets(jurisdiction);
CREATE INDEX IF NOT EXISTS idx_datasets_source_portal ON datasets(source_portal);

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

SCHEMA_V2_UPGRADE = """
-- Recreate audit_scores with letter_grade, findings_json, and UNIQUE(dataset_id)
CREATE TABLE IF NOT EXISTS audit_scores_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL UNIQUE REFERENCES datasets(id),
    composite_score REAL,
    letter_grade TEXT,
    staleness REAL,
    completeness REAL,
    documentation REAL,
    findings_json TEXT,
    audited_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Migrate existing data (if any)
INSERT OR IGNORE INTO audit_scores_new (id, dataset_id, composite_score, staleness, completeness, documentation, audited_at)
    SELECT id, dataset_id, composite_score, staleness, completeness, documentation, audited_at
    FROM audit_scores;

DROP TABLE audit_scores;
ALTER TABLE audit_scores_new RENAME TO audit_scores;
"""

# Fallback schema without json_valid CHECK constraint for Python builds
# lacking the JSON1 extension.
SCHEMA_V1_NO_JSON_CHECK = SCHEMA_V1.replace(
    "CHECK(json_valid(metadata_json) OR metadata_json IS NULL)",
    "",
)


def _backup_database(db_path: str) -> str:
    """Create a timestamped backup of the database before migration.

    Uses shutil.copy2() to preserve file metadata. The backup is placed
    alongside the original file with a timestamp suffix.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Path to the backup file.
    """
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup_path = f"{db_path}.backup-{timestamp}"
    shutil.copy2(db_path, backup_path)
    print(f"Database backed up to: {backup_path}")
    return backup_path


def _migrate_v2_to_v3(conn: sqlite3.Connection, db_path: str) -> None:
    """Migrate database from Schema V2 to V3.

    Implements the create-copy-swap migration pattern:
    1. Create datasets_v3 table with new schema (jurisdiction, arcgis_id, ai_description)
    2. Copy data from datasets with 'miami-dade_' ID prefix and jurisdiction='miami-dade'
    3. Update all child table FK references (columns, enrichments, audit_scores, changes)
    4. Populate ai_description from enrichments.description
    5. Drop old table, rename new table
    6. Create indexes
    7. Verify row counts match

    Args:
        conn: An open sqlite3.Connection.
        db_path: Path to the database file (for logging).

    Raises:
        RuntimeError: If row counts don't match before and after migration,
            or if foreign key check fails.
    """
    # Count rows BEFORE migration
    counts_before = {}
    for table in ["datasets", "columns", "enrichments", "audit_scores", "changes"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        counts_before[table] = count
    print(f"V3 migration: row counts before: {counts_before}")

    # Disable FK checks for migration
    conn.execute("PRAGMA foreign_keys=OFF")

    # Create V3 datasets table
    conn.execute("""
        CREATE TABLE datasets_v3 (
            id TEXT PRIMARY KEY,
            jurisdiction TEXT NOT NULL,
            arcgis_id TEXT NOT NULL,
            source_portal TEXT NOT NULL,
            source_url TEXT,
            title TEXT,
            description TEXT,
            ai_description TEXT,
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
            metadata_json TEXT,
            pulled_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(jurisdiction, arcgis_id)
        )
    """)

    # Migrate existing data with synthetic key prefix
    conn.execute("""
        INSERT INTO datasets_v3
            (id, jurisdiction, arcgis_id, source_portal, source_url, title,
             description, ai_description, category, publisher, format, created_at,
             updated_at, row_count, tags, license, api_endpoint, bbox,
             download_url, metadata_json, pulled_at)
        SELECT
            'miami-dade_' || id, 'miami-dade', id, source_portal, source_url, title,
            description, NULL, category, publisher, format, created_at,
            updated_at, row_count, tags, license, api_endpoint, bbox,
            download_url, metadata_json, pulled_at
        FROM datasets
    """)

    # Update FK references in ALL child tables
    conn.execute("UPDATE columns SET dataset_id = 'miami-dade_' || dataset_id")
    conn.execute("UPDATE enrichments SET dataset_id = 'miami-dade_' || dataset_id")
    conn.execute("UPDATE audit_scores SET dataset_id = 'miami-dade_' || dataset_id")
    conn.execute("UPDATE changes SET dataset_id = 'miami-dade_' || dataset_id")

    # Populate ai_description from enrichments (denormalization)
    conn.execute("""
        UPDATE datasets_v3 SET ai_description = (
            SELECT description FROM enrichments
            WHERE enrichments.dataset_id = datasets_v3.id
        )
    """)

    # Swap tables
    conn.execute("DROP TABLE datasets")
    conn.execute("ALTER TABLE datasets_v3 RENAME TO datasets")

    # Create indexes
    conn.execute("CREATE INDEX idx_datasets_jurisdiction ON datasets(jurisdiction)")
    conn.execute("CREATE INDEX idx_datasets_source_portal ON datasets(source_portal)")

    # Re-enable FK checks
    conn.execute("PRAGMA foreign_keys=ON")

    # Verify FK integrity
    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_violations:
        raise RuntimeError(
            f"Foreign key violations after V3 migration: {fk_violations}"
        )

    # Count rows AFTER migration and verify they match
    counts_after = {}
    for table in ["datasets", "columns", "enrichments", "audit_scores", "changes"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        counts_after[table] = count

    for table in counts_before:
        if counts_before[table] != counts_after[table]:
            raise RuntimeError(
                f"Row count mismatch in '{table}' after V3 migration: "
                f"before={counts_before[table]}, after={counts_after[table]}"
            )

    print(f"V3 migration: row counts after: {counts_after}")
    print("V3 migration complete: all row counts verified")

    # Set schema version
    conn.execute("PRAGMA user_version=3")
    conn.commit()


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
        conn.execute("PRAGMA user_version=1")

    if version < 2:
        conn.executescript(SCHEMA_V2_UPGRADE)
        conn.execute("PRAGMA user_version=2")

    if version < 3:
        # Check if database has existing data that needs migration
        has_data = False
        try:
            row_count = conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]
            has_data = row_count > 0
        except sqlite3.OperationalError:
            # datasets table doesn't exist yet (fresh DB created with V3 schema)
            has_data = False

        if has_data:
            # Existing database with data: backup first, then migrate
            conn.commit()  # commit any pending V2 changes before backup
            _backup_database(db_path)
            _migrate_v2_to_v3(conn, db_path)
        else:
            # Fresh database or empty: already created with V3 schema above
            conn.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION}")

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
        (id, jurisdiction, arcgis_id, source_portal, source_url, title,
         description, category, publisher, format, created_at, updated_at,
         row_count, tags, license, api_endpoint, bbox, download_url,
         metadata_json, pulled_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            dataset["id"],
            dataset.get("jurisdiction", "miami-dade"),
            dataset.get("arcgis_id", dataset["id"]),
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


def get_dataset_ids(conn: sqlite3.Connection) -> set[str]:
    """Get all dataset IDs currently in the database.

    Used for pre/post snapshot comparison during change detection.

    Args:
        conn: An open sqlite3.Connection with row_factory=sqlite3.Row.

    Returns:
        Set of all dataset ID strings.
    """
    rows = conn.execute("SELECT id FROM datasets").fetchall()
    return {row["id"] for row in rows}


def get_columns_snapshot(conn: sqlite3.Connection) -> dict[str, set[str]]:
    """Get column names grouped by dataset_id.

    Builds a mapping from each dataset_id to the set of its column name
    strings. Datasets with no columns will not appear in the dict (treat
    a missing key as an empty set during comparison).

    Args:
        conn: An open sqlite3.Connection with row_factory=sqlite3.Row.

    Returns:
        Dict mapping dataset_id to set of column name strings.
    """
    rows = conn.execute("SELECT dataset_id, name FROM columns").fetchall()
    result: dict[str, set[str]] = {}
    for row in rows:
        ds_id = row["dataset_id"]
        if ds_id not in result:
            result[ds_id] = set()
        result[ds_id].add(row["name"])
    return result


def insert_change(
    conn: sqlite3.Connection,
    dataset_id: str,
    change_type: str,
    details: str | None = None,
    detected_at: str | None = None,
) -> None:
    """Insert a change record into the changes table.

    Does NOT commit -- the caller batches inserts and commits once.

    Args:
        conn: An open sqlite3.Connection (caller manages lifecycle).
        dataset_id: The dataset ID this change applies to.
        change_type: One of 'added', 'removed', 'schema_changed'.
        details: Optional JSON string with change details.
        detected_at: Optional timestamp string. If provided, overrides the
            DEFAULT so all changes from one pull share the same timestamp.
    """
    if detected_at is not None:
        conn.execute(
            "INSERT INTO changes (dataset_id, change_type, details, detected_at) "
            "VALUES (?, ?, ?, ?)",
            (dataset_id, change_type, details, detected_at),
        )
    else:
        conn.execute(
            "INSERT INTO changes (dataset_id, change_type, details) VALUES (?, ?, ?)",
            (dataset_id, change_type, details),
        )


def get_recent_changes(
    conn: sqlite3.Connection, limit: int | None = None
) -> list[dict]:
    """Get change records joined with dataset titles, most recent first.

    Uses LEFT JOIN from changes to datasets so that removed datasets
    (which may still have a row) are included. Results are ordered by
    detected_at DESC, then change_type and dataset_id for deterministic output.

    Args:
        conn: An open sqlite3.Connection with row_factory=sqlite3.Row.
        limit: Optional maximum number of records to return.

    Returns:
        List of dicts with keys: id, dataset_id, change_type, details,
        detected_at, title.
    """
    query = """
        SELECT c.id, c.dataset_id, c.change_type, c.details, c.detected_at,
               d.title
        FROM changes c
        LEFT JOIN datasets d ON c.dataset_id = d.id
        ORDER BY c.detected_at DESC, c.change_type, c.dataset_id
    """
    if limit:
        query += f" LIMIT {limit}"

    rows = conn.execute(query).fetchall()
    return [dict(row) for row in rows]


def get_all_datasets_for_audit(conn: sqlite3.Connection) -> list[dict]:
    """Get all datasets with enrichment and column metadata for audit scoring.

    Joins datasets with enrichments (for update_freq) and computes column
    counts per dataset. Results are ordered by title for deterministic output.

    Args:
        conn: An open sqlite3.Connection with row_factory=sqlite3.Row.

    Returns:
        List of dicts with all dataset fields plus: update_freq (str or None),
        column_count (int), documented_column_count (int).
    """
    rows = conn.execute(
        """
        SELECT d.*,
               e.update_freq,
               COALESCE(col_stats.column_count, 0) AS column_count,
               COALESCE(col_stats.documented_column_count, 0) AS documented_column_count
        FROM datasets d
        LEFT JOIN enrichments e ON d.id = e.dataset_id
        LEFT JOIN (
            SELECT dataset_id,
                   COUNT(*) AS column_count,
                   COUNT(CASE WHEN description IS NOT NULL AND description != '' THEN 1 END) AS documented_column_count
            FROM columns
            GROUP BY dataset_id
        ) col_stats ON d.id = col_stats.dataset_id
        ORDER BY d.title
        """
    ).fetchall()
    return [dict(row) for row in rows]


def upsert_audit_score(
    conn: sqlite3.Connection,
    dataset_id: str,
    composite_score: float,
    letter_grade: str,
    staleness: float,
    completeness: float,
    documentation: float,
    findings_json: str,
) -> None:
    """Insert or replace an audit score record for a dataset.

    Uses INSERT OR REPLACE to ensure only the latest audit per dataset is
    stored. Commits immediately after insert for consistency.

    Args:
        conn: An open sqlite3.Connection (caller manages lifecycle).
        dataset_id: The dataset ID this audit score belongs to.
        composite_score: Weighted composite score (0.0-1.0).
        letter_grade: Letter grade (A-F).
        staleness: Freshness dimension score (0.0-1.0).
        completeness: Completeness dimension score (0.0-1.0).
        documentation: Documentation dimension score (0.0-1.0).
        findings_json: JSON-serialized list of finding strings.
    """
    conn.execute(
        """INSERT OR REPLACE INTO audit_scores
        (dataset_id, composite_score, letter_grade, staleness, completeness,
         documentation, findings_json, audited_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            dataset_id,
            composite_score,
            letter_grade,
            staleness,
            completeness,
            documentation,
            findings_json,
        ),
    )
    conn.commit()


def get_datasets_by_jurisdiction(conn: sqlite3.Connection) -> list[dict]:
    """Get dataset counts grouped by jurisdiction.

    Args:
        conn: An open sqlite3.Connection with row_factory=sqlite3.Row.

    Returns:
        List of dicts with keys: jurisdiction, cnt. Ordered by jurisdiction.
    """
    rows = conn.execute(
        "SELECT jurisdiction, COUNT(*) as cnt "
        "FROM datasets GROUP BY jurisdiction ORDER BY jurisdiction"
    ).fetchall()
    return [dict(row) for row in rows]
