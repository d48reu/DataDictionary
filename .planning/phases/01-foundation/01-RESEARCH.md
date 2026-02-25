# Phase 1: Foundation - Research

**Researched:** 2026-02-24
**Domain:** Python packaging (Hatchling + src layout), CLI framework (Click + rich-click), SQLite schema design
**Confidence:** HIGH

## Summary

Phase 1 builds the installable Python package skeleton that all downstream phases depend on. The technical domain is well-established: Hatchling for build backend, Click for CLI with rich-click for formatted output, and Python's stdlib sqlite3 for database management. All chosen libraries are mature, actively maintained, and have excellent documentation.

The primary complexity is getting the src layout + Hatchling + console_scripts wiring correct on the first try, and designing a SQLite schema flexible enough for 6 downstream phases without requiring breaking migrations. The `PRAGMA user_version` pattern provides a lightweight, no-dependency schema versioning approach that fits the project's "keep it simple" philosophy.

**Primary recommendation:** Use `import rich_click as click` (drop-in replacement) rather than the declarative `cls=RichGroup` pattern -- it's simpler, fewer imports, and provides the same output quality.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Default database location: current working directory as `mdc_encyclopedia.db`
- Override via `MDC_ENCYCLOPEDIA_DB` environment variable (no CLI flag)
- On first run, print one-line Rich message: "Created database: mdc_encyclopedia.db" (green checkmark, non-intrusive)
- No XDG paths, no data subdirectory -- keep it visible and simple
- src/ layout: `src/mdc_encyclopedia/`
- Feature modules (flat, one per concern): cli.py, db.py, and future modules created when their phase starts
- All subcommands registered in Phase 1 as stubs printing "not yet implemented": pull, enrich, audit, diff, export, serve, stats
- CLI framework: Click (with rich-click for Rich-formatted help output)
- Build backend: Hatchling with pyproject.toml
- Entry point: `mdc-encyclopedia` console script
- Hybrid schema: core columns + JSON extras (`metadata_json` TEXT column)
- Broad column set for datasets table: id, source_portal, source_url, title, description, category, publisher, format, created_at, updated_at, row_count, tags, license, api_endpoint, bbox/geometry, download_url
- Columns table: dataset_id (FK), name, data_type, description
- Enrichments table: one row per dataset (latest only) -- dataset_id (FK), description, use_cases, keywords, department, update_freq, civic_relevance, prompt_version, enriched_at
- Audit_scores table: dataset_id (FK), composite_score, staleness, completeness, documentation, audited_at
- Changes table: dataset_id, change_type, details, detected_at
- Schema version tracking: a schema_version table to track current version, with ALTER TABLE upgrades on startup as needed (no Alembic)

### Claude's Discretion
- Exact Rich formatting and colors for help output
- Click group/command decorator patterns
- Schema version upgrade implementation details
- Test structure and fixtures
- .gitignore contents

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CLI-01 | Installable via `pip install .` with pyproject.toml and Hatchling backend | Hatchling src layout config, pyproject.toml structure, console_scripts wiring |
| CLI-02 | Entry point `mdc-encyclopedia` available after install | `[project.scripts]` configuration with Hatchling, src layout package discovery |
| CLI-10 | Rich terminal output for all commands (progress bars, tables, colored status) | rich-click drop-in replacement pattern, Rich console markup |
| INGEST-04 | All metadata stored in SQLite database with normalized schema (datasets, columns tables) | SQLite schema design, PRAGMA user_version migration pattern, stdlib sqlite3 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| click | 8.3.1 | CLI framework with groups, commands, options, arguments | De facto Python CLI standard; 1M+ weekly downloads, Pallets maintained |
| rich-click | 1.9.7 | Rich-formatted help output for Click CLIs | Drop-in Click replacement; 1.1M weekly downloads, actively maintained |
| rich | 14.3.3 | Terminal formatting (colors, tables, progress bars, panels) | Standard Python terminal formatting library; required by rich-click |
| hatchling | 1.29.0 | Build backend for pyproject.toml | Modern PEP 517 build backend; official PyPA project, handles src layout natively |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sqlite3 | stdlib | Database engine | Always -- no external dependency needed, ships with Python |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| click + rich-click | Typer | Typer is built on Click; adds type-hint magic but less control over help formatting. User chose Click -- locked decision. |
| PRAGMA user_version | Alembic | Alembic is overkill for a single-file SQLite DB with simple schema evolution. User chose no Alembic -- locked decision. |
| Hatchling | setuptools | setuptools works but Hatchling has cleaner src layout support and is the modern standard. User chose Hatchling -- locked decision. |

