# Opportunities UI rebuild — 2026-09-20

## Result

Implemented the two-lane Opportunities workspace against all seven approved Figma frames.
Desktop table, mobile cards, filters, sorting, grouping, saved views, shareable URL state and accessible detail drawer are implemented.
Frontend checks and 98 unit tests pass; eight isolated Playwright tests pass.
Backend has six additional passing tests and no reproducible new failure; the full suite remains red as described below.
Durable imported-data verification remains blocked by the pre-existing missing qualified import; the explicit development fixture is not production data.

## Branch, isolation and commits

- Branch: `opportunities-ui-rebuild`, based on `a23da6e`.
- Worktree: `C:/Users/Aruna/btx-opportunities-ui-rebuild`.
- Implementation milestone: `a31495a`. The final audit/verification milestone follows that commit on the same branch.
- The original `C:/Users/Aruna/OneDrive/Desktop/Kapil/btx-omni-prospect` worktree retains its five modified and two untracked communications/App files. Nothing there was reverted, reformatted, staged or committed.
- Explicit file paths were used for staging. No push, deployment, production configuration change, production database write, account/capability rename, scoring change or migration creation occurred.
- Browser verification uses its own temporary SQLite file and existing SQLAlchemy metadata. No application migration command was run. The requested backend suite itself includes existing temporary SQLite migration-chain tests.

## Changed files

Paths below are relative to the repository root.

| Files | Change |
| --- | --- |
| `apps/web/src/features/opportunities/Opportunities.tsx` | Header, lanes/counts, saved views, lane-wide metrics, toolbar, table/cards, loading/error/empty states, URL-driven selection and context |
| `apps/web/src/features/opportunities/opportunities.css` | Scoped desktop/mobile design, columns, status chips, range bars, menus, drawer/sheet, self-hosted fonts and bundled license references |
| `apps/web/src/features/opportunities/opportunityModel.ts` | Pure sorting, filtering, grouping, subtotal, status, priority presentation and URL model |
| `apps/web/src/features/opportunities/PriorityCell.tsx` | Numeric/range priority display and combined status chip |
| `apps/web/src/features/opportunities/OpportunityDetail.tsx` | Shared accessible Drawer, previous/next, six returned factors, gates/reasons, context/questions/next step, lazy CommercialEvidence and account/Omni actions |
| `apps/web/src/features/opportunities/OpportunityMenus.tsx` | Desktop popovers and mobile bottom-sheet controls |
| `apps/web/src/features/opportunities/opportunityFixture.ts` | Explicit development/test-only examples for both lanes, every gate state, complete bands, missing factors, null values/categories |
| `apps/web/src/features/opportunities/assets/search.svg`, `chevron.svg` | Exact Figma-exported icons |
| Same assets directory: `inter-latin.woff2`, `archivo-bold-latin.woff2`, `inter-OFL.txt`, `archivo-OFL.txt` | Self-hosted design fonts with redistribution licenses; no runtime provider request |
| `apps/web/src/types/opportunities.ts` | Nullable value, optional market/BU/gates and already-returned factor contribution typing |
| `apps/web/src/app/navigation.ts` | Additional allowed opportunity-specific f.* query keys; existing record selection and return route retained |
| `backend/src/btx_omni/modules/commercial/opportunities.py` | Only backend implementation change: additive read-only market and BU projection |
| `backend/tests/test_opportunity_categories.py` | Six category projection tests, including missing values and account isolation |
| `apps/web/tests/opportunity-model.test.mjs` | Fourteen new model/rendering/fixture tests |
| `apps/web/e2e/opportunities-rebuild.spec.mjs` | Eight browser scenarios |
| `apps/web/playwright.opportunities.config.mjs` | Isolated test backend/database/frontend startup, no durable import required |
| `apps/web/e2e/profile-opportunity-scope.spec.mjs` | Existing assertions adapted to the new dialog, cards/rows and labels; original business/graph assertions retained |
| `docs/audit/opportunities_ui_baseline_2026-09-20.txt` | Actual baseline results and all failing/error test names |
| `docs/audit/OPPORTUNITIES_UI_DECISIONS_2026-09-20.md` | Full judgment, diagnosis and fallback log |
| This report | Final verification and handoff |

## Implemented behavior and data boundaries

Verified by code and targeted tests:

