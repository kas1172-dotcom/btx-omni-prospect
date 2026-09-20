# Profiles redesign report

## Completion verification — 2026-09-20

Local implementation and deterministic verification are complete. The earlier partial-delivery report below is retained as historical evidence and is superseded by this section.

| Check | Current result |
|---|---|
| Typecheck, lint, production build | PASS |
| Frontend units | 84 passed, 0 failed |
| Full backend | 824 passed, 1 timing-dependent test failure, 2 existing skips |
| Backend failure closure | Exact failed-run identity replaces an assumption about ordering equal timestamps; all 31 Monitor persistence tests passed. No backend production logic changed during this closure. |
| Full configured Chromium suite | 185 passed, 2 history-race failures, 0 skipped |
| Browser failure closure | Both failures fixed; all 14 history/profile journeys passed. All 187 configured cases have passing coverage across the full and closure runs. |
| Manual browser inspection | Account first page, Boeing Overview and retained decision context inspected; no browser errors |

The full backend run covered all 825 executable tests. Its one failure was closed by the focused 31-test run; this is not represented as a second full 825-test run. The two existing backend skips and the existing hosted-demo/public-collection browser exclusions were retained.

Completion changes:

- Fixed first-page initialization, global alphabetical pagination, and retained sorting when returning from a profile.
- Restored the saved private research shortlist filter and its typed Omni context.
- Preserved the original list return location when switching between organizations and prevented unchanged profile effects from overwriting a browser Back destination; shared fix `0e17a19`.
- Restored exact selected-assessment context, linked records, separate commercial scores, follow-up previews, and recorded decision evidence in their appropriate tabs and disclosures.
- Disabled Action and Communication submission until their selected canonical account is loaded, retaining draft and retry behavior.
- Preserved itinerary edits and added stops made while a save is in flight; shared fix `d5daa3a`.
- Combined Actions selection and filter navigation updates to prevent an update loop after converting a suggestion; shared fix `9c7a756`. The seller journey now also rejects browser errors.
- Updated legacy browser selectors to the accepted Profiles controls and explicitly opened retained disclosures. Canonical identity, permission, score, missingness, evidence, and retry assertions remain covered. Updated two stale API presentation assertions and made the persistence test inspect its exact run.

Verification used task-owned loopback PostgreSQL databases `btx_omni_e2e_coordinator_profiles_final` (browser) and `btx_omni_e2e_coordinator_profiles_unit` (backend). The existing import replay verified 3,647 commercial records, 474 reference rows, and the pinned historical G17 excerpt. No canonical fixture, checksum, score definition, migration, production setting, or external provider was changed. The final browser run used API port 8163 and web port 5363.

Receipts: [full browser run](completion/browser.txt), [browser history closure](completion/browser-history-closure.txt), [full backend run](completion/backend.txt), [backend closure](completion/backend-monitor-closure.txt), and [frontend checks](completion/frontend.txt). Screenshots: [first account page](completion/accounts-first-page.png), [Boeing Overview](completion/boeing-overview.png), [retained decision context](completion/boeing-recorded-context.png).

The earlier broad-browser failure count is not a valid before/after baseline because initial setup failed before execution; the current browser failure set is closed by the 14-test follow-up run. Earlier attempts (including 165 passed / 16 failed / 6 not run, followed by 24 of 25 corrected cases) led to the Actions navigation fix and fresh-database run. That run's two Today-return failures were subsequently fixed and verified without weakening their Back-navigation assertions.

Remaining release boundaries: hosted access, WebKit, real Google Maps/Gemini, and production behavior remain unverified. Missing health bands, person-level interaction dates, signal expiry timestamps, and incomplete relationship ranges remain explicitly unavailable because the current contracts do not supply approved values. This local completion does not introduce scoring policy or invent source data. Branch integration and deployment are separate.

## Historical implementation handoff

Everything below records the original six-step implementation and its then-current limitations. References below to an unchanged App.tsx, SQLite-only verification, outstanding Communications work, and a failing browser gate describe that earlier handoff, not the completed state above.