**Installation (runtime dependencies):**
```
click>=8.0
rich-click>=1.8
rich>=13.0
```

**Python version floor:** `>=3.10` (binding constraint: Click 8.3.1 requires Python >=3.10)

## Architecture Patterns

### Recommended Project Structure
```
DataDictionary/
├── pyproject.toml
├── src/
│   └── mdc_encyclopedia/
│       ├── __init__.py          # Package version (__version__ = "0.1.0")
│       ├── cli.py               # Click group + all subcommand stubs
│       └── db.py                # Database init, schema, version management
└── tests/                       # Future test directory
```

### Pattern 1: Drop-in rich-click Import
**What:** Replace `import click` with `import rich_click as click` for automatic Rich formatting of all help output.
**When to use:** Always -- this is the simplest integration path.
**Example:**
```python
# Source: https://ewels.github.io/rich-click/latest/
import rich_click as click

@click.group()
@click.version_option()
def cli():
    """MDC Open Data Encyclopedia - catalog, enrich, and publish Miami-Dade County open datasets."""
    pass

@cli.command()
def pull():
    """Pull dataset metadata from Miami-Dade open data portals."""
    click.echo("Not yet implemented")
```
**Confidence:** HIGH -- verified via rich-click official docs and PyPI

### Pattern 2: Database Initialization on First Command
**What:** Check if database exists at startup; if not, create it with full schema and print a creation message.
**When to use:** On every CLI invocation, as a pre-command hook.
**Example:**
```python
# Pattern: Click group callback initializes DB before any subcommand runs
import rich_click as click
from rich.console import Console

console = Console()

@click.group()
@click.pass_context
def cli(ctx):
    """MDC Open Data Encyclopedia."""
    ctx.ensure_object(dict)
    db_path = os.environ.get("MDC_ENCYCLOPEDIA_DB", "mdc_encyclopedia.db")
    created = init_db(db_path)  # Returns True if newly created
    if created:
        console.print(f"[green]✓[/green] Created database: {db_path}")
    ctx.obj["db_path"] = db_path
```
**Confidence:** HIGH -- standard Click context pattern from official docs

### Pattern 3: PRAGMA user_version for Schema Versioning
**What:** Use SQLite's built-in `PRAGMA user_version` integer to track schema version. On startup, compare against expected version and run upgrade SQL if needed.
**When to use:** Every time the database connection is opened.
**Example:**
```python
# Source: https://levlaz.org/sqlite-db-migrations-with-pragma-user_version/
import sqlite3

CURRENT_SCHEMA_VERSION = 1

def init_db(db_path: str) -> bool:
    """Initialize or upgrade the database. Returns True if newly created."""
    is_new = not os.path.exists(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    version = conn.execute("PRAGMA user_version").fetchone()[0]

    if version < 1:
        _create_schema_v1(conn)
        conn.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION}")

    # Future: if version < 2: _upgrade_to_v2(conn)

    conn.commit()
    conn.close()
    return is_new
```
**Confidence:** HIGH -- PRAGMA user_version is an official SQLite feature, verified via SQLite docs and community patterns

