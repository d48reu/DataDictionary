# Phase 8: Multi-Jurisdiction Foundation - Research

**Researched:** 2026-02-26
**Domain:** Multi-jurisdiction data ingestion, SQLite schema migration, registry-driven configuration
**Confidence:** HIGH

## Summary

Phase 8 transforms the single-portal MDC Encyclopedia into a multi-jurisdiction catalog supporting Miami-Dade County, Broward County, and City of Miami. The core technical challenges are: (1) a Schema V3 migration that introduces a synthetic composite primary key to prevent ID collisions across jurisdictions while preserving all existing enrichment and audit data, (2) a YAML-based jurisdiction registry that maps CLI slugs to ArcGIS Hub portal URLs, and (3) parameterizing the hub client and normalizer to accept any registered portal.

Both target portals have been verified live. Broward County GeoHub (`geohub-bcgis.opendata.arcgis.com`, 83 datasets) and City of Miami DataHub (`datahub-miamigis.opendata.arcgis.com`, 83 datasets) both expose the identical `/api/search/v1/collections/dataset/items` OGC API Records endpoint with the same GeoJSON FeatureCollection response structure as Miami-Dade. The existing pagination, retry, and normalization logic will work across all three portals with only base URL parameterization.

**Primary recommendation:** Use a synthetic composite key (`{jurisdiction}_{arcgis_id}`) as the datasets PRIMARY KEY, keeping it as a single TEXT column so all existing foreign key patterns work unchanged. Migrate existing Miami-Dade records by prefixing their IDs. Use YAML for the jurisdiction registry config file because users will edit it to add future jurisdictions.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Include three jurisdictions in v1.1: Miami-Dade County, Broward County, City of Miami
- City of Miami included if it has a compatible ArcGIS Hub portal (researcher should verify)
- Short CLI slugs: `miami-dade`, `broward`, `miami`
- Full display names: "Miami-Dade County", "Broward County", "City of Miami"
- External config file (YAML or JSON), not hardcoded in Python
- Users can add new ArcGIS Hub jurisdictions by editing the config file without code changes
- Registry maps slug to base URL, display name, and portal type
- Jurisdiction-specific prompts -- swap jurisdiction name into system prompt
- e.g., "Broward County data librarian" instead of generic "South Florida" prompt
- More contextually accurate descriptions per jurisdiction
- Auto-backup the database file before running V3 migration (timestamped copy)
- No dry-run mode -- auto-backup provides the safety net
- Auto-assign `jurisdiction='miami-dade'` to all existing datasets (deterministic -- they all came from opendata.miamidade.gov)
- Auto-migrate on first CLI run after upgrade (same seamless pattern as V1->V2 migration)

### Claude's Discretion
- Composite key design (synthetic PK vs composite TEXT key)
- Config file format choice (YAML vs JSON)
- Hub client refactoring approach
- Pull sequential vs parallel execution
- Progress reporting format for multi-jurisdiction pulls
- Stats command output format and jurisdiction breakdown layout
- Error handling when one jurisdiction's portal is unavailable

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MULTI-01 | Jurisdiction registry mapping slugs to portal base URLs and display names | YAML config file (`jurisdictions.yaml`) with slug, display_name, hub_url, portal_type. New `registry.py` module to load/validate. PyYAML dependency. |
| MULTI-02 | Hub client parameterized to accept base URL for any ArcGIS Hub portal | Verified all 3 portals use identical `/api/search/v1/collections/dataset/items` endpoint. `create_client(base_url)` parameter, normalizer accepts jurisdiction context. |
| MULTI-03 | Schema V3 migration -- synthetic composite key, ai_description column, source_portal index, existing data migration | Synthetic key `{jurisdiction}_{arcgis_id}`, auto-backup, create-copy-swap migration, FK reference updates, ai_description denormalization, UNIQUE(jurisdiction, arcgis_id) constraint. |
| MULTI-04 | CLI `pull --jurisdiction` flag to pull from specific jurisdiction(s) | Click option on pull command, registry lookup, sequential loop over jurisdictions, per-jurisdiction progress bars, continue-on-error for individual jurisdiction failures. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyYAML | >=6.0 | YAML config file parsing | De facto Python YAML library; stable, HIGH reputation (Context7). `yaml.safe_load()` for safe parsing. |
| sqlite3 | stdlib | Database engine | Already in use; no change needed |
| httpx | >=0.28 | HTTP client | Already in use; parameterize base_url |
| tenacity | >=9.0 | Retry with backoff | Already in use for hub_client |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shutil | stdlib | File copy for DB backup | Auto-backup before V3 migration |
| pathlib | stdlib | Path manipulation | Config file discovery |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyYAML (YAML config) | json (JSON config) | JSON has no new dependency but lacks comments and is less human-editable. YAML wins for user-facing config. |
| PyYAML | tomllib/tomli (TOML config) | TOML requires tomli for Python 3.10 (tomllib is 3.11+ stdlib). YAML is more familiar for config files. |
| Synthetic key string | Composite PRIMARY KEY (jurisdiction, arcgis_id) | Composite PK changes every FK reference from single-column to two-column. Synthetic key keeps the existing single-column FK pattern. |