## Final summary — partial delivery, not release-qualified

The six implementation steps are present in this branch, with baseline and per-step screenshots. The Profiles-focused checks pass, but the full browser suite is red and several requested values cannot be supplied under the no-invention/no-scoring-policy-change guardrails. **Do not treat this as a fully verified end-to-end release.** Backend and frontend-unit failures did not increase; full-E2E regression equivalence is UNVERIFIED because its initial baseline failed before execution. No deployment, production configuration/database write, dependency addition, fixture/hash edit, migration, history rewrite, or original-working-copy edit was performed.

| Suite | Before | Final | Comparison |
|---|---|---|---|
| Typecheck | PASS | PASS | Unchanged |
| Lint | PASS | PASS | Unchanged |
| Build | PASS | PASS | Unchanged |
| Frontend units | 84 passed, 0 failed | 84 passed, 0 failed | Same count; removed-UI assertions updated |
| Full backend, normalized local settings | 788 passed, 25 failed, 10 errors, 2 skipped | 790 passed, 25 failed, 10 errors, 2 skipped | Two new passes; identical FAILED/ERROR test-name sets |
| Profiles/Relationships focused backend | Initial baseline not retained for this exact selection | 25 passed, 0 failed | Current verification, not a claimed baseline count |
| Focused Profiles E2E | Startup failed; repaired baseline selection 4 passed | Expanded final selection 27 passed, 0 failed | Expanded coverage, not 23 repaired baseline failures |
| Full configured E2E inventory | Startup failed before execution | 107 passed, 74 failed, 5 did not run | Red; no-increase claim UNVERIFIED |

Full E2E shard results: 1 = 20 passed / 27 failed; 2 = 23 passed / 21 failed / 5 did not run; 3 = 35 passed / 9 failed; 4 = 29 passed / 17 failed. Sum: 186 configured tests. Five tests did not run after an existing serial group failed; no new skip was introduced. The existing hosted-demo and public-monitor-collection exclusions were unchanged and those separate gates are UNVERIFIED. `full-e2e-shard-1.txt` through `full-e2e-shard-4.txt` retain exact failures and evidence paths. Shell logging wrappers returned successfully even when Playwright failed: the recorded test summaries above, not wrapper exit codes, determine status.

Failures include pre-branch stale navigation labels, expectations for removed decision/brief/filter UI that are **not all migrated in the broader legacy suite**, and unrelated Actions/Communications/Map/Intelligence expectations. Not all 74 failures have a verified pre-change comparison or root cause; they are not all claimed as baseline failures. This is outstanding verification/compatibility work, not a passing release gate. Scoring definitions, canonical data, privacy checks and unrelated test assertions were not changed to force green results.

The complete DTO additions are listed in Step 2; no later step adds backend fields. Remaining value/workflow limitations are enumerated below. App.tsx has no changes on this branch; Communications integration still needs review. Native SVG/CSS avoids new chart dependencies; the React review informed request cleanup, derived state and keyboard behavior. Local preview: frontend 5328, backend 8128, repository-local SAMPLE database only.

## Workspace and scope

Worktree: `C:\dev\btx-omni-prospect-redesign`; branch: `redesign/profiles-screen`; starting commit: `a23da6e`. Created with `git worktree add` from committed `codex/linkedin-relationship-ingestion`. First target succeeded; no fallback required. Initial status was clean. Original Communications work was not changed.