### Pattern 4: Console Script Entry Point with Hatchling src Layout
**What:** Wire `mdc-encyclopedia` command to the Click group via pyproject.toml.
**When to use:** Package configuration.
**Example:**
```toml
# Source: https://hatch.pypa.io/1.13/config/build/ + https://packaging.python.org/en/latest/guides/creating-command-line-tools/
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mdc-encyclopedia"
version = "0.1.0"
description = "Miami-Dade County Open Data Encyclopedia"
requires-python = ">=3.10"
dependencies = [
    "click>=8.0",
    "rich-click>=1.8",
    "rich>=13.0",
]

[project.scripts]
mdc-encyclopedia = "mdc_encyclopedia.cli:cli"

[tool.hatch.build.targets.wheel]
packages = ["src/mdc_encyclopedia"]
```
**Confidence:** HIGH -- verified via Hatchling official docs and PyPA packaging guide

### Anti-Patterns to Avoid
- **Importing click AND rich_click separately:** Use `import rich_click as click` exclusively. Mixing imports causes inconsistent help formatting.
- **Putting DB path as a CLI global option:** User decided env var only (`MDC_ENCYCLOPEDIA_DB`). No `--db` flag.
- **Creating the DB lazily per-command:** Initialize in the group callback so every subcommand has a guaranteed database.
- **Using `setup.py` or `setup.cfg`:** Hatchling + pyproject.toml is the locked decision. No legacy packaging files.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI argument parsing | Custom argparse wrapper | Click (via rich-click) | Click handles help generation, type validation, error messages |
| Terminal formatting | ANSI escape codes | Rich | Cross-platform, handles terminal width, fallback for dumb terminals |
| Help output formatting | Custom help formatter | rich-click | Automatic Rich formatting of all Click help with zero config |
| Schema migrations | Custom migration framework | PRAGMA user_version + versioned SQL | SQLite's built-in version tracking is simpler than any migration library |
| Package building | Manual sys.path hacks | Hatchling + pip install -e . | Proper editable installs, console_scripts, dependency resolution |

**Key insight:** This phase has zero novel technical problems. Every component has a well-established library solution. The risk is in wiring them together incorrectly, not in any individual piece.

## Common Pitfalls

### Pitfall 1: Hatchling Not Finding src Layout Packages
**What goes wrong:** `pip install .` succeeds but `import mdc_encyclopedia` fails with ModuleNotFoundError, or the installed package is named "src" instead of "mdc_encyclopedia".
**Why it happens:** Hatchling's auto-detection can fail when package name (mdc-encyclopedia with hyphen) differs from import name (mdc_encyclopedia with underscore), or when `[tool.hatch.build.targets.wheel]` is missing the `packages` directive.
**How to avoid:** Explicitly set `packages = ["src/mdc_encyclopedia"]` in `[tool.hatch.build.targets.wheel]`. Do NOT rely on auto-detection.
**Warning signs:** After `pip install .`, try `python -c "import mdc_encyclopedia"` -- if it fails, the build config is wrong.

### Pitfall 2: Console Script Entry Point Not Found
**What goes wrong:** `pip install .` works but running `mdc-encyclopedia` gives "command not found".
**Why it happens:** The `[project.scripts]` entry points to wrong module path, or the function name is wrong. With src layout, the module path must NOT include "src." prefix -- it's `mdc_encyclopedia.cli:cli`, not `src.mdc_encyclopedia.cli:cli`.
**How to avoid:** The entry point path is the import path, not the file path. Test with `pip install -e .` then `which mdc-encyclopedia` to verify.
**Warning signs:** `pip show mdc-encyclopedia` shows the package is installed but the command doesn't exist in PATH.

### Pitfall 3: Foreign Keys Not Enforced in SQLite
**What goes wrong:** Rows with invalid foreign key references get inserted without error.
**Why it happens:** SQLite does not enforce foreign keys by default. You must run `PRAGMA foreign_keys=ON` on every new connection.
**How to avoid:** Execute `PRAGMA foreign_keys=ON` immediately after opening any connection, before any other SQL.
**Warning signs:** Orphan rows in child tables (columns, enrichments, etc.) with dataset_ids that don't exist in datasets.