**Installation:**
```bash
pip install pyyaml>=6.0
```

Add to `pyproject.toml` dependencies:
```toml
"pyyaml>=6.0",
```

## Architecture Patterns

### Recommended Project Structure
```
src/mdc_encyclopedia/
├── registry.py              # NEW: jurisdiction registry loader
├── jurisdictions.yaml       # NEW: default jurisdiction config (shipped with package)
├── db.py                    # MODIFIED: Schema V3, backup, migration, jurisdiction queries
├── cli.py                   # MODIFIED: --jurisdiction flag, multi-jurisdiction pull loop, stats breakdown
├── ingestion/
│   ├── hub_client.py        # MODIFIED: parameterized base_url
│   └── normalizer.py        # MODIFIED: jurisdiction-aware ID/URL generation
└── enrichment/
    └── prompts.py           # MODIFIED: jurisdiction-aware system prompt template
```

### Pattern 1: Synthetic Composite Key
**What:** Generate a unique primary key by concatenating `{jurisdiction_slug}_{arcgis_id}` as a single TEXT column. Store `jurisdiction` and `arcgis_id` as separate indexed columns for querying.
**When to use:** When adding a multi-tenancy dimension to an existing single-tenant SQLite schema where foreign keys reference a single PK column.
**Example:**
```python
# In normalizer.py
def normalize_hub_dataset(feature: dict, jurisdiction: str, hub_url: str) -> dict:
    """Normalize a Hub API feature with jurisdiction context."""
    props = feature.get("properties", {})
    arcgis_id = feature.get("id", "")
    synthetic_id = f"{jurisdiction}_{arcgis_id}"

    return {
        "id": synthetic_id,              # PK: 'broward_abc123def456'
        "jurisdiction": jurisdiction,      # 'broward'
        "arcgis_id": arcgis_id,           # 'abc123def456'
        "source_portal": "arcgis_hub",
        "source_url": f"{hub_url}/datasets/{arcgis_id}",
        # ... rest of fields
    }
```

### Pattern 2: Registry-Driven Configuration
**What:** External YAML config file maps jurisdiction slugs to portal metadata. A loader module validates the config and returns typed dicts. Config location follows a priority chain: env var > user data dir > package default.
**When to use:** When users need to add new data sources without code changes.
**Example:**
```yaml
# jurisdictions.yaml
jurisdictions:
  miami-dade:
    display_name: "Miami-Dade County"
    hub_url: "https://opendata.miamidade.gov"
    portal_type: "arcgis_hub"

  broward:
    display_name: "Broward County"
    hub_url: "https://geohub-bcgis.opendata.arcgis.com"
    portal_type: "arcgis_hub"

  miami:
    display_name: "City of Miami"
    hub_url: "https://datahub-miamigis.opendata.arcgis.com"
    portal_type: "arcgis_hub"
```