App.tsx will need integration review when merging the Communications work (including `wip/communications-snapshot`). Its shared resource loading, content rendering, and account-detail props are the likely integration areas. Redesign App.tsx changes: **none**, so there are no direct App.tsx edit conflicts from this branch. Account DTO types are additive.

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
| E2E startup | New isolated database has no `commercial_account_profiles` table; prior runtime rejected empty imported records | Bootstrapped local schema and imported using existing validated repositories; focused browser suites now start and execute |
| Customer Health bands | Scoring service has no health band or thresholds; public signal/risk bands are different families | Preserve score and coverage; expose unavailable health band rather than invent rubric thresholds |
| Windows frontend startup | npm forwarding dropped Vite host/port flags | Invoke the existing installed Vite entry point directly; local and E2E startup verified |
| Screenshot write failure | Existing profile test hardcoded another user's macOS directory | Replaced only its output destination with Playwright testInfo.outputPath; assertions retained |
| New legacy monthly projection error | Valid durable readback rows inherit ledger currency | Fixed the additive projection's fallback; unchanged legacy test passes and full backend failing names match baseline |
| Relationship workspace browser setup | Old setup toggled a now-open workspace closed; graph is now secondary | Updated navigation/setup helper only; unchanged graph/Omni/context assertions pass in final 27-test run |
| Full browser suite remains red | Logs show stale primary navigation labels (pre-branch App.tsx already says Profiles), old removed-panel selectors, and other surface expectations | Preserve logs and distinguish focused success from full-suite failures; do not claim all failures are pre-existing or that full E2E failure count did not increase |
| Slow serial broad browser verification | 186 tests, including 45–120 second unrelated selector timeouts | Interrupted serial attempt and reran the full inventory in four separate-database, single-worker shards, without changing tests or timeout limits |

## Baseline

`npm ci`: 157 packages, zero audit vulnerabilities. `uv sync --frozen` with `UV_LINK_MODE=copy`: succeeded, local backend/.venv.

Baseline results are recorded below. Earlier 82 versus 84 frontend tests: two subsequently committed tests account for the difference: relationship loading (`ec229ca`) and network contacts (`68cb633`). Communications tests in the original dirty folder are excluded by the committed worktree.

Initial Playwright: failed before tests, missing local commercial schema. Dedicated ports 8127/5327 avoid the original server.

## Changes and DTO additions

The per-step sections record changes and test reasons. Step 2 is the complete DTO addition list; subsequent steps add no backend fields. No production configuration, dependencies, fixtures, scoring rules, or existing response fields were changed.

## Step 1 — local environment verified

The local bootstrap imports 3,647 records for 11 canonical accounts using the existing hash-validated import and reference repositories. The original startup failure was an empty database, not an invalid release package. A first bootstrap attempt referenced a nonexistent monitor metadata export; corrected to the application's shared SQLAlchemy metadata. No migrations or fixture edits.

Backend serves on 8128; frontend on 5328; E2E uses 8127/5327. All database URLs are repository-local SQLite files, never production. Windows npm argument forwarding dropped Vite host flags: direct invocation of the installed Vite CLI fixes startup. Playwright's API base is explicitly local `/api`.

| Verification | Initial baseline | After environment repairs |
|---|---|---|
| Typecheck | PASS | PASS |
| Lint | PASS | PASS |
| Build | PASS | PASS |
| Frontend unit | 84 passed, 0 failed | 84 passed, 0 failed |
| Full backend (SQLite, copied durable settings) | 779 passed, 34 failed, 10 errors, 2 skipped | Normalized baseline: 788 passed, 25 failed, 10 errors, 2 skipped |
| Profile/backend/reference focused | Initial result not retained | 18 passed, 0 failed with non-durable test settings |
| Focused profile E2E | Startup failure, then 2 passed / 2 failed | 4 passed, 0 failed |

The two E2E failures were ENOENT for a hardcoded other-user macOS screenshot destination. Changed only screenshot destinations in `profile-opportunity-scope.spec.mjs` to `testInfo.outputPath`; no assertions removed or weakened. Database-dependent full-suite verification remains partially UNVERIFIED: SQLite cannot substitute for tests explicitly requiring PostgreSQL.

Baseline screenshots are in `baseline/`: list, Boeing Overview/Commercial/Intelligence/Relationships, prospect Intel. Actions has no baseline tab, so no fake Actions-tab screenshot was created. Commercial contains the pre-redesign actions UI.

