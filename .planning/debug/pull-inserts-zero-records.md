---
status: diagnosed
trigger: "mdc-encyclopedia pull creates database and tables but inserts 0 records"
created: 2026-02-24T00:00:00Z
updated: 2026-02-24T02:55:00Z
---

## Current Focus

hypothesis: CONFIRMED - Two separate database files exist due to relative path; pull writes to CWD, user checks from different CWD
test: Inspected both database files
expecting: One has data, one is empty
next_action: Return diagnosis

## Symptoms

expected: ~576 datasets inserted into SQLite database after pull command
actual: Database created, tables created, progress bar completes, 0 records in database
errors: None visible (command completes without errors)
reproduction: Run `mdc-encyclopedia pull`
started: First observed during Phase 2 development

## Eliminated

- hypothesis: Data flow broken (fetch_all_datasets not yielding, normalize failing, upsert not committing)
  evidence: Code trace shows correct data flow; upsert_dataset calls conn.commit(); cli.py also calls conn.commit() at line 150; normalize_hub_dataset produces valid dict matching API response structure; actual API response confirmed to match expected format
  timestamp: 2026-02-24T02:50:00Z

- hypothesis: Silent exception swallowing causing all 576 datasets to skip
  evidence: If all failed, summary table would show Skipped/failed: 576 and Total datasets: 0; user says command completes without errors; also the home-dir DB has 486 records proving the pipeline works
  timestamp: 2026-02-24T02:52:00Z

- hypothesis: json_valid CHECK constraint rejecting all inserts
  evidence: json.dumps(props) always produces valid JSON from response.json() output; also fallback schema exists; and home-dir DB has 486 records
  timestamp: 2026-02-24T02:52:00Z

## Evidence

- timestamp: 2026-02-24T02:50:00Z
  checked: ArcGIS Hub Search API response structure
  found: curl to https://opendata.miamidade.gov/api/search/v1/collections/dataset/items?limit=1 returns valid GeoJSON with feature.id, feature.properties.title, feature.properties.created (integer ms), etc. - matches what normalize_hub_dataset expects
  implication: Normalizer should work correctly with real API data

- timestamp: 2026-02-24T02:53:00Z
  checked: Database files on filesystem
  found: TWO database files exist - /home/d48reu/DataDictionary/mdc_encyclopedia.db (40KB, 0 records, created 19:58) and /home/d48reu/mdc_encyclopedia.db (3.8MB, 486 datasets + 6165 columns, modified 21:19)
  implication: Pull command ran from home dir, wrote to home dir DB; project dir DB only has schema

- timestamp: 2026-02-24T02:54:00Z
  checked: Record counts in both databases
  found: Project dir DB = 0 datasets, 0 columns. Home dir DB = 486 datasets, 6165 columns with real Miami-Dade data (MDPD PCB Reporting Data, Groundwater Level, BuildingModel3D, etc.)
  implication: The pull pipeline WORKS correctly. The data is going to the wrong file (relative to where user expects it)

## Resolution

root_cause: The database path defaults to the relative path "mdc_encyclopedia.db" (cli.py line 39). When the user runs `mdc-encyclopedia pull` from their home directory (~), the database is created at ~/mdc_encyclopedia.db. When they check for records or run the command from the project directory (~/DataDictionary/), a DIFFERENT database file is created/checked at ~/DataDictionary/mdc_encyclopedia.db. The pull data (486 datasets, 6165 columns) is in ~/mdc_encyclopedia.db; the project-dir database has 0 records because it only had init_db run on it.
fix:
verification:
files_changed: []