- Customer expansion and prospect opportunities retain their existing route `#/opportunities` and lane identifiers. Counts and the three metrics describe the whole lane, independent of active filters.
- Saved views use returned `gates.qualified_and_durable` and `gates.durable_best_bet`; neither is recalculated from the displayed score.
- The column is now Priority and reads `opportunity_priority`, not `attractiveness`. The backend's v2 family derives weights from the six-factor rubric: 30/25/15/10/10/10. Source: `backend/src/btx_omni/modules/scoring/families.py:15-32` and `account_attractiveness.py:89-94` (both unchanged).
- Complete scores render the returned number. Incomplete scores render the returned low-to-high range and dashed segment, never a midpoint or partial point score. Factor contribution and weight are returned backend values. Unknown contributions stay Unknown.
- Priority default orders complete scores first, then incomplete range tops; every sort has an opportunity-ID tie-break. Company uses a case-insensitive locale-aware collator. All headers except Opportunity cycle ascending, descending, default.
- Market multi-select counts respect the other filters. BU and stage filters intersect with text/account/saved-view filters. Zero-count markets are dimmed; selected zero-count values can still be cleared.
- Company/market/BU/stage grouping is alphabetical, Unassigned last, with collapsible groups, counts and sized-value subtotals. Different currencies are not converted or added together.
- Existing hash serialization stores lane, saved view, market list, BU, stage, text, sort, grouping, collapsed groups and selected record. Legacy account links and return context are preserved.
- Enter opens a row. Shared Drawer provides dialog semantics, Escape/outside close and focus trapping. Focus returns to the initiating row, or the selected visible row after a deep-link reload. Previous/next follows group order and the active row sort.
- Mobile uses cards and bottom sheets with the same controls. Metric cards are omitted on mobile as in the supplied mobile frame.
- The screen distinguishes loading, load failure with Retry, an empty lane and an empty filtered result with Clear filters.

### What is real versus illustrative

| Item | Actual source / limit |
| --- | --- |
| Normal rows, scores, ranges, gates and evidence | Existing Opportunities API and CommercialEvidence; this change does not connect a new external system |
| Market | Explicit primary ledger assignment when present; otherwise alphabetically first canonical account industry; null if absent |
| BU | Matching opportunity/account-scoped canonical CRM deal's business_unit; null if absent, never guessed from account name or general BU membership |
| Development examples | Twelve authored examples, explicitly labeled, only opt-in under `import.meta.env.DEV`; no canonical evidence/account/Omni actions for invented IDs |
| Browser API-backed evidence test | Explicitly intercepted test response exercising the real client/component path; not proof of live commercial evidence |
| Unseeded local backend | Actually returned an empty opportunity list; UI showed the empty lane and did not silently substitute fixtures |
| Production bundle | Built and inspected: no fixture module or illustrative row markers; both font license assets present |

Development preview URL: `/#/opportunities?f.opportunity_fixture=demo`. Add `&f.lane=PROSPECT` for prospects. Without the explicit flag, the API remains authoritative, including empty/error responses.

## Design verification

Read Figma file `QPWPGGDAxEtzG6a69Nsr68` frames `392:93`, `394:93`, `394:385`, `397:93`, `397:403`, `398:93`, `398:193` using the Figma design-to-code skill. The skill informed token/layout adaptation and exact icon reuse. Federal Notices frames were not treated as this screen.

Rendered and visually inspected desktop (1440px) and mobile (390px) screenshots: typography, metrics, columns, chips, low/high ranges, selected rows, drawer controls, bottom sheet, grouped rows and menus. Browser assertions verify no horizontal document overflow at both widths. The existing application shell/navigation and its simulated-data banner were preserved; they are not part of this screen rebuild.

Screenshots are generated in the ignored `apps/web/test-results/opportunities/` output directory, including each viewport's `list.png` and `drawer.png`, plus `group-sheet.png`. They are local verification artifacts, not committed design assets. This was a human visual comparison, not a pixel-diff claim.

The browser-verification skill checklist was used with the explicitly requested Playwright toolchain because agent-browser CLI is not installed. Main desktop/mobile flows asserted no page errors, no console errors, no unexpected failed requests/HTTP errors and no Vite error overlay.

## Baseline versus final checks

Baseline was run before implementation in the isolated worktree. The supplied historical audit (82 frontend passes; approximately 710 backend passes/67 failures/10 errors) differs from this HEAD and was not substituted for a measurement.

| Check | Actual baseline | Final |
| --- | --- | --- |
| Frontend typecheck | Pass | Pass |
| Frontend lint | Pass | Pass |
| Full frontend unit suite | 84 passed, 0 failed | 98 passed, 0 failed |
| Production build | Not part of baseline request | Pass |
| Backend category tests | Did not exist | 6 passed |
| Full backend suite | 797 passed, 16 failed, 10 errors, 2 skipped | 803 passed, 16 failed, 10 errors, 2 skipped |
| Existing durable profile/opportunity E2E | Backend startup blocked before assertions | Still unavailable without qualified import; selectors updated, not executed against durable data |
| Isolated Opportunities Playwright suite | Did not exist | 8 passed, 0 failed (35.2s final run) |
| Two varying monitor tests, targeted rerun | One failed during full baseline | Both passed on targeted rerun |
| Fixture production exclusion / font licenses | Not applicable | Artifact assertions pass |
| Git whitespace check | Clean starting worktree | Pass |