```python
# registry.py
import os
import yaml
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).parent / "jurisdictions.yaml"

def load_registry(config_path: str | None = None) -> dict:
    """Load jurisdiction registry from YAML config.

    Priority: explicit path > env var > user data dir > package default.
    """
    if config_path is None:
        config_path = os.environ.get("MDC_ENCYCLOPEDIA_JURISDICTIONS")
    if config_path is None:
        user_config = Path.home() / ".local" / "share" / "mdc-encyclopedia" / "jurisdictions.yaml"
        if user_config.exists():
            config_path = str(user_config)
    if config_path is None:
        config_path = str(DEFAULT_CONFIG)

    with open(config_path) as f:
        data = yaml.safe_load(f)

    return data.get("jurisdictions", {})
```

### Pattern 3: Create-Copy-Swap Migration
**What:** SQLite migration pattern: create new table with target schema, INSERT INTO new FROM old with transformations, update child FK references, drop old, rename new. Wrapped in transaction with FK checks disabled.
**When to use:** When altering a PRIMARY KEY or making structural changes SQLite ALTER TABLE cannot handle.
**Example:**
```python
# In db.py migration
def _backup_database(db_path: str) -> str:
    """Create timestamped backup of database before migration."""
    from datetime import datetime
    import shutil
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup_path = f"{db_path}.backup-{timestamp}"
    shutil.copy2(db_path, backup_path)
    return backup_path

def _migrate_v2_to_v3(conn, db_path: str):
    """Schema V3 migration: synthetic composite key + jurisdiction."""
    backup = _backup_database(db_path)
    # ... (see Code Examples section for full SQL)
```

### Pattern 4: Sequential Multi-Jurisdiction Pull with Continue-on-Error
**What:** Loop over registered jurisdictions, pull each sequentially. If one fails, log the error and continue with the next. Report per-jurisdiction results at the end.
**When to use:** When pulling from multiple independent data sources where one failure should not block others.
**Example:**
```python
# In cli.py pull command
for slug, config in jurisdictions.items():
    try:
        count = pull_jurisdiction(conn, slug, config)
        results[slug] = {"status": "ok", "count": count}
    except Exception as exc:
        results[slug] = {"status": "error", "error": str(exc)}
        console.print(f"[red]Failed to pull {config['display_name']}: {exc}[/red]")
        continue  # Don't abort -- try next jurisdiction
```

### Anti-Patterns to Avoid
- **Hardcoding portal URLs in Python:** The current `HUB_BASE_URL` constant must be replaced with registry-driven configuration. Never add more constants for new portals.
- **Parallel jurisdiction pulls:** Although tempting for speed, parallel pulls risk rate-limit collisions across portals sharing Esri infrastructure. Use sequential pulls (one portal at a time).
- **Using ALTER TABLE ADD COLUMN for PK changes:** SQLite cannot ALTER a PRIMARY KEY. Must use the create-copy-swap pattern.
- **Committing child FK updates before parent PK migration:** All changes must happen in a single transaction with `PRAGMA foreign_keys=OFF` to avoid constraint violations during the transition.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML parsing | Custom config parser | PyYAML `yaml.safe_load()` | Edge cases in YAML spec (anchors, multi-doc, encoding) are extensive |
| HTTP retry/backoff | Custom retry loop | tenacity (already in use) | Exponential backoff, jitter, and conditional retry are tricky to get right |
| Database backup | Custom file copy | `shutil.copy2()` | Preserves metadata, handles OS-level edge cases |
| URL construction | String concatenation | f-strings with validated base URLs | Ensure URLs don't double-slash from trailing/leading slashes |

**Key insight:** The registry pattern means future jurisdictions (Palm Beach, Monroe County, etc.) require zero code changes -- just a YAML edit. This is the primary extensibility win.

## Common Pitfalls

