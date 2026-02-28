# Phase 12: Site UI Polish and CI Pipeline - Research

**Researched:** 2026-02-27
**Domain:** Static site UI (Jinja2/CSS/JS) + GitHub Actions CI/CD
**Confidence:** HIGH

## Summary

Phase 12 has two distinct workstreams: (1) surfacing jurisdiction metadata throughout the browsing experience via filter dropdown, badges, and search, and (2) updating the CI pipeline to pull from all three jurisdictions and deploy automatically. Both workstreams build on well-understood, already-integrated technology -- Jinja2 templates, vanilla JS filtering, lunr.py search indexing, and GitHub Actions with Pages deployment.

The codebase is well-structured for these changes. The `jurisdiction` field already flows from the database through `_build_dataset_context()` (via `dict(row)`) into every dataset dict. The browse page already has a working filter bar with three dropdowns (format, publisher, tag) and a client-side `filter.js` that hides/shows rows by data attributes. Adding a jurisdiction dropdown follows the exact same pattern. The search index already uses lunr.py with field-based boosting -- adding a `jurisdiction` field is a one-line addition to the documents list and fields list. The CI workflow already exists and deploys to GitHub Pages -- it just needs the `pull` command updated for multi-jurisdiction and the enrichment step made optional via input.

**Primary recommendation:** Follow existing codebase patterns exactly -- add jurisdiction as a fourth filter dropdown (same pattern as format/publisher/tag), add a jurisdiction badge styled like the existing AI badge, add jurisdiction as a searchable field in lunr with moderate boost, and update the CI workflow to use `mdc-encyclopedia pull` (which already pulls all jurisdictions by default) with the enrichment toggle from CONTEXT.md decisions.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **CI Trigger**: Both weekly cron schedule AND manual workflow_dispatch
- **Schedule**: Weekly (government data doesn't change hourly -- good balance of freshness vs CI minutes)
- **Failure handling**: Continue pulling remaining jurisdictions if one fails; build site with whatever succeeded; flag failures in workflow summary/logs
- **AI enrichment**: Optional -- skipped on scheduled runs, available as a boolean input on manual dispatch
- **Pipeline steps**: pull all jurisdictions -> (optionally) enrich new datasets -> build site with feeds/exports -> deploy to GitHub Pages

### Claude's Discretion
- Jurisdiction filter placement and interaction with existing format/publisher/tag filters
- Badge visual design and color coding per jurisdiction
- Search index integration approach for jurisdiction field in Lunr.js
- CI caching strategy (pip cache, database, etc.)
- Exact cron day/time for weekly schedule
- GitHub Pages deployment method (peaceiris/actions-gh-pages vs built-in)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MULTI-05 | Jurisdiction filter dropdown on browse page | Existing filter bar pattern (format/publisher/tag dropdowns + filter.js) provides exact template. Add fourth `<select>` with `data-jurisdiction` attribute on dataset rows. |
| MULTI-06 | Jurisdiction badge on dataset cards and detail pages | Existing `.ai-badge` and `.chip` CSS classes provide visual patterns. Badge text from `ds.jurisdiction` mapped through registry `display_name`. |
| MULTI-07 | Jurisdiction field in Lunr.js search index | lunr.py `lunr()` call in `search_index.py` already uses dict-based field specs with boosts. Add `{"field_name": "jurisdiction", "boost": 5}` to fields list. |
| MULTI-08 | Updated CI pipeline with multi-jurisdiction pull | Existing `encyclopedia.yml` workflow needs: remove single-jurisdiction `pull`, add `enrich_ai` boolean input, add `enrich-fields` step, update cron schedule. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Jinja2 | >=3.1 | HTML template rendering | Already used in site generator |
| lunr | 0.8.0 | Python-side Lunr.js index building | Already installed, generates JS-compatible index |
| Lunr.js | 2.3.9 (CDN) | Client-side full-text search | Already loaded in base.html |
| GitHub Actions | v4 actions | CI/CD pipeline | Already configured with deploy-pages@v4 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| actions/checkout | v5 | Repository checkout | Already in workflow |
| actions/setup-python | v5 | Python environment | Already in workflow, has pip cache |
| actions/upload-pages-artifact | v4 | Bundle site for Pages | Already in workflow |
| actions/deploy-pages | v4 | Deploy to GitHub Pages | Already in workflow |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Built-in deploy-pages@v4 | peaceiris/actions-gh-pages | peaceiris pushes to gh-pages branch; built-in uses Pages artifact API (cleaner, already working) |
| Client-side JS filtering | Server-side pre-rendered filtered pages | JS filtering is simpler, already proven in codebase, works well for <5000 datasets |

**Recommendation:** Keep `actions/deploy-pages@v4` (already working). No reason to switch deployment methods.

**Installation:** No new dependencies needed. All libraries already installed.

## Architecture Patterns

### Recommended Project Structure
No new files needed. Changes touch existing files:
```
src/mdc_encyclopedia/
├── site/
│   ├── templates/
│   │   ├── browse.html         # Add jurisdiction dropdown + data attr
│   │   ├── dataset.html        # Add jurisdiction badge
│   │   └── base.html           # (optional) update footer for multi-jurisdiction
│   ├── static/
│   │   ├── filter.js           # Add jurisdiction filter logic
│   │   ├── search.js           # (no changes -- reads search-data.json)
│   │   └── style.css           # Add jurisdiction badge styles
│   ├── generator.py            # Pass jurisdictions list to browse context
│   ├── search_index.py         # Add jurisdiction field to index
│   └── context.py              # (no changes -- jurisdiction already in dict(row))
.github/
└── workflows/
    └── encyclopedia.yml        # Update pipeline for multi-jurisdiction
```

### Pattern 1: Jurisdiction Filter (follows existing filter pattern)
**What:** Add a fourth `<select>` dropdown to the browse page filter bar, backed by a `data-jurisdiction` attribute on each dataset row.
**When to use:** This is the established pattern in the codebase.
**Example:**

Template addition in `browse.html`:
```html
<select id="filter-jurisdiction" aria-label="Filter by jurisdiction">
    <option value="">All Jurisdictions</option>
    {% for j in jurisdictions %}
    <option value="{{ j.slug }}">{{ j.display_name }}</option>
    {% endfor %}
</select>
```

Dataset row attribute addition:
```html
<div class="dataset-row"
     data-format="{{ ds.format|default('')|lower }}"
     data-publisher="{{ ds.publisher|default('')|lower }}"
     data-tags="{{ ds.tags_text|default('')|lower }}"
     data-jurisdiction="{{ ds.jurisdiction|default('')|lower }}">
```

JavaScript in `filter.js` (same pattern as existing filters):
```javascript
var jurisdictionSelect = document.getElementById("filter-jurisdiction");
// In applyFilters():
var jurisdictionVal = jurisdictionSelect.value.toLowerCase();
var matchJurisdiction = !jurisdictionVal || rowJurisdiction === jurisdictionVal;
```

### Pattern 2: Jurisdiction Badge (follows .chip / .ai-badge pattern)
**What:** A small colored badge showing jurisdiction name, placed on dataset cards and detail pages.
**When to use:** On every dataset card in browse list and in the metadata table on detail pages.
**Example:**

Badge in browse page dataset rows:
```html
<span class="jurisdiction-badge jurisdiction-{{ ds.jurisdiction|default('unknown') }}">
    {{ ds.jurisdiction_display_name|default(ds.jurisdiction|default('Unknown')) }}
</span>
```

CSS using existing custom properties:
```css
.jurisdiction-badge {
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 0.1rem 0.45rem;
    border-radius: 3px;
    vertical-align: middle;
    letter-spacing: 0.3px;
}
.jurisdiction-miami-dade { background: #e3f2fd; color: #003366; }
.jurisdiction-broward { background: #fff3e0; color: #e65100; }
.jurisdiction-miami { background: #e8f5e9; color: #1b5e20; }
```

### Pattern 3: Search Index Field Addition
**What:** Add `jurisdiction` as an indexed field in lunr.py so searching "Broward" returns Broward datasets.
**When to use:** In `search_index.py` `build_search_index()`.
**Example:**

```python
# In build_search_index(), add to documents:
documents.append({
    "id": slug,
    "title": title,
    "description": description,
    "keywords": keywords,
    "department": department,
    "category": category,
    "jurisdiction": jurisdiction_display_name,  # NEW
})

# In lunr() call, add field:
idx = lunr(
    ref="id",
    fields=[
        {"field_name": "title", "boost": 10},
        {"field_name": "keywords", "boost": 8},
        {"field_name": "jurisdiction", "boost": 5},  # NEW
        {"field_name": "description", "boost": 5},
        {"field_name": "department", "boost": 3},
        {"field_name": "category", "boost": 3},
    ],
    documents=documents,
)
```

Also add jurisdiction to `search_data` so it can be displayed in search results:
```python
search_data[slug] = {
    "title": title,
    "snippet": snippet,
    "department": department,
    "jurisdiction": jurisdiction_display_name,  # NEW
    "url": f"{base_url}/dataset/{slug}/",
    "grade": ds.get("letter_grade") or "",
}
```

### Pattern 4: CI Pipeline Update
**What:** Update the GitHub Actions workflow for multi-jurisdiction pull with optional enrichment.
**When to use:** The `encyclopedia.yml` workflow file.
**Key changes:**

```yaml
on:
  schedule:
    - cron: '0 6 * * 1'  # Weekly Monday 6:00 UTC
  workflow_dispatch:
    inputs:
      enrich_ai:
        description: 'Run AI enrichment (dataset + field descriptions)'
        type: boolean
        default: false
      skip_enrichment:
        description: 'Skip the enrichment step entirely'
        type: boolean
        default: false
      force_enrich:
        description: 'Override 25-dataset threshold and enrich all'
        type: boolean
        default: false
```

Pipeline steps:
1. `mdc-encyclopedia pull` (already pulls all jurisdictions by default)
2. `mdc-encyclopedia audit`
3. `mdc-encyclopedia diff || true`
4. (Conditional) `mdc-encyclopedia enrich` + `mdc-encyclopedia enrich-fields` -- only on manual dispatch with `enrich_ai: true`
5. Commit database
6. `mdc-encyclopedia export` with `--site-url`
7. Upload + Deploy to Pages

### Anti-Patterns to Avoid
- **Don't add server-side jurisdiction pages:** Don't create `/browse/jurisdiction/miami-dade/` routes. Client-side filtering on the existing browse page is simpler and consistent with how format/publisher/tag work.
- **Don't duplicate jurisdiction display_name in the database:** The registry YAML already maps slugs to display names. Compute display names at render time by passing registry data to the template context.
- **Don't hardcode jurisdiction colors in templates:** Use CSS classes keyed by jurisdiction slug, not inline styles.
- **Don't create separate CI workflows per jurisdiction:** The `pull` command already loops over all jurisdictions with failure isolation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Search indexing | Custom search algorithm | lunr.py + Lunr.js (already integrated) | Full-text search with stemming, boosting, wildcards |
| CI deployment | Manual deploy script | actions/deploy-pages@v4 (already working) | Handles artifact upload, caching, atomic deploys |
| Jurisdiction registry | Hardcoded jurisdiction list | jurisdictions.yaml + registry.py (already built) | Single source of truth, extensible for future jurisdictions |
| Filter UI | Custom dropdown widget | Native HTML `<select>` + existing filter.js pattern | Accessible, works without JS, consistent with existing UX |

**Key insight:** Every component needed for this phase already exists in the codebase. The work is wiring jurisdiction data into existing patterns, not building new systems.

## Common Pitfalls

### Pitfall 1: Jurisdiction Display Name vs Slug Confusion
**What goes wrong:** Using raw jurisdiction slugs (e.g., "miami-dade") in user-facing text instead of display names ("Miami-Dade County").
**Why it happens:** The DB stores slugs, templates render what they're given.
**How to avoid:** In `generator.py`, load the jurisdiction registry and build a `jurisdiction_display_name` lookup dict. Pass it to templates or compute `ds["jurisdiction_display_name"]` in `_build_dataset_context()`.
**Warning signs:** UI showing "miami-dade" instead of "Miami-Dade County".

### Pitfall 2: CI Pipeline Fails Silently on One Jurisdiction
**What goes wrong:** If Broward's portal is down, the `pull` command may exit 0 but produce incomplete data. The site builds without Broward datasets.
**Why it happens:** The pull command catches per-jurisdiction errors and continues.
**How to avoid:** The pull command already prints a summary table with status per jurisdiction. In CI, capture the summary output. The CONTEXT.md decision says "flag failures in workflow summary/logs" -- use `>> $GITHUB_STEP_SUMMARY` to surface errors.
**Warning signs:** Dataset count drops between runs.

### Pitfall 3: Filter.js Doesn't Account for New Dropdown
**What goes wrong:** Adding the jurisdiction `<select>` to HTML but forgetting to wire it into `filter.js`'s `applyFilters()` function. Dropdown appears but does nothing.
**Why it happens:** Template and JS are separate files; easy to update one without the other.
**How to avoid:** Update template, JS, and CSS together as a single unit of work.
**Warning signs:** Jurisdiction dropdown shows but selecting a value doesn't filter.

### Pitfall 4: Search Index Bloat from Redundant Jurisdiction Text
**What goes wrong:** Indexing jurisdiction slug AND display name AND abbreviations, causing the search index to grow unnecessarily.
**Why it happens:** Trying to be thorough with search coverage.
**How to avoid:** Index the display name only (e.g., "Miami-Dade County"). Lunr's stemming and partial matching handle variations. Users searching "miami" will match "Miami-Dade County".
**Warning signs:** Search index JSON grows significantly after adding one field.

### Pitfall 5: Enrichment Runs on Every Scheduled CI Run
**What goes wrong:** Scheduled weekly runs trigger AI enrichment, consuming API credits unnecessarily.
**Why it happens:** The CONTEXT.md decision is explicit: enrichment is "skipped on scheduled runs, available as a boolean input on manual dispatch."
**How to avoid:** Gate enrichment behind `inputs.enrich_ai == 'true'` AND `github.event_name == 'workflow_dispatch'`.
**Warning signs:** Anthropic API costs spike after CI schedule activates.

### Pitfall 6: `data-jurisdiction` Attribute Missing from Dataset Rows
**What goes wrong:** The filter dropdown exists but rows lack the `data-jurisdiction` attribute, so JavaScript can't match them.
**Why it happens:** Updating the `<select>` dropdown in `browse.html` but forgetting to add the data attribute to the `dataset-row` div.
**How to avoid:** Template changes for filters always require both the dropdown AND the data attribute on each row.
**Warning signs:** All datasets disappear when selecting a jurisdiction filter.

## Code Examples

Verified patterns from the existing codebase:

### Adding Filter Options in generator.py
Source: `src/mdc_encyclopedia/site/generator.py` lines 256-281
```python
# Existing _extract_filter_options pattern -- extend to include jurisdictions
def _extract_filter_options(datasets):
    formats = set()
    publishers = set()
    tags = set()
    jurisdictions = set()

    for ds in datasets:
        # ... existing format/publisher/tag extraction ...
        j = (ds.get("jurisdiction") or "").strip()
        if j:
            jurisdictions.add(j)

    return list(formats), list(publishers), list(tags), list(jurisdictions)
```

### Adding Jurisdiction to Lunr Index
Source: `src/mdc_encyclopedia/site/search_index.py` lines 40-82
```python
# Existing document building pattern -- add jurisdiction field
jurisdiction = ds.get("jurisdiction") or ""
# Map slug to display name for searchability
jurisdiction_name = jurisdiction_display_names.get(jurisdiction, jurisdiction)

documents.append({
    "id": slug,
    "title": title,
    "description": description,
    "keywords": keywords,
    "department": department,
    "category": category,
    "jurisdiction": jurisdiction_name,  # NEW
})
```

### CI Workflow Enrichment Gating
Source: `.github/workflows/encyclopedia.yml`
```yaml
- name: Enrich new datasets (manual dispatch only)
  if: >-
    github.event_name == 'workflow_dispatch' &&
    inputs.enrich_ai == 'true'
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  run: |
    mdc-encyclopedia enrich --model claude-haiku-4-5-20251001
    mdc-encyclopedia enrich-fields --model claude-haiku-4-5-20251001 --resume
```

### Jurisdiction Badge in Browse Template
Source pattern: `src/mdc_encyclopedia/site/templates/browse.html` lines 58-61
```html
<!-- Existing department chip pattern, adapted for jurisdiction -->
<div class="dataset-meta">
    {% if ds.jurisdiction_display_name %}
    <span class="jurisdiction-badge jurisdiction-{{ ds.jurisdiction|default('unknown') }}">
        {{ ds.jurisdiction_display_name }}
    </span>
    {% endif %}
    {% if ds.department %}
    <span class="chip">{{ ds.department }}</span>
    {% endif %}
</div>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| peaceiris/actions-gh-pages (push to branch) | actions/deploy-pages@v4 (artifact-based) | 2023 | Already using current approach. Atomic deployments via artifact API. |
| Single-jurisdiction pull | Multi-jurisdiction pull (Phase 8) | Phase 8 (this project) | `mdc-encyclopedia pull` already loops all jurisdictions. |
| No search index | lunr.py pre-built index | Phase 3 (this project) | Adding fields to existing index is trivial. |

**Deprecated/outdated:**
- `peaceiris/actions-gh-pages@v3`: Still works but project already uses the newer artifact-based approach via `deploy-pages@v4`. No reason to switch.

## Open Questions

1. **Jurisdiction display name resolution in templates**
   - What we know: Registry YAML maps slugs to display names. `_build_dataset_context` creates `dict(row)` which includes the `jurisdiction` slug from the DB.
   - What's unclear: Should we add `jurisdiction_display_name` inside `_build_dataset_context()` (requires registry access in context.py), or in `generator.py` when building page contexts?
   - Recommendation: Build the lookup dict in `generator.py` from the registry and inject `jurisdiction_display_name` into each dataset dict before passing to templates. This keeps `context.py` DB-only and `generator.py` as the orchestrator. **Confidence: HIGH** -- this follows the separation of concerns already in the codebase.

2. **Jurisdiction badge color assignment for future jurisdictions**
   - What we know: Three jurisdictions now (miami-dade, broward, miami). CSS class per slug works fine.
   - What's unclear: If more jurisdictions are added later, do we need a dynamic color assignment system?
   - Recommendation: Use CSS classes keyed by slug for the three known jurisdictions. Future jurisdictions get a generic `.jurisdiction-default` style. This is v1.1 scope; v1.2+ can revisit if needed. **Confidence: HIGH** -- YAGNI applies here.

3. **Footer and About page text updates for multi-jurisdiction**
   - What we know: Footer says "Data sourced from Miami-Dade County Open Data" and about page references Miami-Dade throughout.
   - What's unclear: Should these be updated in Phase 12 to reflect multi-jurisdiction?
   - Recommendation: Yes, update footer to "Data sourced from South Florida open data portals" and About page to mention all three jurisdictions. This is natural polish work within the phase scope. **Confidence: HIGH**

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `src/mdc_encyclopedia/site/generator.py`, `context.py`, `search_index.py`, `filter.js`, `browse.html`, `dataset.html`, `style.css`
- Codebase inspection: `.github/workflows/encyclopedia.yml`
- Codebase inspection: `src/mdc_encyclopedia/jurisdictions.yaml`, `registry.py`
- Codebase inspection: `src/mdc_encyclopedia/db.py` (schema V4 with jurisdiction column)
- Codebase inspection: `src/mdc_encyclopedia/cli.py` (pull command already multi-jurisdiction)

### Secondary (MEDIUM confidence)
- GitHub docs on `actions/deploy-pages@v4` and `actions/upload-pages-artifact@v4` -- confirmed v4 current and in use
- lunr.py 0.8.0 -- field dict format with `field_name` and `boost` keys verified from working codebase code

### Tertiary (LOW confidence)
- None -- all findings verified against the actual codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and working in the codebase
- Architecture: HIGH -- every pattern follows existing codebase conventions exactly
- Pitfalls: HIGH -- identified from direct code inspection of the patterns being modified

**Research date:** 2026-02-27
**Valid until:** 2026-03-27 (stable codebase, no external API dependencies for this phase)
