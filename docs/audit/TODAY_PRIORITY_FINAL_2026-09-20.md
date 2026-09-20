# Today implementation final report, 2026-09-20

Branch: `codex/today-screen-refinement`, isolated worktree `btx-omni-prospect-today`.

## Result by phase

| Phase / scope | Result |
| --- | --- |
| Setup and baseline | Required audit cherry-picked as `52fd7e1`. Baseline saved before implementation. Original working branch was not switched. |
| Phase 1, reviewed-input line endings | Complete. Three narrow LF attributes restore exact reviewed Git blob bytes. No hash constants or reviewed content changed. |
| Task A, fixture and screen structure | Implemented in `d418a92`: browser-local greeting, shared importance predicate, page tabs, segmented source control, separate compact toolbar, unfiltered lead cards, URL-backed market selection, empty states, canonical ranks, local timestamp/date-only handling, SAMPLE labels and tests. |
| Phase 3B, priority ordering | Complete. One backend ordering module owns optional metadata, exclusions, class, completeness, score, date/age and stable-ID order. Internal and public items interleave without source as a sort key. Validation admission and placement are unchanged. |
| Phase 3B frontend integration | Header, badges and lead treatment read only server `high_importance`. Canonical mode preserves delivered order. Alternate user sorts preserve canonical rank labels. Rank/badge tooltips expose `triage_reason`. Expanded public priority cards receive the same metadata. |
| Integration corrections | Market Hubs page selection survives URL reload. Review on a filtered-out lead card reveals and focuses its canonical row. Development fixture is deterministic SAMPLE, off by default and enabled only in development. |
| Additional enrichment phases | No additional Phase 4/7 specification was supplied. No sample enrichment, supplemental file, fixed-clock change or re-pin was necessary. |
| Final gate | No new failing IDs against baseline. Two pre-existing assistant acceptance failures remain, documented with attempted approaches in `BLOCKERS_2026-09-20.md`. |

No push, deploy, production configuration/database change, migration creation, or Monitor code edit. Database tests used only task-owned local PostgreSQL databases. Account IDs and capability values were not renamed or removed.

## Verification against baseline

| Check | Baseline | Final result |
| --- | --- | --- |
| Frontend build/typecheck | Passed | `npm run build`: passed, including `tsc -b`. |
| Frontend lint | Passed | `npm run lint`: passed. |
| Full frontend unit suite | 82 passed | `npm test`: 86 passed, 0 failed. Task A intermediate was 85 passed. |
| Full backend suite | 710 passed, 67 failed, 10 errors | 814 passed, 2 failed, 0 errors, 8 warnings; 542.10 seconds. |
| Baseline failing/error IDs | 77 | 2 remain, 75 resolved, 0 new. |
| Final focused backend suite | Existing command-center coverage | `test_priority_ordering.py` and `test_command_center.py`: 40 passed. |
| Python lint | Not part of saved baseline | `ruff check src tests/test_priority_ordering.py tests/test_command_center.py`: passed. |
| Scoped browser suite | Existing reference and validation cases | 9 passed: five new ordering/tab/empty-state cases plus four existing desktop/mobile/reference/validation cases. |

The full backend run was collected before the final two additive regression tests and final small fixture/Critical-tier refinements. The subsequent 40-test focused run verifies those exact final changes, including the real HTTP `/today` contract and Critical-before-High tier order. The full unrelated browser suite was not run; the full frontend unit and backend suites were run.

Browser coverage includes desktop and mobile, server-only High decisions, canonical lead cards and ranks, source counts, alternate sort, search, filtered-out lead review, local dates, singular/zero header, keyboard tabs, URL reload, disabled/empty hubs and explicit watchlist copy. Manual browser verification found no Vite error overlay and checked the live desktop layout. Screenshot: `C:/Users/Aruna/.agent-browser/tmp/screenshots/screenshot-1789917012456.png`.

React checklist review covered derived state, effect dependencies, stable keys, keyboard tabs and optional metadata compatibility. It did not require a separate behavior change. Browser verification exposed the URL-persistence and filtered-lead integration corrections described above.