### Pitfall 1: Foreign Key Cascade During Migration
**What goes wrong:** Updating the datasets PK without updating ALL child table references (columns, enrichments, audit_scores, changes) causes FK constraint violations on next DB access.
**Why it happens:** Four separate child tables reference `datasets.id`. Easy to miss one.
**How to avoid:** Disable FK checks during migration (`PRAGMA foreign_keys=OFF`). Update ALL four child tables. Re-enable FKs. Verify with `PRAGMA foreign_key_check`.
**Warning signs:** `sqlite3.IntegrityError: FOREIGN KEY constraint failed` after upgrade.

### Pitfall 2: source_url and download_url Hardcoded to Miami-Dade
**What goes wrong:** The normalizer builds `source_url` and `download_url` using hardcoded `opendata.miamidade.gov`. Broward datasets would get Miami-Dade URLs.
**Why it happens:** The current normalizer has the Miami-Dade domain baked into the URL templates.
**How to avoid:** Pass `hub_url` from the jurisdiction registry into `normalize_hub_dataset()`. Build URLs from the registry base URL.
**Warning signs:** Broward dataset links pointing to Miami-Dade portal (404s).

### Pitfall 3: Enrichment Prompt References Miami-Dade Departments
**What goes wrong:** The `SYSTEM_PROMPT` in `prompts.py` lists Miami-Dade specific departments (Police, Fire Rescue, PortMiami, etc.). When enriching Broward datasets, the model tries to match to Miami-Dade departments.
**Why it happens:** Prompt was written for single-jurisdiction use.
**How to avoid:** Make the system prompt a template with `{jurisdiction_display_name}` placeholder. For non-Miami-Dade jurisdictions, omit the department list and let the model infer. Or use a generic "local government" department approach.
**Warning signs:** Broward datasets assigned to "PortMiami" or "Miami-Dade Police" departments.

### Pitfall 4: Auto-Backup Must Precede Any Schema Change
**What goes wrong:** If the backup happens after a partial migration failure, the "backup" contains corrupt data.
**Why it happens:** Backup logic placed after some migration steps.
**How to avoid:** In `init_db()`, check if version < 3. If so, backup FIRST (before any V3 SQL), then migrate. If migration fails, user can restore from backup.
**Warning signs:** Backup file has the same corruption as the main DB.

### Pitfall 5: Registry File Not Found on Fresh Install
**What goes wrong:** New user runs `mdc-encyclopedia pull` but the YAML config file doesn't exist in their user data directory.
**Why it happens:** Package default config ships inside the wheel, but user hasn't copied it.
**How to avoid:** Use the fallback chain: env var > user data dir > package default. The package default should always be available via `importlib.resources` or `Path(__file__).parent`.
**Warning signs:** `FileNotFoundError` on first run after install.

### Pitfall 6: Row Count Mismatch After Migration
**What goes wrong:** Migration silently drops rows due to INSERT errors or constraint violations.
**Why it happens:** Unique constraint on `(jurisdiction, arcgis_id)` conflicts, or migration SQL has bugs.
**How to avoid:** Count rows in datasets, columns, enrichments, audit_scores, and changes BEFORE and AFTER migration. Assert counts match. Log both counts.
**Warning signs:** `stats` command shows fewer datasets after upgrade.

## Code Examples

### Schema V3 Migration SQL
```sql
-- Disable FK checks for migration
PRAGMA foreign_keys=OFF;

-- Create V3 datasets table
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
);

-- Migrate existing data with synthetic key
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
FROM datasets;

-- Update FK references in ALL child tables
UPDATE columns SET dataset_id = 'miami-dade_' || dataset_id;
UPDATE enrichments SET dataset_id = 'miami-dade_' || dataset_id;
UPDATE audit_scores SET dataset_id = 'miami-dade_' || dataset_id;
UPDATE changes SET dataset_id = 'miami-dade_' || dataset_id;

-- Populate ai_description from enrichments (denormalization)
UPDATE datasets_v3 SET ai_description = (
    SELECT description FROM enrichments WHERE enrichments.dataset_id = datasets_v3.id
);

-- Swap tables
DROP TABLE datasets;
ALTER TABLE datasets_v3 RENAME TO datasets;

-- Create indexes
CREATE INDEX idx_datasets_jurisdiction ON datasets(jurisdiction);
CREATE INDEX idx_datasets_source_portal ON datasets(source_portal);

-- Re-enable FK checks
PRAGMA foreign_keys=ON;

-- Verify FK integrity
PRAGMA foreign_key_check;
```

