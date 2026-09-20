# Profiles redesign report

## Workspace and scope

Worktree: `C:\dev\btx-omni-prospect-redesign`; branch: `redesign/profiles-screen`; starting commit: `a23da6e`. Created with `git worktree add` from committed `codex/linkedin-relationship-ingestion`. First target succeeded; no fallback required. Initial status was clean. Original Communications work was not changed.

App.tsx will need integration review when merging the Communications work (including `wip/communications-snapshot`). Its shared resource loading, content rendering, and account-detail props are the likely conflict areas. Redesign App.tsx changes: none yet.

## Copied local files

Only ignored environment files were required. Values are intentionally not recorded. SHA256 before and after were identical:

| File | Before SHA256 | After SHA256 |
|---|---|---|
| apps/web/.env | 02B159933D30B0BDDFE32348094AEF757C55D149267326FE05900EE9FEB558C3 | 02B159933D30B0BDDFE32348094AEF757C55D149267326FE05900EE9FEB558C3 |
| apps/web/.env.local | AC80360E460169C0A1BA854194C2CA57BE9488B69B0D87BFE300EC9E0984A134 | AC80360E460169C0A1BA854194C2CA57BE9488B69B0D87BFE300EC9E0984A134 |
| backend/.env | 9BF907EB6864BB784F77BE6521F582D9AFCC0262B6765DEB3763DCE9A24F5A2B | 9BF907EB6864BB784F77BE6521F582D9AFCC0262B6765DEB3763DCE9A24F5A2B |

The private workbook reference is tracked and was checked out from Git, not copied over. No untracked seed/import source was found. Old acceptance SQLite databases were excluded: they are previous test outputs, not authoritative seed inputs. Local runs explicitly override database and AI settings; copied credentials are not used for external operations.

## Blocker log

| Blocker | Root cause/evidence | Action and result |
|---|---|---|
| Previous invalid working directory | Target did not exist | Created isolated worktree successfully |
| Previous fixture hash failures | Clean HEAD and worktree bytes now both match pinned hashes; no BOM, no CRLF, no content diff | No pinned data or checksums changed. Commercial SHA256 `b9ff27965e2716abab313f840de903191617c4da24d8fd8df7bf999c868bcd2e`; reference SHA256 `d0e4a1ca28d5f6ec38edd457b81fe98177d5b9d5396ac582b6bf34e9901e55d7`. Earlier original-working-copy root cause remains unverified; no repair there attempted. |
| E2E startup | New isolated database has no `commercial_account_profiles` table; prior runtime rejected empty imported records | Bootstrap local schema and import using existing validated repositories; verification pending |
| Customer Health bands | Scoring service has no health band or thresholds; public signal/risk bands are different families | Preserve score and coverage; expose unavailable health band rather than invent rubric thresholds |

## Baseline

`npm ci`: 157 packages, zero audit vulnerabilities. `uv sync --frozen` with `UV_LINK_MODE=copy`: succeeded, local backend/.venv.

Current frontend/backend baseline runs are in progress. Earlier 82 versus 84 frontend tests: two subsequently committed tests account for the difference: relationship loading (`ec229ca`) and network contacts (`68cb633`). Communications tests in the original dirty folder are excluded by the committed worktree.

Initial Playwright: failed before tests, missing local commercial schema. Dedicated ports 8127/5327 avoid the original server.

## Changes and DTO additions

Files added so far: this report; local bootstrap utility. No production configuration, dependencies, fixtures, scoring rules, or API shapes changed yet.

Tests changed: none.

## Step 1 — local environment verified

The local bootstrap imports 3,647 records for 11 canonical accounts using the existing hash-validated import and reference repositories. The original startup failure was an empty database, not an invalid release package. A first bootstrap attempt referenced a nonexistent monitor metadata export; corrected to the application's shared SQLAlchemy metadata. No migrations or fixture edits.

Backend serves on 8128; frontend on 5328; E2E uses 8127/5327. All database URLs are repository-local SQLite files, never production. Windows npm argument forwarding dropped Vite host flags: direct invocation of the installed Vite CLI fixes startup. Playwright's API base is explicitly local `/api`.

| Verification | Initial baseline | After environment repairs |
|---|---|---|
| Typecheck | PASS | PASS |
| Lint | PASS | PASS |
| Build | PASS | PASS |
| Frontend unit | 84 passed, 0 failed | 84 passed, 0 failed |
| Full backend (SQLite, copied durable settings) | 779 passed, 34 failed, 10 errors, 2 skipped | Isolated non-durable rerun pending |
| Profile/backend/reference focused | Initial result not retained | 18 passed, 0 failed with non-durable test settings |
| Focused profile E2E | Startup failure, then 2 passed / 2 failed | 4 passed, 0 failed |

The two E2E failures were ENOENT for a hardcoded other-user macOS screenshot destination. Changed only screenshot destinations in `profile-opportunity-scope.spec.mjs` to `testInfo.outputPath`; no assertions removed or weakened. Database-dependent full-suite verification remains partially UNVERIFIED: SQLite cannot substitute for tests explicitly requiring PostgreSQL.

Baseline screenshots are in `baseline/`: list, Boeing Overview/Commercial/Intelligence/Relationships, prospect Intel. Actions has no baseline tab, so no fake Actions-tab screenshot was created. Commercial contains the pre-redesign actions UI.

Step 1 files: `apps/web/playwright.config.mjs`, `apps/web/e2e/profile-opportunity-scope.spec.mjs`, `apps/web/tools/redesign-capture.mjs`, `backend/tools/redesign_local.py`, this report, baseline PNGs and backend test output. No DTO additions. No App.tsx changes.

Dependency inspection: package.json has React and Google Maps but no chart library. Use native SVG/CSS plus text/table fallbacks, as requested.

## Phase 0 findings

Priority is `account.prospect_research_priority`, a seeded string sorted HIGH/MEDIUM/LOW in Accounts.tsx, not a computed score. Evidence is the list `truth_state` string returned in api/accounts.py based on research/scenario membership. Neither measures health or coverage. Strategic designation and growth/research shortlist currently live in Accounts.tsx AccountPlanningPanel, mapped to the Opportunities profile tab. Existing APIs enforce manager designation, reason length and version/idempotency controls.

Available canonical fields: `commercial_ledger.monthly_history[].revenue_minor/bookings_minor`, `ttm`, fulfillment `remaining_quantity` and raw line `unit_price_minor`, health `backlog_coverage.raw_value`, risk `pipeline.raw_value` (overdue share), `concentration.raw_value`, CRM `last_activity_at/owner_id`, `role_targets.contact_verified/verified_function`, `interactions.two_way/date`, `relationship_profile.expected_touch_days`, active `public_risk_events` and `CommercialAlert.status`. Expansion records are existing scoped commercial opportunities. Monthly history is already returned but not typed in TypeScript. All commercial sample provenance must remain visible.

## Unverified / remaining

- Steps 1–6 are in progress, not complete.
- Baseline screenshots and full suite results pending.
- Health bands cannot be assigned without an existing approved backend definition.