## Every intentional existing test change

| File / test | Change and reason |
| --- | --- |
| `apps/web/tests/poc-ui.test.mjs`: list-surface context assertion | Replaced removed disclosure state with Market Hubs tab state; preserves bounded context checks. |
| Same file: Seller Command Center test | Replaced old title and filtered lead-card assumptions; added greeting, tabs, keyboard, toolbar, source counts, hub/empty copy, analysis copy, canonical rank, SAMPLE and sizing checks for Task A. |
| `apps/web/tests/wave2-contracts.test.mjs`: bounded queues | Lead-card source changed from filtered priorities to the full canonical list. Pagination assertions remain. |
| `apps/web/tests/today-model.test.mjs`: shared importance test | Replaced frontend-inferred severity/eligibility fixtures with server metadata. Added contradictory severity and legacy payload checks; retains count-equals-High-badges assertion. Removed now-unused attention-module test transpilation. |
| `backend/tests/test_command_center.py::test_priority_projection_is_ordered_and_self_describing` | Replaced old internal-first/newest-first expected order with triage/score interleaving and oldest-first ties; added alert kind/status provenance and explicit opportunity score/confidence. |
| Same file: development fixture test | Added deterministic SAMPLE assertions so fabricated public data cannot masquerade as live observations. |
| `apps/web/e2e/today-reference.spec.mjs`: both width cases | Lead cards now stay canonical while list filters change; updated source-control and customer-selector labels. Waits for account heading before back navigation to synchronize the existing navigation assertion. |
| `apps/web/e2e/today-validation-lanes.spec.mjs`: both cases | Updated source-control selectors/customer label only. Validation separation and Omni behavior assertions remain. |

Additive coverage: local-component greeting boundaries/date-only tests in `today-model.test.mjs`; fixture guard tests in `test_command_center.py`; Today page-tab/market URL roundtrip in `navigation.test.mjs`; new `test_priority_ordering.py`; five new `today-priority-ordering.spec.mjs` cases. Backend coverage includes explicit hard stops, all exclusion states, duplicates, 100 deterministic random shuffles, confidence/score boundaries, complete-before-incomplete, unknowns, mapping exhaustiveness, date ties, schema compatibility and unchanged validation admission. No existing test was skipped, deleted or weakened.

## Mapping judgments and confidence decisions

Full per-kind rationale and optional-field meanings are in `PRIORITY_ORDERING.md`; alternatives and reasons are in `DECISIONS.md`.