Step 1 files: `apps/web/playwright.config.mjs`, `apps/web/e2e/profile-opportunity-scope.spec.mjs`, `apps/web/tools/redesign-capture.mjs`, `backend/tools/redesign_local.py`, this report, baseline PNGs and backend test output. No DTO additions. No App.tsx changes.

Dependency inspection: package.json has React and Google Maps but no chart library. Use native SVG/CSS plus text/table fallbacks, as requested.

## Phase 0 findings

Priority is `account.prospect_research_priority`, a seeded string sorted HIGH/MEDIUM/LOW in Accounts.tsx, not a computed score. Evidence is the list `truth_state` string returned in api/accounts.py based on research/scenario membership. Neither measures health or coverage. Strategic designation and growth/research shortlist currently live in Accounts.tsx AccountPlanningPanel, mapped to the Opportunities profile tab. Existing APIs enforce manager designation, reason length and version/idempotency controls.

Available canonical fields: `commercial_ledger.monthly_history[].revenue_minor/bookings_minor`, `ttm`, fulfillment `remaining_quantity` and raw line `unit_price_minor`, health `backlog_coverage.raw_value`, risk `pipeline.raw_value` (overdue share), `concentration.raw_value`, CRM `last_activity_at/owner_id`, `role_targets.contact_verified/verified_function`, `interactions.two_way/date`, `relationship_profile.expected_touch_days`, active `public_risk_events` and `CommercialAlert.status`. Expansion records are existing scoped commercial opportunities. Monthly history is already returned but not typed in TypeScript. All commercial sample provenance must remain visible.

## Step 2 — canonical projections

List additions: `owner_id`, `business_unit_ids`, `naics` (original assignment objects including verification), `health_band` (null), `health_band_state`, `open_items.public/internal`, `bookings_monthly`, `bookings_delta_3m_vs_prior_3m`, `last_activity_at`.

Detail addition: `profile`, containing the same list fields plus `backlog_months`, `quote_overdue_share`, `concentration.share/evidence`, `open_order_count`, `open_order_value_minor`, `fulfillment`, `function_coverage`, `last_two_way_at`, `expected_touch_days`, `internal_commercial_risk`, `public_risk_rollup`, active `public_risk_events`, `overall_customer_risk`, `open_internal_items`, `expansion_opportunity_count`. Existing `commercial_ledger` is now typed, not duplicated or recomputed. Existing factor `raw_value/period` fields are now typed.

All scoring values use existing health/risk input calculations and assessment/rollup services. Open items are defined once in `profile_projection.py`: unique active public risk events; unique internal alerts with OPEN status. Counts are records known to the projection, not claims of complete public monitoring. Function coverage preserves role-only SAMPLE verification; no invented identified people. Missing is never inferred from incomplete research. Band thresholds remain unconfigured.

Verification: typecheck/lint/build PASS; frontend 84/84 unchanged; existing focused backend 18/18 plus new parity/reconciliation tests 2/2; focused E2E 4/4. New tests assert every sample list field equals the detail projection and commercial inputs equal existing scoring factors. Boeing's referenced line reconciles 292 ordered / 146 shipped / 146 remaining / 14,308,000 minor units ($143,080). This is one line, not the sum of all recorded account history. Initial new-test setup errors (missing Settings, then unenriched sample) fixed by constructing runtime with the existing validated commercial projection, without changing fixtures or assertions.

Full baseline after non-durable local test overrides: **788 passed / 25 failed / 10 errors / 2 skipped**, recorded in baseline-backend.txt. This is the comparison configuration for final full-suite verification. No test exclusions added. PostgreSQL-only verification remains UNVERIFIED.

Step 2 files: backend api/accounts.py; modules/accounts/profile_projection.py; tests/test_profile_projections.py (two new tests, no existing tests changed); frontend types/api.ts, types/decisions.ts, types/accountProfile.ts; report, test logs, step2 screenshots. App.tsx unchanged. Step2 Actions screenshot absent because no Actions tab exists yet.

