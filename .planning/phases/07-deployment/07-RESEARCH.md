# Phase 7: Deployment - Research

**Researched:** 2026-02-26
**Domain:** GitHub Actions CI/CD + GitHub Pages static site hosting
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Auto-enrich only if fewer than 25 new datasets are found in the pull
- If 25+ new datasets appear, skip enrichment and auto-create a GitHub issue ("25+ new datasets found, manual enrichment needed")
- Pin to Haiku model (`--model haiku`) in CI for cost savings -- user can run Sonnet manually for higher quality
- When no ANTHROPIC_API_KEY secret is set, skip enrichment entirely (no error)
- **Weekly cron:** Full pipeline -- pull, audit, diff, enrich (if under threshold and key exists), export, deploy
- **Push to master:** Export-only -- re-export site from current DB state and deploy (no pull, no enrich, fast)
- **Manual dispatch (workflow_dispatch):** Full pipeline with two input options:
  - `skip_enrichment` (boolean) -- skip the enrich step entirely
  - `force_enrich` (boolean) -- override the 25-dataset threshold and enrich all unenriched datasets
- Push-to-master should be fast -- just re-export and deploy, no API calls
- The GitHub issue created when enrichment is skipped should be actionable: include the count of new datasets and a suggested command to run manually

### Claude's Discretion
- Cron schedule timing (day of week, hour)
- GitHub Pages deployment method (gh-pages branch vs actions artifact)
- Workflow job structure (single job vs matrix)
- How to persist SQLite DB between workflow runs (artifact caching strategy)
- Error handling and retry logic for API calls in CI

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEPLOY-01 | Static site deploys to GitHub Pages | Use `actions/upload-pages-artifact@v4` + `actions/deploy-pages@v4` with artifact-based deployment (modern approach, no gh-pages branch needed) |
| DEPLOY-02 | GitHub Actions workflow runs weekly (pull + auto-enrich new + audit + export + deploy) | Cron schedule trigger + workflow_dispatch + push trigger; pipeline logic orchestrated by shell steps calling `mdc-encyclopedia` CLI commands |
| DEPLOY-03 | ANTHROPIC_API_KEY handled as GitHub Secret (optional -- workflow runs without it, skipping enrichment) | Check `${{ secrets.ANTHROPIC_API_KEY }}` existence in conditional step; CLI already raises ValueError when key missing, workflow catches and skips gracefully |
</phase_requirements>

## Summary

This phase creates a GitHub Actions workflow that automates the full encyclopedia pipeline (pull, audit, diff, conditional enrich, export) and deploys the generated static site to GitHub Pages. The core technical challenge is **persisting the SQLite database between workflow runs** so that each weekly pull builds on previous data rather than starting fresh.

The recommended approach uses **artifact-based GitHub Pages deployment** (`actions/upload-pages-artifact@v4` + `actions/deploy-pages@v4`) which is the modern standard -- no `gh-pages` branch management needed. For database persistence, the recommended approach is **committing the SQLite database to the repository** via `git add/commit/push` within the workflow, which provides reliable, auditable persistence with full history.

**Primary recommendation:** Single workflow file with three triggers (cron, push, workflow_dispatch), conditional step logic using shell conditionals, and the DB committed to the repo for persistence.

## Standard Stack

### Core
| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| `actions/checkout@v5` | v5 | Clone repository | Standard first step in any workflow |
| `actions/setup-python@v5` | v5 | Install Python 3.10+ | Required to run CLI; supports pip caching |
| `actions/upload-pages-artifact@v4` | v4 | Package site/ directory for Pages | Official GitHub action for Pages artifact upload |
| `actions/deploy-pages@v4` | v4 | Deploy artifact to GitHub Pages | Official GitHub action for Pages deployment |
| `actions/cache@v4` | v4 | Cache pip dependencies | Speeds up Python dependency install |

### Supporting
| Component | Purpose | When to Use |
|-----------|---------|-------------|
| `gh` CLI (pre-installed) | Create GitHub issues from workflow | When 25+ new datasets trigger enrichment skip |
| `git` (pre-installed) | Commit DB changes back to repo | After pull/enrich/audit steps modify the database |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Artifact-based Pages deploy | `gh-pages` branch via `peaceiris/actions-gh-pages` | gh-pages branch adds branch clutter; artifact approach is official and cleaner |
| DB committed to repo | `actions/cache` for DB persistence | Cache evicts after 7 days of inactivity and has 10GB repo limit; cache misses mean lost data. Committing to repo is durable and auditable |
| DB committed to repo | GitHub release artifact | Overly complex for a single SQLite file; harder to restore |