### Pitfall 4: Missing `__init__.py` in src Layout
**What goes wrong:** Package installs but imports fail or the package appears empty.
**Why it happens:** Hatchling requires `__init__.py` to recognize a directory as a Python package.
**How to avoid:** Always create `src/mdc_encyclopedia/__init__.py` with at least `__version__ = "0.1.0"`.
**Warning signs:** `pip install .` completes but `mdc-encyclopedia` fails with ImportError.

### Pitfall 5: SQLite Schema Uses Wrong TEXT Affinity for JSON
**What goes wrong:** JSON data stored in TEXT columns works fine but developers later try to query it with SQLite JSON functions and get unexpected behavior.
**Why it happens:** SQLite has built-in JSON functions (json_extract, json_each) that work on TEXT columns, but the column must contain valid JSON.
**How to avoid:** For `metadata_json` and similar columns, validate JSON before insertion. Consider using CHECK constraints: `CHECK(json_valid(metadata_json) OR metadata_json IS NULL)`.
**Warning signs:** Malformed JSON strings stored in metadata_json that break downstream queries.

### Pitfall 6: Editable Install Not Reflecting Changes
**What goes wrong:** Code changes aren't reflected when running `mdc-encyclopedia` after `pip install -e .`.
**Why it happens:** Hatchling editable installs work differently than setuptools. Some environments need `--config-settings editable_mode=compat` for classic .pth-file behavior.
**How to avoid:** Use `pip install -e .` and verify changes are picked up. If not, try `pip install -e . --config-settings editable_mode=compat`.
**Warning signs:** Old behavior persists after code edits despite editable install.

## Code Examples

Verified patterns from official sources:

### Complete pyproject.toml
```toml
# Sources: Hatchling docs (https://hatch.pypa.io/1.13/config/build/)
#          PyPA packaging guide (https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mdc-encyclopedia"
version = "0.1.0"
description = "Miami-Dade County Open Data Encyclopedia"
requires-python = ">=3.10"
license = "MIT"
authors = [
    { name = "Diego Abreu", email = "diego@abreudataworks.com" },
]
dependencies = [
    "click>=8.0",
    "rich-click>=1.8",
    "rich>=13.0",
]

[project.scripts]
mdc-encyclopedia = "mdc_encyclopedia.cli:cli"

[tool.hatch.build.targets.wheel]
packages = ["src/mdc_encyclopedia"]
```

### CLI Entry Point (cli.py)
```python
# Source: Click docs (https://github.com/pallets/click/blob/main/docs/commands-and-groups.md)
#         rich-click docs (https://ewels.github.io/rich-click/latest/)
import os
import rich_click as click
from rich.console import Console

console = Console()

@click.group()
@click.version_option(package_name="mdc-encyclopedia")
@click.pass_context
def cli(ctx):
    """MDC Open Data Encyclopedia - catalog, enrich, and publish Miami-Dade County open datasets."""
    ctx.ensure_object(dict)
    db_path = os.environ.get("MDC_ENCYCLOPEDIA_DB", "mdc_encyclopedia.db")
    ctx.obj["db_path"] = db_path

@cli.command()
def pull():
    """Pull dataset metadata from Miami-Dade open data portals."""
    console.print("[yellow]Not yet implemented[/yellow]")

# ... additional stub commands follow same pattern
```

### Database Schema Creation (db.py)
```python
# Source: Python sqlite3 docs + PRAGMA user_version pattern
#         (https://levlaz.org/sqlite-db-migrations-with-pragma-user_version/)
import sqlite3
import os

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
    metadata_json TEXT,
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

def init_db(db_path: str) -> bool:
    """Initialize or upgrade the database schema. Returns True if newly created."""
    is_new = not os.path.exists(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    version = conn.execute("PRAGMA user_version").fetchone()[0]

    if version < 1:
        conn.executescript(SCHEMA_V1)
        conn.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION}")

    conn.commit()
    conn.close()
    return is_new
```