## Step 3 — Accounts list

Replaced the old summary cards, Priority/Evidence columns and filter box. Native SVG bookings with expandable exact monthly values; coverage/ranges remain adjacent to scores. Added persisted All/Customers/Prospects/Needs attention/Strategic partners views and live counts, search/inline chips/additional filters, saved filter selection, density, row focus/arrow navigation/Enter, bounded pagination, monograms and per-row provenance tooltip. PUBLIC_MARKET now matches the backend's Prospect classification. Exact strategic filter labels retained. Health-band choice is explicitly Unavailable because the backend has no approved bands.

Tests changed: `poc-ui.test.mjs` semantic-list test now verifies the replacement columns and sort implementation; removed Priority/Evidence assertions replaced with absence assertions. Its list-context test's old curated-only filter-box assertions now verify the replacement All-view and canonical market filter, while preserving (and adding an explicit 50-row limit to) bounded Omni context checks. No unrelated surface assertions removed. Added `profiles-redesign.spec.mjs` for persistence, filtering, public/internal labels, coverage and keyboard entry.

Verification: typecheck/lint/build PASS; frontend unit 84 passed / 0 failed (unchanged count); focused backend 20 passed / 0 failed; existing focused profile E2E 4 passed / 0 failed. New list E2E result recorded below. Step3 screenshots captured for all existing tabs and Intel; no Actions tab yet. React best-practices review used versioned local storage, request cleanup, derived render state, no dependencies. Files: Accounts.tsx, Portfolio.tsx, ProfileMetrics.tsx, profiles-redesign.css, poc-ui.test.mjs, profiles-redesign.spec.mjs, report/screenshots.

List E2E initially counted nested sparkline table rows; corrected its new selector to direct account rows. The same check exposed and fixed arrow navigation selecting nested rows: navigation is now restricted to direct sibling account rows. Final new list E2E: 1 passed / 0 failed.

## Step 4 — header and Overview

Removed decision brief and Opportunities tab, added Actions tab. Existing manager-only designation and personal shortlist forms are available in a header disclosure with required audited reason (minimum 10), actor/time, optimistic version and idempotency preserved. Owner and BUs are shown; no identity invented. Customer Overview shows canonical KPIs, separate public/internal risk, explicit coverage, a revenue/bookings chart with table fallback, quote records, function coverage, activity/cadence, concentration and top three active records. Prospect Overview uses Fit factors, market, evidenced sites and access state; no revenue chart. Expansion count links to account-filtered Opportunities. Existing federal pursuit context and program/capability evidence retained on Overview.

Boeing account total is 2 open orders / $167,090 open; the requested $143,080 is the bracket line, not all account history. Score explanation modal remains keyboard-accessible. Initial compact score omitted its explanation control; restored it and explicit inline coverage before final E2E rerun.

Step4 tests: typecheck/lint/build PASS; frontend 84/84; focused backend profile/planning 17/17; focused E2E 5/5. Test changes: decision-experience and wave3-contracts replace decision-brief assertions with Overview/absence checks; profile-ux-refinement relocates brief selectors and removed Opportunities-tab planning to the header while retaining draft preservation, modal, keyboard and responsive checks; profile-opportunity-scope uses the new health KPI selector without changing its score-scope assertions. Screenshots include all five requested Boeing tabs (Actions now exists), list and Intel.

Step4 files: Accounts.tsx, ProfileOverview.tsx, profileTabs.ts; the four tests above; report/screenshots. No App.tsx changes. No DTO additions in this step. Header planning opens inline; it is not a new authorization path.

## Step 5 — Commercial, Intelligence, Actions

Commercial begins with late shipment commitments / open quote expiry / past decision dates, followed by order quantities/open value/due/status with expandable canonical lines, shipments and cancellations; table-first Quotes, RFQs, Agreements and Service events. All collections use existing paginated routes, with abort/timeout/retry and original evidence disclosures. Linked source actions reuse the existing preview/confirm component. Records without a canonical action explicitly say Create is unavailable; no unrelated action is attached. Existing related-record and commercial-source detail moved to More, not discarded.