## Architecture Patterns

### Recommended Workflow Structure
```
.github/
  workflows/
    encyclopedia.yml    # Single workflow file with all three triggers
```

### Pattern 1: Conditional Step Execution via Shell
**What:** Use shell `if/else` blocks within `run:` steps rather than GitHub Actions `if:` conditions for complex pipeline logic. This keeps the workflow readable and avoids YAML complexity.
**When to use:** When conditional logic depends on runtime values (e.g., count of new datasets, presence of API key).
**Example:**
```yaml
- name: Enrich new datasets (conditional)
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  run: |
    if [ -z "$ANTHROPIC_API_KEY" ]; then
      echo "No ANTHROPIC_API_KEY set, skipping enrichment"
      exit 0
    fi
    # Count new datasets from diff output
    NEW_COUNT=$(mdc-encyclopedia diff --latest 2>/dev/null | grep -c "Added" || echo "0")
    if [ "$NEW_COUNT" -ge 25 ] && [ "${{ github.event.inputs.force_enrich }}" != "true" ]; then
      echo "25+ new datasets ($NEW_COUNT), skipping enrichment and creating issue"
      gh issue create \
        --title "Manual enrichment needed: $NEW_COUNT new datasets" \
        --body "The weekly pull found $NEW_COUNT new datasets (threshold: 25). Run manually: \`mdc-encyclopedia enrich --model claude-sonnet-4-5-20250929\`" \
        --label "enrichment"
      exit 0
    fi
    mdc-encyclopedia enrich --model claude-haiku-4-5-20251001
```

### Pattern 2: Trigger-Based Pipeline Branching
**What:** Use `github.event_name` to determine which pipeline steps to run.
**When to use:** When different triggers require different pipeline stages.
**Example:**
```yaml
- name: Pull latest data
  if: github.event_name != 'push'  # Skip pull on push-to-master
  run: mdc-encyclopedia pull

- name: Export site
  run: mdc-encyclopedia export -o site  # Always runs
```

### Pattern 3: DB Persistence via Git Commit
**What:** After the pipeline modifies the SQLite DB, commit it back to the repo.
**When to use:** After pull/enrich/audit steps in the cron or manual dispatch triggers. NOT on push-to-master (to avoid infinite loops).
**Example:**
```yaml
- name: Commit updated database
  if: github.event_name != 'push'
  run: |
    git config user.name "github-actions[bot]"
    git config user.email "github-actions[bot]@users.noreply.github.com"
    git add mdc_encyclopedia.db
    git diff --staged --quiet || git commit -m "chore: update encyclopedia database [skip ci]"
    git push
```

### Anti-Patterns to Avoid
- **Using `actions/cache` for database persistence:** Cache entries expire after 7 days of inactivity and are scoped to branches. If the cron job fails for two consecutive weeks, the database is lost permanently. Committing to the repo is durable.
- **Triggering infinite push loops:** A workflow that commits to `master` will re-trigger the `push` event. Use `[skip ci]` in the commit message or make the push-to-master path skip the commit step.
- **Interactive prompts in CI:** The `enrich` command has a `click.confirm` when cost > $5. With Haiku model on <25 datasets, cost will be well under $5 (estimated <$0.05), so the auto-proceed path is taken. No CLI change needed for v1.
- **Running the full pipeline on push:** Push-to-master should only re-export and deploy. Running pull/enrich on every push wastes API calls and time.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| GitHub Pages deployment | Custom `gh-pages` branch management scripts | `actions/upload-pages-artifact@v4` + `actions/deploy-pages@v4` | Official actions handle artifact packaging, permissions, and deployment atomically |
| Issue creation | Custom GitHub API calls via `curl` | `gh issue create` CLI (pre-installed on runners) | Simpler, handles auth via GH_TOKEN env var, less error-prone |
| Python setup + caching | Manual `apt-get` + pip | `actions/setup-python@v5` with `cache: 'pip'` | Handles version management, virtual environments, and pip caching in one step |
| Push-back to repo | Custom `curl` to Git API | `git add/commit/push` with bot user config | Git is pre-installed, straightforward, and creates auditable history |