### Parameterized Hub Client
```python
# hub_client.py changes
SEARCH_ENDPOINT = "/api/search/v1/collections/dataset/items"

def create_client(base_url: str) -> httpx.Client:
    """Create an httpx.Client for a specific ArcGIS Hub portal."""
    return httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"User-Agent": "mdc-encyclopedia/0.2.0"},
    )
```

### Jurisdiction-Aware Normalizer
```python
# normalizer.py changes
def normalize_hub_dataset(feature: dict, jurisdiction: str, hub_url: str) -> dict:
    """Normalize Hub API feature with jurisdiction context."""
    props = feature.get("properties", {})
    arcgis_id = feature.get("id", "")
    synthetic_id = f"{jurisdiction}_{arcgis_id}"

    ds_type = props.get("type", "")
    if ds_type == "Feature Service":
        download_url = f"{hub_url}/api/download/v1/items/{arcgis_id}/csv?layers=0"
    else:
        download_url = None

    return {
        "id": synthetic_id,
        "jurisdiction": jurisdiction,
        "arcgis_id": arcgis_id,
        "source_portal": "arcgis_hub",
        "source_url": f"{hub_url}/datasets/{arcgis_id}",
        "title": props.get("title"),
        "description": strip_html(props.get("description", "")),
        # ... rest unchanged
        "download_url": download_url,
    }
```

### Jurisdiction-Aware Prompt Template
```python
# prompts.py changes
SYSTEM_PROMPT_TEMPLATE = """\
You are a {jurisdiction_display_name} data librarian helping residents understand open datasets.

Write as if explaining to a neighbor -- clear, helpful, no bureaucratic jargon.
...
"""

def build_system_prompt(jurisdiction_display_name: str) -> str:
    """Build jurisdiction-specific system prompt."""
    return SYSTEM_PROMPT_TEMPLATE.format(
        jurisdiction_display_name=jurisdiction_display_name
    )
```

### CLI Pull with --jurisdiction Flag
```python
# cli.py pull command changes
@cli.command()
@click.option("--jurisdiction", "-j", default=None,
              help="Pull from a specific jurisdiction (e.g., broward). Pulls all if omitted.")
@click.pass_context
def pull(ctx, jurisdiction):
    """Pull dataset metadata from registered ArcGIS Hub portals."""
    registry = load_registry()

    if jurisdiction:
        if jurisdiction not in registry:
            console.print(f"[red]Unknown jurisdiction: {jurisdiction}[/red]")
            console.print(f"Available: {', '.join(registry.keys())}")
            raise click.Abort()
        targets = {jurisdiction: registry[jurisdiction]}
    else:
        targets = registry

    for slug, config in targets.items():
        console.print(f"\n[bold]Pulling from {config['display_name']}...[/bold]")
        # ... pull logic per jurisdiction
```