Intelligence now has only Recent, with source/date, backend Confidence band, severity/disposition, site/program and freshness. **Expiry timestamp is not in the DTO; displayed as not projected, not fabricated.** Actions has a compact table, original idempotent inline create, and full Actions link. No API signature or scoring-policy changes.

Verification: typecheck/lint/build PASS; frontend 84/84; commercial/follow-up/planning/profile backend 12/12; focused E2E 6/6. Added Boeing order reconciliation/preview test. Existing profile-ux test now locates the replacement decision panel; no other assertions changed. New commercial test's expected external-write disclosure is now explicitly rendered from the preview's `external_write` field. Fixed duplicate generic table React keys and screenshot capture racing with deferred commercial load; recaptured Step5 after the decision panel is ready.

Full backend rerun surfaced a genuine projection regression: legacy valid monthly rows inherit currency from the ledger rather than repeating it. Fixed the new projection to honor that existing representation; unchanged durable readback test plus parity tests now 3/3. No fixture or assertion changes. Also removed case-only duplicate function labels from the read projection, without changing source labels, scoring or ranking. Full-suite recheck result is recorded under Step 6.

Step5 files: Accounts.tsx, ProfileCommercial.tsx, CommercialDecisions.tsx (export/reuse existing Followup and explicit external-write disclosure), modules/accounts/profile_projection.py (legacy compatibility), profile-ux-refinement.spec.mjs, profiles-redesign.spec.mjs, redesign-capture.mjs, report/screenshots. No DTO additions beyond Step2. App.tsx unchanged.

## Step 6 — Relationships

Function coverage retains Present / Thin / Unknown source states; Missing is reserved for explicit completed negative research. Ranked cards and a horizontal selected route are visible on entry. Full graph is a secondary toggle; canonical ranking, graph expansion, route selection, evidence, constraints and Omni context remain in place. Cards show hop count, backend strength only with complete coverage, freshness factor (explicitly not route time), weakest link and Verified/Hypothetical text. Unverified route connections use dotted lines. An Omni explanation panel retains evidence and next action. Retained reference connections are collapsed, not discarded.

Contacts use only existing public/CRM people. Verification and last two-way dates are Unknown where the person DTO does not project them. Unknown function rows can create an idempotent internal research action through the existing authorized action route; they never create a person or relationship. Route strength ranges are not projected by the backend: incomplete route strength is withheld with an explicit Unknown/range-not-projected message rather than an invented range.

Tests/setup changed: `helpers.mjs` waits for profile tabs before navigation, maps removed/relocated sections to current tabs, and explicitly opens the now-secondary desktop graph. `relationship-neighborhood.spec.mjs` uses that helper instead of blindly toggling the now-open workspace closed; graph-coordinate, expansion and route-preservation assertions are unchanged. `profiles-redesign.spec.mjs` adds a third test for default ranked cards, coverage, Hypothetical labeling, secondary graph and research controls. No ranking tests or assertions were weakened. The first scene rerun exposed text-selector disruption from an inserted coverage label; retained the original sentence and appended coverage in production UI, leaving those assertions unchanged. A worker already running the old neighborhood setup failed; the corrected setup passed in the final 27-test rerun.

Final typecheck/lint/build PASS; frontend 84 passed / 0 failed. Focused backend 25 passed / 0 failed. Full backend **790 passed / 25 failed / 10 errors / 2 skipped**: two new passes and exactly the same failing/error test names as the normalized baseline, verified by comparison of FAILED/ERROR lines. The intermediate legacy-currency regression was repaired without changing an existing test. See `final-backend-recheck.txt`.