**Key insight:** GitHub Actions runners come with `git`, `gh`, Python, and all needed tools pre-installed. The workflow is essentially a shell script with conditional logic calling the existing `mdc-encyclopedia` CLI commands.

## Common Pitfalls

### Pitfall 1: Infinite Push Loop
**What goes wrong:** Workflow commits DB to master, which triggers the `push` event, which runs the workflow again (export-only path), which potentially commits again.
**Why it happens:** The `push` trigger fires on every push to master, including commits made by the workflow itself.
**How to avoid:** Two complementary strategies:
1. Include `[skip ci]` in the bot's commit message to suppress workflow triggers.
2. In the push-to-master path, do NOT commit anything -- only export and deploy.
**Warning signs:** Workflow runs appearing in pairs or chains in the Actions tab.

### Pitfall 2: GitHub Pages Not Enabled in Repository Settings
**What goes wrong:** The deploy-pages action fails with a permissions error.
**Why it happens:** GitHub Pages must be manually configured in the repo settings to use "GitHub Actions" as the source (not "Deploy from a branch").
**How to avoid:** Document the one-time setup: Repository Settings > Pages > Source > "GitHub Actions".
**Warning signs:** Error message "Pages is not enabled for this repository" or "Not Found" deployment error.

### Pitfall 3: Database Path Mismatch Between Local and CI
**What goes wrong:** The CLI creates the DB at `~/.local/share/mdc-encyclopedia/mdc_encyclopedia.db` (XDG default) in CI, but we need it at a known path in the repo for git commit.
**Why it happens:** The `MDC_ENCYCLOPEDIA_DB` env var must be explicitly set to a path within the repo checkout.
**How to avoid:** Set `MDC_ENCYCLOPEDIA_DB=./mdc_encyclopedia.db` in the workflow environment so the DB lives in the repo root.
**Warning signs:** "No datasets found" errors after pull, or DB not appearing in `git status`.

### Pitfall 4: Permissions for Pages + Issues
**What goes wrong:** Workflow fails at deploy or issue creation with 403/permission errors.
**Why it happens:** The GITHUB_TOKEN needs specific permission scopes: `pages: write`, `id-token: write`, `contents: write` (for git push), and `issues: write` (for gh issue create).
**How to avoid:** Declare all needed permissions at the workflow level.
**Warning signs:** "Resource not accessible by integration" errors.

### Pitfall 5: Cron Schedule Not Running
**What goes wrong:** The scheduled workflow never fires.
**Why it happens:** GitHub disables scheduled workflows on repos with no activity for 60 days. Also, cron schedules run on the default branch only.
**How to avoid:** Ensure the workflow file is on the `master` branch (the default). If the repo goes quiet, any manual push or workflow_dispatch reactivates cron.
**Warning signs:** No scheduled workflow runs in the Actions tab after the expected time.

### Pitfall 6: Cost Confirmation Prompt Blocking CI
**What goes wrong:** The `enrich` command hangs waiting for user input because cost exceeds $5.
**Why it happens:** `click.confirm()` blocks on stdin in CI (no TTY).
**How to avoid:** With Haiku model on <25 datasets, estimated cost is ~$0.01-$0.05, well under the $5 auto-proceed threshold. The 25-dataset cap + Haiku model makes this safe. If a future scenario needs forced confirmation bypass, add a `--yes` flag to the CLI.
**Warning signs:** Workflow step hanging indefinitely with no output.

### Pitfall 7: Branch Name Mismatch
**What goes wrong:** Workflow triggers reference `main` but the repo uses `master`.
**Why it happens:** Many workflow examples default to `main`.
**How to avoid:** This repo's default branch is `master`. All trigger configurations must reference `master`, not `main`.
**Warning signs:** Workflow never triggers on push.

## Code Examples