Commands run from `apps/web`: `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`, `npx playwright test --config playwright.opportunities.config.mjs`.

Backend command from `backend`: `python -m pytest -p no:cacheprovider --tb=no -q`, with PYTHONPATH explicitly targeting this worktree and BTX_DATABASE_URL unset. The existing installed Python environment was used consistently for baseline/final. Backend full-run durations were 365.70s baseline and 568.84s final.

### Backend result detail — not a clean suite

All ten PostgreSQL setup error names and fifteen failure names match baseline exactly. The complete original names are in [the baseline file](opportunities_ui_baseline_2026-09-20.txt).

Two monitor results varied:

1. Baseline failure `tests/test_monitor_live.py::test_durable_monitor_persists_runs_versions_events_and_failures` passed in the final full suite.
2. `tests/test_monitor_operations.py::test_postgresql_operational_lock_keeps_its_session_alive` failed in the final full suite despite passing baseline. Its unchanged test uses a fake connection, a 1ms heartbeat and only a 10ms sleep (`backend/tests/test_monitor_operations.py:533-571`).
3. Immediate targeted rerun of those exact two tests passed: 2 passed in 3.00s. Neither monitor implementation nor monitor tests were edited. This is a timing-sensitive, non-reproduced failure, not evidence that the whole backend is green.

No sample-hash failure reproduced in this checkout's measured baseline/final runs. The sample JSON and pinned hash remain untouched. The user-reported stale-hash issue remains outside this task; no claim is made that it was fixed.

### Browser scenarios

1. Desktop row Enter/open, backend number/contribution, next, Escape, focus return, shared URL/reload, focus trap, range, other lane, overflow and console/network checks.
2. Same flow on 390px mobile, including selected-row focus after direct-link reload.
3. Market/BU/stage filters, saved view, group subtotal/collapse and URL restoration.
4. Mobile Filters/Sort/Group sheets and sorted cards.
5. Controlled API load failure, Retry, empty lane versus no filter matches, Clear filters.
6. API-backed detail evidence lazy-loading, account return URL and outside-click close.
7. Header three-state sorting, filter-independent lane metrics and Unassigned-last groups.
8. Actual unseeded backend empty response with no silent fixture fallback.

## Decisions and fallbacks

Every implementation judgment and intermediate failure is recorded in [the decisions log](OPPORTUNITIES_UI_DECISIONS_2026-09-20.md). Key outcomes:

- No migration, scoring modification, invented market mapping, imported sample change or new dependency.
- “Active Opportunities” was not found as the frontend federal screen label; its current label is Federal Procurement, so no conditional rename was made.
- The durable browser configuration fails with “Durable commercial mode requires a qualified import.” Rejected modifying the pinned hash/importing data; used the separate opt-in fixture and isolated test config.
- Port collision, empty database URL, in-memory SQLite thread/schema issues and late-registered metadata were diagnosed. Final browser backend uses unused ports and a unique test-owned file database with the already-defined metadata; startup is clean.
- React StrictMode request replay was accounted for in the new fault-injection and evidence tests. No existing assertions were removed or weakened to get a pass.
- Existing profile/scope test retained its graph and commercial-context assertions, adapted selectors to the new accessible UI, and retained the old absolute screenshot path because that path was not the runtime blocker.
- Font delivery was verified in production output; Vite stripped a legal CSS comment, so URL metadata now bundles the original license files without adding UI chrome.

## Remaining follow-ups / not executed

- Run the existing durable profile/opportunity test and the broader browser suite in an environment with a qualified commercial import and its required database. Their assertions were not executed here; the dedicated eight-test UI suite is the verified fallback, not proof of durable integration.
- PostgreSQL-specific backend cases still need an isolated configured PostgreSQL instance. Investigate the two timing-sensitive monitor tests separately.
- Missing real market/owner BU data must be populated through the existing upstream governance process; the UI correctly displays Unassigned meanwhile.
- Real evidence and account/Omni actions for imported pursuits need a connected-pilot smoke test. Development examples deliberately cannot impersonate canonical pursuits.
- The reported stale commercial-sample hash was neither modified nor repaired. Investigate it separately before importing/connecting that sample.
- No Safari/WebKit run, assistive-technology session or pixel-diff automation was performed. Chromium keyboard, dialog semantics, focus, both viewport sizes and absence of overflow were tested.

No known remaining implementation failure was reproduced in the scoped unit/browser/category tests. No deployment or production-data validation is claimed.