Step6 screenshots: list, Boeing Overview/Commercial/Intelligence/Actions/Relationships, and Intel prospect, all captured with zero page errors. Final focused browser result: **27 passed / 0 failed** (`step6-e2e-verified.txt`), including the unchanged scene, Omni in-flight, graph-coordinate/expansion and record-context assertions. The intermediate run was 24 passed / 3 failed (one loading race plus two workers with old workspace setup); all 27 passed together on the final rerun. Generated focused trace artifacts were preserved under ignored `apps/web/test-results/redesign-focused-27`, not deleted.

Broad E2E execution uses the existing test inventory (186 tests; existing hosted-demo/public-collection exclusions unchanged). The initial serial broad attempt was interrupted to run four shards, each with one worker, its own local SQLite backup and unique ports 8141–8144 / 5341–5344. No test skip, retry, timeout or assertion was loosened. Each database was copied through SQLite backup from the same local SAMPLE database; no production data or invented fixtures. Cross-shard ordering equivalence remains UNVERIFIED.

## Unverified / deferred requirements

- PostgreSQL-specific backend behavior: UNVERIFIED in the isolated SQLite environment; the existing 25 failures and 10 errors remain. No original/production database was used.
- Full E2E pass-count comparison: UNVERIFIED because the pre-change E2E baseline failed at startup. The broader suite includes stale pre-branch navigation selectors and unrelated failures; focused checks and broad-run results are reported separately.
- Health bands/health-band filtering beyond Unavailable: deferred. No backend-approved health band definitions exist; adding thresholds would violate the scoring-policy guardrail.
- Signal freshness expiry timestamp: not projected by the existing DTO; explicitly unavailable rather than calculated from an invented retention rule.
- Person-level last two-way interactions and some verification dates: not projected by the contact DTO. Function-level and account-level recorded interactions are exposed separately, never attributed to a guessed person.
- Incomplete relationship-score ranges: not projected by the ranking service. Numeric strength is withheld rather than displayed as falsely precise or fabricated.
- A commercial decision without a canonical source action cannot use follow-up preview/confirm; the row explicitly reports Create unavailable. No synthetic source action or permission bypass was introduced.
- Existing federal pursuit context and header shortlist access remain. A new generic pursuit-creation workflow was not added; end-to-end pursuit creation from the relocated header is UNVERIFIED.
- UI manager designation/audit mutation and real external integrations remain UNVERIFIED in final browser coverage; existing backend planning/auth tests pass. No deployment performed.
- Original dirty Communications changes and historical original-folder hash mismatch cause were not investigated by modifying the original checkout. Merge integration remains outstanding.

## Complete changed-file manifest

Paths below include implementation, tests, local tooling, reports, retained run logs (including failed intermediate attempts), and requested screenshots. Ignored environment/database/build/browser artifacts are not committed. No App.tsx, dependency manifest, lockfile, migration, account ID, capability value or pinned data file changed.