### Complete Workflow Skeleton
```yaml
# Source: Composed from official GitHub Actions docs + project-specific CLI
name: Encyclopedia Pipeline

on:
  schedule:
    - cron: '0 6 * * 1'  # Every Monday at 6:00 UTC
  push:
    branches: [master]
  workflow_dispatch:
    inputs:
      skip_enrichment:
        description: 'Skip the enrichment step entirely'
        type: boolean
        default: false
      force_enrich:
        description: 'Override 25-dataset threshold and enrich all'
        type: boolean
        default: false

permissions:
  contents: write    # For git push (DB commit)
  pages: write       # For GitHub Pages deploy
  id-token: write    # Required by deploy-pages
  issues: write      # For auto-creating issues

concurrency:
  group: "pages"
  cancel-in-progress: false

env:
  MDC_ENCYCLOPEDIA_DB: ./mdc_encyclopedia.db
  PYTHON_VERSION: '3.12'

jobs:
  pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install package
        run: pip install .

      # --- Full pipeline (cron + manual dispatch only) ---
      - name: Pull latest data
        if: github.event_name != 'push'
        run: mdc-encyclopedia pull

      - name: Run audit
        if: github.event_name != 'push'
        run: mdc-encyclopedia audit

      - name: Detect changes
        if: github.event_name != 'push'
        run: mdc-encyclopedia diff || true

      - name: Enrich new datasets (conditional)
        if: github.event_name != 'push'
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          # ... conditional enrichment logic (see Pattern 1 above)

      - name: Commit database updates
        if: github.event_name != 'push'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add mdc_encyclopedia.db
          git diff --staged --quiet || git commit -m "chore: update encyclopedia database [skip ci]"
          git push

      # --- Export + Deploy (all triggers) ---
      - name: Export static site
        run: mdc-encyclopedia export -o site

      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v4
        with:
          path: site/

  deploy:
    needs: pipeline
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

### GitHub Issue Creation for Enrichment Skip
```yaml
# Source: GitHub CLI docs for Actions
- name: Create enrichment issue
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    gh issue create \
      --title "Manual enrichment needed: $NEW_COUNT new datasets" \
      --body "$(cat <<EOF
    ## Auto-enrichment skipped

    The weekly pull on $(date -u +%Y-%m-%d) found **$NEW_COUNT new datasets**, exceeding the 25-dataset threshold.

    ### Suggested action
    \`\`\`bash
    mdc-encyclopedia enrich --model claude-sonnet-4-5-20250929
    \`\`\`

    Or to enrich with the CI model:
    \`\`\`bash
    mdc-encyclopedia enrich --model claude-haiku-4-5-20251001
    \`\`\`
    EOF
    )"
```