- Internal risks: CUSTOMER_INACTIVITY, BOOKINGS_DECLINE, STALE_QUOTE, OVERDUE_ORDER. These establish negative conditions, but neither lateness nor inactivity implies a hard stop.
- Internal opportunities: QUOTE_FOLLOW_UP, CRM_INACTIVITY, CROSS_BU_COORDINATION. Follow-up/coordination work does not itself establish severe commercial harm.
- Internal UNKNOWN: INTELLIGENCE_COMMERCIAL_CONTEXT and missing/future kinds. A review request does not establish direction.
- Public risks: CONTRACT_REDUCTION, PROGRAM_CANCELLATION, FACILITY_CLOSURE, WORKFORCE_REDUCTION, FINANCIAL_DISTRESS, EXPORT_RESTRICTION, PRODUCTION_DELAY. Export restriction alone does not establish an explicit legal hard stop.
- Public opportunities: CONTRACT_AWARD, SOLICITATION, FACILITY_EXPANSION, CAPACITY_EXPANSION, NEW_FACILITY, PROGRAM_LAUNCH, PRODUCTION_RAMP, PRODUCT_LAUNCH, SUPPLIER_AWARD, CAPITAL_INVESTMENT, PARTNERSHIP, REGULATORY_APPROVAL, GOVERNMENT_FUNDING, GRANT_AWARD. These are possible pursuit/demand conditions, not claims that BTX won business. Approval is enabling, not inferred regulatory risk.
- Public UNKNOWN: UNCLASSIFIED_PUBLIC_UPDATE, CONTRACT_MODIFICATION, SUPPLY_CHAIN_CHANGE, M_AND_A, REGULATORY_CHANGE, EXECUTIVE_CHANGE, EARNINGS_SIGNAL, BACKLOG_CHANGE, and missing/future types. Direction is ambiguous or absent.
- Explicit structured `risk_severity` overrides the public event default. No headline, ID or recommendation parsing establishes nature.
- Public confidence uses only the brief's explicit signal-confidence score/tier. High is 70+, Medium is 40+, otherwise Low. Missing confidence stays unknown; READY/eligibility/URL/watch status never substitutes.
- Internal explicit evidence confidence wins. Otherwise CONFIRMED provenance with evidence IDs defaults to High. Unconfirmed/absent provenance remains unknown. SAMPLE confidence describes support within the labeled sample scenario, not live truth.
- Opportunity score is an explicit governed opportunity-priority assessment, never confidence, fit, attractiveness or monetary amount. Public producers do not always supply it; missing means NONE/null/incomplete.
- Tier-only fallback sorts Critical/High/Medium-or-Moderate/Low as ordinal 100/75/50/25; returned numeric score remains null. Explicit numeric scores take precedence. Customer-health values are not silently inverted into risk.
- Missing inputs prevent complete status. Incomplete score ranges sort by their upper bound, but a range ceiling never creates confirmed High importance. Unknown score sorts last.
- Unknown nature/confidence stays Class 3. Under the supplied separate importance rule, a known High-severity risk with unknown confidence can still be High importance without escalating its class.
- Only an explicit true source hard_stop sets Class 0. Public lifecycle/hard-stop/due-date fields are currently absent, so nothing is invented. Existing public stale admission still applies.
- Due dates are not inferred from program dates. Age uses creation time if supplied, otherwise observed time. Terminal duplicate identities suppress open copies; no headline-based merging.
- Legacy payloads without metadata render with undetermined attention, not guessed High. Explicit false uses the existing non-High medium badge.

## Full reviewed-input ledger summary

`REVIEWED_INPUT_CHANGES.md` records checkout normalization only. Old and new reviewed SHA-256 values are identical:

| File | Unchanged reviewed SHA-256 |
| --- | --- |
| `docs/research/enriched_commercial_sample.json` | `b9ff27965e2716abab313f840de903191617c4da24d8fd8df7bf999c868bcd2e` |
| `docs/research/btx_original_workbook_references.json` | `d0e4a1ca28d5f6ec38edd457b81fe98177d5b9d5396ac582b6bf34e9901e55d7` |
| `backend/tests/fixtures/g17-ip-sa-20260908.txt` | `e8f510e4ade5b3d0d2c43a1339185494c0996f4b2678ca810579caf9869791c3` |

All three working copies were CRLF while reviewed Git blobs were LF. Narrow `.gitattributes` entries enforce LF. Working bytes now match Git blob SHA-256 and existing constants. The ledger also preserves each original CRLF checksum. Baseline recorded system `core.autocrlf=true`; continuation observed repository `input` with existing CRLF copies. This task changed no Git config. No repin, reviewed content edit, supplemental sample file or fixed sample-clock change occurred. Existing `backend/tests/prepare_e2e.py` prepared browser data; full backend tests reran reviewed-input consumers.

## Deck versus rubric discrepancy

The user reports executive deck slide 15 weights of urgency 30, BTX impact 30, dependency 20, age 10 and ownership gap 10. Those weights were NOT implemented. This task follows the supplied Action Priority rubric: exclusions, triage class, assessment completeness, underlying score, due date, age, stable ID. The deck was not supplied for independent inspection. Owner follow-up is to align its description with the implemented rubric, not silently blend the two policies.

## Remaining baseline failures

1. `tests/test_api_acceptance.py::test_canonical_poc_api_end_to_end_paths`: machine alert-kind text versus existing human-facing assistant label.
2. `tests/test_api_acceptance.py::test_omni_cross_account_score_ranking_uses_typed_market_filter`: account-attractiveness expectation versus existing opportunity-score response.

Both are unchanged baseline IDs. Evidence and attempted approaches are in `BLOCKERS_2026-09-20.md`.