### Package __init__.py
```python
"""MDC Open Data Encyclopedia."""
__version__ = "0.1.0"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| setup.py + setuptools | pyproject.toml + Hatchling | PEP 621 (2021), Hatchling matured 2023+ | No setup.py needed; single config file |
| argparse for CLI | Click + rich-click | Click stable since 2014, rich-click since 2022 | Automatic help formatting, subcommand groups, type validation |
| Alembic for SQLite migrations | PRAGMA user_version | Always available (SQLite feature) | Zero dependencies, simpler for single-file DBs |
| flat layout (package at repo root) | src layout | PEP 517/518 era (2019+) | Prevents accidental local imports during testing |

**Deprecated/outdated:**
- `setup.py` / `setup.cfg`: Still works but pyproject.toml is the modern standard. Hatchling does not use these.
- `pkg_resources` for version detection: Use `importlib.metadata.version()` instead (stdlib since Python 3.8).
- Click's built-in help formatting: Still functional but visually plain. rich-click is now the community standard for enhanced output.

## Open Questions

1. **Dataset ID format**
   - What we know: The `id` column is TEXT PRIMARY KEY. Socrata uses 4-char identifiers like "xxxx-yyyy". ArcGIS Hub uses UUIDs.
   - What's unclear: Whether to use source IDs directly or generate composite IDs (e.g., "socrata:xxxx-yyyy").
   - Recommendation: Defer to Phase 2 (data ingestion). For Phase 1, TEXT PRIMARY KEY is flexible enough for any format. The planner should note this as a Phase 2 decision.

2. **Enrichments table: one row per dataset vs. history**
   - What we know: User decided "one row per dataset (latest only)" with UNIQUE constraint on dataset_id.
   - What's unclear: Whether old enrichments should be preserved anywhere when re-enriched.
   - Recommendation: Locked decision says "latest only." If history is needed later, a schema_version upgrade can add an enrichment_history table. Not a Phase 1 concern.

3. **JSON validation in metadata_json**
   - What we know: SQLite has `json_valid()` function available in recent versions.
   - What's unclear: Whether the Python sqlite3 stdlib binding includes JSON1 extension on all target platforms.
   - Recommendation: Use CHECK constraint if available (`CHECK(json_valid(metadata_json) OR metadata_json IS NULL)`), but wrap in try/except during schema creation and fall back to no constraint if JSON1 is not compiled in. LOW risk -- most modern Python distributions include JSON1.

## Sources

### Primary (HIGH confidence)
- Context7 `/pallets/click` -- group/command patterns, decorator usage, context passing
- Context7 `/pypa/hatch` -- pyproject.toml structure, console_scripts, src layout configuration
- Context7 `/websites/rich_readthedocs_io_en_stable` -- Rich console markup, print formatting
- [Hatchling build config docs](https://hatch.pypa.io/1.13/config/build/) -- packages option for src layout
- [PyPI: click 8.3.1](https://pypi.org/project/click/) -- current version, Python >=3.10
- [PyPI: rich-click 1.9.7](https://pypi.org/project/rich-click/) -- current version, dependencies
- [PyPI: rich 14.3.3](https://pypi.org/project/rich/) -- current version
- [PyPI: hatchling 1.29.0](https://pypi.org/project/hatchling/) -- current version
- [PyPA packaging guide: creating CLI tools](https://packaging.python.org/en/latest/guides/creating-command-line-tools/) -- src layout + entry points

### Secondary (MEDIUM confidence)
- [rich-click official docs](https://ewels.github.io/rich-click/latest/) -- drop-in import pattern, configuration options
- [PRAGMA user_version migration pattern](https://levlaz.org/sqlite-db-migrations-with-pragma-user_version/) -- versioned migration approach
- [Hatch discussion #1051](https://github.com/pypa/hatch/discussions/1051) -- src layout package naming gotcha

### Tertiary (LOW confidence)
- None -- all findings verified via primary or secondary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries verified via PyPI with current versions, Context7 docs confirmed APIs
- Architecture: HIGH -- src layout + Click groups + PRAGMA user_version are well-documented patterns with official examples
- Pitfalls: HIGH -- Hatchling src layout issues confirmed via GitHub discussions; SQLite foreign key gotcha is well-documented

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (stable domain, slow-moving libraries)