- `apps/web/e2e/helpers.mjs`
- `apps/web/e2e/profile-opportunity-scope.spec.mjs`
- `apps/web/e2e/profile-ux-refinement.spec.mjs`
- `apps/web/e2e/profiles-redesign.spec.mjs`
- `apps/web/e2e/relationship-neighborhood.spec.mjs`
- `apps/web/playwright.config.mjs`
- `apps/web/src/features/accounts/Accounts.tsx`
- `apps/web/src/features/accounts/CommercialDecisions.tsx`
- `apps/web/src/features/accounts/Portfolio.tsx`
- `apps/web/src/features/accounts/ProfileCommercial.tsx`
- `apps/web/src/features/accounts/ProfileContacts.tsx`
- `apps/web/src/features/accounts/ProfileMetrics.tsx`
- `apps/web/src/features/accounts/ProfileOverview.tsx`
- `apps/web/src/features/accounts/RankedRelationships.tsx`
- `apps/web/src/features/accounts/profileTabs.ts`
- `apps/web/src/features/accounts/profiles-redesign.css`
- `apps/web/src/features/accounts/ranked-relationships.css`
- `apps/web/src/types/accountProfile.ts`
- `apps/web/src/types/api.ts`
- `apps/web/src/types/decisions.ts`
- `apps/web/tests/decision-experience.test.mjs`
- `apps/web/tests/poc-ui.test.mjs`
- `apps/web/tests/wave3-contracts.test.mjs`
- `apps/web/tools/redesign-capture.mjs`
- `backend/src/btx_omni/api/accounts.py`
- `backend/src/btx_omni/modules/accounts/profile_projection.py`
- `backend/tests/test_profile_projections.py`
- `backend/tools/redesign_local.py`
- `docs/redesign/REPORT.md`
- `docs/redesign/baseline-backend.txt`
- `docs/redesign/baseline/boeing-commercial.png`
- `docs/redesign/baseline/boeing-intelligence.png`
- `docs/redesign/baseline/boeing-overview.png`
- `docs/redesign/baseline/boeing-relationships.png`
- `docs/redesign/baseline/list.png`
- `docs/redesign/baseline/prospect.png`
- `docs/redesign/final-backend-recheck.txt`
- `docs/redesign/final-backend.txt`
- `docs/redesign/full-e2e-inventory.txt`
- `docs/redesign/full-e2e-shard-1.txt`
- `docs/redesign/full-e2e-shard-2.txt`
- `docs/redesign/full-e2e-shard-3.txt`
- `docs/redesign/full-e2e-shard-4.txt`
- `docs/redesign/full-e2e.txt`
- `docs/redesign/step2-frontend.txt`
- `docs/redesign/step2-initial-frontend.txt`
- `docs/redesign/step2/boeing-commercial.png`
- `docs/redesign/step2/boeing-intelligence.png`
- `docs/redesign/step2/boeing-overview.png`
- `docs/redesign/step2/boeing-relationships.png`
- `docs/redesign/step2/list.png`
- `docs/redesign/step2/prospect.png`
- `docs/redesign/step3-frontend.txt`
- `docs/redesign/step3-initial-frontend.txt`
- `docs/redesign/step3/boeing-commercial.png`
- `docs/redesign/step3/boeing-intelligence.png`
- `docs/redesign/step3/boeing-overview.png`
- `docs/redesign/step3/boeing-relationships.png`
- `docs/redesign/step3/list.png`
- `docs/redesign/step3/prospect.png`
- `docs/redesign/step4-frontend.txt`
- `docs/redesign/step4-initial-frontend.txt`
- `docs/redesign/step4/boeing-actions.png`
- `docs/redesign/step4/boeing-commercial.png`
- `docs/redesign/step4/boeing-intelligence.png`
- `docs/redesign/step4/boeing-overview.png`
- `docs/redesign/step4/boeing-relationships.png`
- `docs/redesign/step4/list.png`
- `docs/redesign/step4/prospect.png`
- `docs/redesign/step5-frontend.txt`
- `docs/redesign/step5/boeing-actions.png`
- `docs/redesign/step5/boeing-commercial.png`
- `docs/redesign/step5/boeing-intelligence.png`
- `docs/redesign/step5/boeing-overview.png`
- `docs/redesign/step5/boeing-relationships.png`
- `docs/redesign/step5/list.png`
- `docs/redesign/step5/prospect.png`
- `docs/redesign/step6-backend.txt`
- `docs/redesign/step6-e2e-final.txt`
- `docs/redesign/step6-e2e-recheck.txt`
- `docs/redesign/step6-e2e-verified.txt`
- `docs/redesign/step6-e2e.txt`
- `docs/redesign/step6-frontend.txt`
- `docs/redesign/step6/boeing-actions.png`
- `docs/redesign/step6/boeing-commercial.png`
- `docs/redesign/step6/boeing-intelligence.png`
- `docs/redesign/step6/boeing-overview.png`
- `docs/redesign/step6/boeing-relationships.png`
- `docs/redesign/step6/list.png`
- `docs/redesign/step6/prospect.png`