### Stats with Jurisdiction Breakdown
```python
# cli.py stats command addition
jurisdiction_rows = conn.execute(
    "SELECT jurisdiction, COUNT(*) as cnt FROM datasets GROUP BY jurisdiction ORDER BY jurisdiction"
).fetchall()

jurisdiction_table = Table(title="Datasets by Jurisdiction")
jurisdiction_table.add_column("Jurisdiction", style="bold")
jurisdiction_table.add_column("Count", justify="right")

for row in jurisdiction_rows:
    jurisdiction_table.add_row(row["jurisdiction"], str(row["cnt"]))
jurisdiction_table.add_section()
jurisdiction_table.add_row("Total", str(total_datasets))

console.print(jurisdiction_table)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded portal URL | Registry-driven config | This phase | Extensible to any ArcGIS Hub portal |
| Single-value TEXT PK (arcgis_id) | Synthetic composite PK (jurisdiction_arcgis_id) | This phase | Multi-jurisdiction coexistence |
| Miami-Dade-specific prompt | Template-driven jurisdiction prompt | This phase | Accurate enrichment per jurisdiction |
| ArcGIS Hub Search API v1 | Same -- all portals use v1 | Stable since ~2019 | No API migration needed |

**Deprecated/outdated:**
- ArcGIS Hub v2 API (older REST-based search): Replaced by v1 OGC API Records. All three portals are on v1.

## Open Questions

1. **Department lists for Broward and City of Miami**
   - What we know: Miami-Dade departments are enumerated in the current prompt. Broward and City of Miami have different department structures.
   - What's unclear: Whether to enumerate departments per jurisdiction or use a generic approach.
   - Recommendation: For Phase 8, use a generic prompt that names the jurisdiction but omits department lists for non-Miami-Dade. Jurisdiction-specific department lists can be added to the registry config later if enrichment quality suffers.

2. **ArcGIS Hub rate limits across portals**
   - What we know: The current 1-second rate limit works for Miami-Dade. All portals are hosted on Esri infrastructure.
   - What's unclear: Whether Esri applies per-portal or per-IP rate limits.
   - Recommendation: Keep the same 1-second rate limit per request. Sequential jurisdiction pulls (not parallel) avoid any shared-infrastructure rate limit issues.

3. **Config file distribution in pip package**
   - What we know: `pyproject.toml` uses `force-include` for site templates. Same pattern can include `jurisdictions.yaml`.
   - What's unclear: Whether `importlib.resources` or `Path(__file__).parent` is more reliable across install methods.
   - Recommendation: Use `Path(__file__).parent / "jurisdictions.yaml"` (consistent with current template loading pattern in `generator.py`). Add to `force-include` in `pyproject.toml`.

## Sources

### Primary (HIGH confidence)
- **Live API verification**: `https://geohub-bcgis.opendata.arcgis.com/api/search/v1/collections/dataset/items?limit=1` -- Confirmed GeoJSON FeatureCollection response, 83 datasets, pagination links, identical structure to Miami-Dade.
- **Live API verification**: `https://datahub-miamigis.opendata.arcgis.com/api/search/v1/collections/dataset/items?limit=1` -- Confirmed GeoJSON FeatureCollection response, 83 datasets, pagination links, identical structure to Miami-Dade.
- **Context7 /yaml/pyyaml** -- PyYAML `yaml.safe_load()` usage patterns, security considerations. HIGH reputation source.
- **Codebase analysis**: `db.py`, `cli.py`, `hub_client.py`, `normalizer.py`, `prompts.py`, `context.py`, `generator.py` -- Full understanding of current architecture and all touchpoints.

### Secondary (MEDIUM confidence)
- [Broward County GeoHub](https://geohub-bcgis.opendata.arcgis.com/) -- Portal landing page verified via WebSearch.
- [City of Miami Open Data GIS](https://datahub-miamigis.opendata.arcgis.com/) -- Portal landing page verified via WebSearch.
- [ArcGIS Hub Search API / OGC API Records](https://doc.arcgis.com/en/hub/content/federate-data-with-external-catalogs.htm) -- Esri documentation on Hub catalog feeds and OGC endpoints.

### Tertiary (LOW confidence)
- None. All findings verified with live API calls or codebase analysis.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- PyYAML is the only new dependency; all other libraries already in use. Verified via Context7.
- Architecture: HIGH -- Based on complete codebase analysis of all affected files. Migration pattern follows existing V1->V2 precedent. API compatibility confirmed via live requests.
- Pitfalls: HIGH -- Identified from direct analysis of current code (hardcoded URLs in normalizer, FK references in 4 child tables, prompt department list). Migration risks documented from SQLite documentation.

**Research date:** 2026-02-26
**Valid until:** 2026-03-26 (stable domain -- SQLite, YAML, ArcGIS Hub APIs are slow-moving)