### Counting New Datasets from Diff
```bash
# The diff command outputs Rich-formatted tables to stdout.
# To count new datasets programmatically, query the DB directly:
NEW_COUNT=$(python3 -c "
import sqlite3, os
conn = sqlite3.connect(os.environ['MDC_ENCYCLOPEDIA_DB'])
conn.row_factory = sqlite3.Row
# Count 'added' changes from the most recent batch
row = conn.execute('''
    SELECT COUNT(*) as cnt FROM changes
    WHERE change_type = \"added\"
    AND detected_at = (SELECT MAX(detected_at) FROM changes)
''').fetchone()
print(row['cnt'] if row else 0)
conn.close()
")
echo "New datasets found: $NEW_COUNT"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Deploy from `gh-pages` branch | Deploy from Actions artifact (`upload-pages-artifact` + `deploy-pages`) | 2022-2023 | No branch management, cleaner history, official support |
| `peaceiris/actions-gh-pages` third-party action | Official `actions/deploy-pages@v4` | 2023 | First-party support, tighter integration, no third-party dependency |
| `actions/upload-pages-artifact@v3` | `actions/upload-pages-artifact@v4` | Aug 2025 | Latest stable version |
| `actions/checkout@v4` | `actions/checkout@v5` | 2024-2025 | Node 20+ runtime, performance improvements |

**Deprecated/outdated:**
- `gh-pages` branch approach: Still works but is the legacy pattern. Artifact-based deployment is the recommended approach for new projects.
- `actions/upload-pages-artifact@v1-v3`: Superseded by v4. Use v4 for latest features and Node runtime compatibility.

## Open Questions

1. **Database file size over time**
   - What we know: The SQLite DB contains ~476 datasets (based on the site/ directory count). File size is currently unknown but likely <10MB.
   - What's unclear: Growth rate over time as changes accumulate in the `changes` table.
   - Recommendation: Start with committing to repo (GitHub supports files up to 100MB). Monitor file size. If it grows past ~50MB, consider periodic VACUUM or archiving old change records.

2. **Enrich command interactive confirmation in edge cases**
   - What we know: The `click.confirm` prompt triggers only when estimated cost exceeds $5. With Haiku model on <25 datasets, cost is ~$0.01-$0.05.
   - What's unclear: Whether any edge case could push cost over $5 in the CI path (e.g., very large dataset metadata).
   - Recommendation: Proceed with current approach for v1. The 25-dataset threshold combined with Haiku pricing makes $5+ cost virtually impossible. If needed, add a `--yes` flag later.

3. **GitHub Pages source configuration**
   - What we know: Repository Settings > Pages > Source must be set to "GitHub Actions" (not "Deploy from a branch") for the artifact-based deploy to work.
   - What's unclear: Whether this can be configured programmatically or requires manual repo setup.
   - Recommendation: Document as a one-time manual setup step. It's a single toggle in repo settings.

## Discretion Recommendations

Based on research, here are recommendations for areas left to Claude's discretion:

### Cron Schedule Timing
**Recommendation:** Monday at 06:00 UTC (01:00 AM EST / 02:00 AM EDT)
**Rationale:** Monday catches weekend data updates. Early morning EST avoids peak API traffic and gives the maintainer a fresh weekly report at start of work week. UTC is the standard for cron in GitHub Actions.

### GitHub Pages Deployment Method
**Recommendation:** Artifact-based deployment (`upload-pages-artifact` + `deploy-pages`)
**Rationale:** This is the official, modern approach. No `gh-pages` branch to manage, no force pushes, cleaner git history. Requires one-time repo settings change to set Pages source to "GitHub Actions".

### Workflow Job Structure
**Recommendation:** Two jobs: `pipeline` (build + export) and `deploy` (Pages deployment)
**Rationale:** The `deploy` job needs a separate `environment: github-pages` declaration for proper Pages integration. Keeping it as a separate job follows GitHub's recommended pattern and provides clear deployment status in the UI.

### SQLite DB Persistence Strategy
**Recommendation:** Commit the database file to the repository
**Rationale:** `actions/cache` evicts after 7 days of inactivity (dangerous for a weekly cron), has a 10GB repo limit, and provides no audit trail. Committing the DB to the repo is durable, auditable, and simple. The DB file size should remain well under GitHub's 100MB file limit. Use `[skip ci]` in the commit message to prevent infinite push loops.

### Error Handling and Retry Logic
**Recommendation:** Let the CLI's built-in retry logic (tenacity, httpx retries) handle transient failures. Use `|| true` on the `diff` command (which may exit non-zero on first run). Let the workflow fail visibly on hard errors so the maintainer can investigate via GitHub Actions notifications.
**Rationale:** Over-engineering retry logic in the workflow YAML adds complexity. The CLI already has retry logic for API calls (tenacity with 5 retries in the enrichment client). Workflow-level retries would just retry the same failing request.

## Sources

### Primary (HIGH confidence)
- `actions/upload-pages-artifact` README (v4.0.0, Aug 2025) -- inputs: `path`, `name`, `retention-days`
- `actions/deploy-pages` README (v4.0.5) -- inputs: `token`, `timeout`, `artifact_name`; outputs: `page_url`
- `actions/cache` README (v4/v5) -- restore/save patterns, cache key strategies
- GitHub Actions docs: workflow syntax (permissions, schedule, workflow_dispatch, concurrency)
- GitHub CLI docs: `gh issue create` in workflows with `GH_TOKEN` env var

### Secondary (MEDIUM confidence)
- Simon Willison's TIL on GitHub Pages deployment with Actions -- verified minimal working pattern
- GitHub docs on configuring Pages publishing source -- confirms "GitHub Actions" source option
- devmedeiros.com SQLite persistence guide -- verified git commit pattern for DB persistence

### Tertiary (LOW confidence)
- karlhorky/github-actions-database-persistence repo -- SQLite approach was "TODO" but cache limitations documented (7-day eviction, 10GB limit)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all actions are official GitHub first-party, versions verified from README/release pages
- Architecture: HIGH -- workflow pattern is well-established, project CLI already handles all pipeline steps
- Pitfalls: HIGH -- each pitfall identified from real failure modes documented in Stack Overflow and GitHub community discussions
- DB persistence: MEDIUM -- committing DB to repo is the pragmatic choice but monitoring file size is recommended

**Research date:** 2026-02-26
**Valid until:** 2026-03-26 (stable domain, 30 days)
