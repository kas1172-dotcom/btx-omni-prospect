# SAMPLE enhancement report

Status: Tiers 1, 2 and 3 implemented and verified locally. Checkpoints: `tier1-complete`, `tier2-complete`, `tier3-complete`.

The enhancement is an opt-in, deterministic demonstration dataset, not evidence of real BTX commercial activity. It supplies reconciled synthetic transactions, fictional regional accounts, all requested scoring vectors and context for J1–J9. Verified Kratos, Federal Reserve and FDA public context stays separate from invented commercial facts. The mechanics are tested; unresolved identity, location, sourcing and adverse-event research remains visibly unresolved rather than fabricated. Live Gemini generation and browser/map-provider rendering were not exercised.

## Local activation and scope

Use the isolated `sample-data-enhancement` branch/worktree. Configure only a local database with the existing migration chain, then run the existing application startup workflow with these settings:

```text
BTX_DATA_MODE=SAMPLE
BTX_SAMPLE_ENHANCEMENT_ENABLED=true
DEMO_AS_OF_DATE=2026-09-20
BTX_COMMERCIAL_DURABLE_STATE_ENABLED=false
BTX_MONITOR_MODE=disabled
BTX_MARKET_REFRESH_ENABLED=false
BTX_DATABASE_URL=<your task-owned local database URL>
```

Selection composes a read-only runtime view; no seed script, new migration or fixture import is required. The switch defaults off and does not activate the additions in CONNECTED mode. Existing persisted planning/itinerary choices override demonstration defaults. Explicit user workflow saves still use the normal local persistence APIs. No deployment, push, production configuration change or production database access was performed. The task-owned PostgreSQL container is `btx-sample-enhancement-pg` on loopback port 57379; it remains available for reproduction.

## Per-journey coverage

Paths below are relative to `backend/tests/`; scenario modules are in `backend/src/btx_omni/providers/sample/`.

| Journey | Demonstration and honest boundary | Fixture-backed assertion |
|---|---|---|
| J1 regional prospecting | Fictional Watch Southwest origin, nine nearby organization sites plus fictional BTX site; six markets, matching directory/map IDs, nine-stop draft itinerary. No invented meetings or travel times. | `test_sample_regional.py:test_j1_regional_cohort_has_exact_pins_and_directory_parity`; `test_sample_journey_contracts.py:test_j1_prefilled_itinerary_has_no_contact_or_meeting_or_travel_inventions` |
| J2 cross-BU planning | APM missing monthly feed explicitly Unknown, not a forecast; ERA invoices at three sites; All/Exclude/Only partnership filters and persisted override precedence. | `test_sample_planning.py:test_j2_gap_is_not_forecast_and_three_sister_bu_sites_have_invoices`; `test_sample_journey_contracts.py:test_j2_j3_api_defaults_and_model_context_are_available_without_writes` |
| J3 market coverage | Medical customer/prospects/partnership/BTX location and fictional regional concentration; verified national G.17 series and FDA draft context separate from account evidence. No M&A score. | `test_sample_medical_market.py:test_j3_medical_coverage_and_separate_verified_national_series`; `test_sample_public_research.py:test_fda_draft_stays_aggregate_and_expires_without_invented_effective_date` |
| J4 research lead | Curated Kratos J85 signal, computed 63.75 Medium, Auburn Hills production statement, superseded Oxford history, Unknown need and sourcing-role gap. Research-only publication hold is intentional, not a qualified prospect. | `test_sample_kratos.py:test_j4_visible_provenance_and_publication_hold`; `test_j4_curated_research_not_invented_canonical_pursuit` |
| J5 expansion | Boeing public Kratos development joined to explicitly synthetic programs, component rationale, two BUs and current quote; unsupported BTX/JDAM-LR supply remains a hypothesis. | `test_sample_expansion.py:test_j5_public_signal_and_synthetic_history_join_without_inventing_supply` |
| J6 external risk | Fictional consolidation exercises distinguish unconfirmed Validate immediately from high-confidence Escalate now; separate public/internal explanations and live combined 62 result. Not a real SEC/WARN allegation. | `test_sample_external_risk.py:test_j6_unconfirmed_risk_requires_validation_and_confirmed_risk_escalates`; `test_sample_journey_contracts.py:test_live_customer_risk_wrapper_is_62_not_only_a_standalone_vector` |
| J7 recovery | Boeing 292 ordered / 146 shipped / 146 open / $143,080; pending September 26 proposal, revisions, partial shipments, options, owner role and dependency. Completion without scoped proof is rejected. | `test_sample_enhancement_ledger.py:test_j7_reconciles_exact_units_value_and_unaccepted_proposal`; `test_j7_completion_requires_scoped_verified_proof` |
| J8 relationship discovery | Fictional regional-defense manufacturing goal has distinct 2/3/4-edge evidenced routes, dates, source IDs and weakest links; unsupported link displayed separately. No personal introduction. | `test_sample_relationships.py:test_j8_j9_longer_evidenced_route_beats_shorter_older_route` |
| J9 relationship comparison | Four-edge route outranks older two-edge route; separate versioned relationship calculation, no cycles/duplicates, not PWIN or Signal Confidence. | `test_sample_relationships.py:test_j8_j9_longer_evidenced_route_beats_shorter_older_route` |

`test_sample_journey_contracts.py:test_all_authored_ledgers_reconcile_and_commercial_rows_are_labeled` checks all 15 selected ledgers. `test_sample_model_budgets.py:test_rich_fixtures_reach_model_without_exceeding_evidence_budget` exercises model retrieval and exact drill-down traces without a live model request. All corrected numeric golden targets in the two tables below match; no expected failures remain.

## Confidence and remaining unknowns

- The supplied rubric lacked R9–R10 text: **NOT FOUND**. Explicit user amendments take precedence; missing make/buy bands retain the documented existing mapping. These are specification limitations, not silently invented authority.
- Kratos investor-page retrieval returned 403; its primary corporate mirror verifies the date and J85 production scope. Official CAGE/UEI, precise address/coordinates and sourcing contact remain unverified. The lead correctly stays in Research, not Map/directory. No names or introductions were invented.
- The supplied stale history is retained but not newly verified: Air & Space Forces Magazine, 2026-08-05, https://www.airandspaceforces.com/long-range-jdam-air-force-new-standoff-strike-option/; Kratos via GlobeNewswire, 2024-09-12, https://finance.yahoo.com/news/kratos-announces-immediate-availability-tdi-120000356.html. Both retain the payload's 2026-09-20 retrieval-date field and explicit historical status; this is not a claim that their page contents were retrieved in this run.
- AIM-260 primary-government verification was not completed. J5 uses the verified Kratos release instead. No new SAM.gov/USAspending/SEC/WARN account claim was verified; J6 uses explicitly fictional adverse-event exercises. Therefore real connected risk intelligence is not delivered by this fixture task.
- Actual travel, meeting confirmation, named contacts, warm introductions, browser interaction and live Gemini/provider output are unverified. Contract tests prove evidence delivery, scoring and API behavior, not generated prose quality or third-party map rendering.
- Connected operation still requires real governed source records, entity/site resolution, commercial-system mappings, verified role/access evidence and authorized credentials through existing integration boundaries. Integration stubs were not altered. Synthetic quantitative assumptions must never be treated as BTX measurements or real customer facts.
- Full suite warnings are dependency deprecations (Starlette/httpx and Alembic path separation), not failed assertions. Historical intermediate results below are retained for traceability and superseded by the final 877/87 checkpoint.

## Tier checkpoints

### Generated catalog counts

Generated 2026-09-20 by existing `build_sample_environment()` and `enhance_environment(base)`; aggregate lengths only, no reference-record content exported. The base has **34 researched accounts**, not 78. Canonical totals include existing reference identities and are not counts of verified public companies.

| Collection | Base | Enhancement enabled |
|---|---:|---:|
| Canonical accounts | 309 | 323 |
| Account facilities (all truth classes) | 431 | 441 |
| Public/facility projection, including explicitly fictional additions | 39 | 49 |
| BTX facilities, including one fictional addition | 5 | 6 |
| Watch profiles | 309 | 309 |
| Selected commercial ledgers | 0 | 15 |
| Programs | 32 | 47 |
| Component classes | 30 | 47 |

Reproduce with the local Python interpreter from `backend`: prepend `os.path.abspath('src')`; build both environments; print `{key: len(getattr(environment, key)) for key in ('accounts', 'facilities', 'public_facilities', 'btx_facilities', 'watch_profiles', 'commercial_ledgers', 'programs', 'component_classes')}`. Research count is `len(base.researched_accounts)`. No database or network command is needed.

Item 3.4: stale current-count claims in WORKFLOW, research index and acceptance matrix now point here. Historical input reports are explicitly marked historical. `SampleRepository.seed()` in `backend/src/btx_omni/persistence/repository.py` is **dead code in the inspected repository**: `rg -n 'SampleRepository|\.seed\(' backend -g '*.py'` finds only its definition, no callers. It also expects a retired `environment.ranks` attribute. It was not executed or deleted; external callers cannot be ruled out. Runtime composition, not this method, selects the enhancement.

### Verified checkpoints

Tier 3: **877 backend tests passed**, 8 dependency deprecation warnings, no deselection/xfail (309.43 seconds). Frontend typecheck, ESLint and production build passed; **87 frontend tests passed**. This adds 21 backend and 3 frontend tests relative to Tier 2, with no remaining failures. The final backend run used the loopback-only PostgreSQL harness below. Targeted evidence-budget/Gemini-contract checks: 46 passed; final targeted public-signal, award and journey checks: 38 passed. `git diff --check` and targeted Ruff checks passed. No live Gemini invocation or browser verification is claimed.

Tier 2: **856 backend tests passed**, 8 dependency warnings, no deselection/xfail (202.94 seconds). Frontend typecheck, ESLint and production build passed; **84 frontend tests passed**. Ten more backend tests than Tier 1. Tag: `tier2-complete`.

Tier 1: **846 backend tests passed**, 8 dependency deprecation warnings, no deselection/xfail (373.08 seconds). Frontend typecheck, ESLint and production build passed; **84 frontend tests passed**. Compared with the first valid local PostgreSQL checkpoint (829 passed / 3 failed), all failures are resolved and new fixture assertions are included. Tag: `tier1-complete`.

Full backend command (from this worktree's `backend`, using the existing Python 3.11 interpreter): set `PYTHONDONTWRITEBYTECODE=1`, `BTX_DATABASE_URL` to the task-owned loopback PostgreSQL database, `BTX_MONITOR_MODE=disabled`, and an empty `BTX_GEMINI_API_KEY`; prepend the absolute local `src` to `sys.path`; install a Python audit hook rejecting non-loopback `socket.connect`; run `pytest.main(['-q', '--tb=short', '-p', 'no:cacheprovider'])`. Frontend commands: `npm run typecheck`, `npm run lint`, `npm run build`, `node --test --test-reporter=dot tests/*.test.mjs`. Existing reference JSON may be loaded by existing code, but was not printed, copied, edited or used to author additions.

## Decisions made without user input

- Evidence-budget validation found that the rich Watch history/decision reads were 90,184/115,189 characters and would be rejected by the existing 24,000-character per-read limit. Kept both hard budgets unchanged. Oversized reads now return explicit indexes, with account-scoped `read_decision` and `read_rubric_example` drill-downs preserving exact factor evidence and calculations. Direct API/full canonical reads remain intact. `test_sample_model_budgets.py` exercises the actual provider-selection loop, verifies completion under both budgets, and compares drill-down factors byte-for-value with the full canonical result.

- Final R1/R2 review found that expired Signal Confidence still retained a numeric total in a legacy test. Section 4's freshness contribution remains its explicit zero band, while the other expired observations become Unknown with history retained: the current assessment has no point score and range 0–90. Updated `test_public_signal_assessment.py:test_source_change_invalidates_decision_and_old_publication_loses_freshness` to assert Unknown/range rather than its old 49.11 total. This is a rubric correction, not a weakened test; the 30.1-day service-level vector asserts the same result. Fresh 3/9-day vectors are unchanged. The legacy account-context compatibility projection now also carries the v2.0 rule version; its old configuration identifier is preserved.

- Final verification (3.5) found business-date API paths still using the operational clock. Planning targets, itinerary persistence, snoozes and SAMPLE CRM deadlines now use the as-of provider. Minimal test/adaptor runtimes without settings use that same provider, not wall time. Authentication, receipt ordering, retention and deadline timers remain operational clocks.
- The runtime's instance date now overrides the global default. Enhancement plus durable commercial import is rejected explicitly: a durable revision must not silently replace the selected demonstration view. This is an opt-in, local read-only scenario selector, not a production import path.
- J1 receives a nine-stop, prefilled, read-only itinerary with origin and purpose. It has no contact names, meetings, driving times or route-provider claims. A saved user itinerary wins; null version means the draft has never been persisted. Existing optimistic concurrency remains intact.
- Stale/Conflicting pursuit and Prospect Fit factors retain their linked history while contributing Unknown. Added missing rule-version/trace metadata on Prospect Fit, Data Coverage and queue receipts. No weights changed in this final pass.
- Combined customer risk now exposes a fixed-weight range when an input is unknown. Its upper bound also evaluates possible rubric floors; e.g. internal 52.5/public unknown is 31.5–75, not an unjustified point score. Confirmed current legal/safety service evidence explicitly reaches the wrapper; absent or expired confirmation does not trigger a floor.
- Gemini's canonical decision read now receives the same server-owned public/internal/combined risk projection as the API, not merely the internal score. Synthetic risk factors are labeled POC_SCENARIO, not PUBLIC_SOURCE. Account and Map disclosures expose the authored narratives, hypotheses and numerical traces; Medical context remains separate from account evidence.
- React best-practices review: reused existing disclosures and canonical-record rendering; no new fetch waterfalls, render-time side effects or conditional hooks. New list identities remain deterministic. UI behavior is covered by typecheck, lint, build and contract tests; no live browser/Gemini validation is claimed.

### Final alignment before/after (3.5)

| Code | Before | After / authority |
|---|---|---|
| `api/runtime.py:observed_at` | Ignored instance date | Instance DEMO_AS_OF_DATE wins; R1/R6 |
| planning/actions/itinerary API; technical-fit/explanation defaults | Mixed wall and business dates | As-of provider for business decisions, operational timers unchanged; amendment 2 |
| `families.overall_customer_risk` | Unknown input suppressed point score but gave no range | Fixed 60/40 bounds, explicit floor/uplift trace; R2/R8 |
| `families.customer_risk_projection` / commercial API | Explicit safety input available only to direct callers | Fresh confirmed source service events forwarded; no inference from a high risk number; R8 |
| pursuit and Prospect Fit inputs | Expired inputs lost history IDs; fallback cohort could ignore age | Retained historical IDs/state, expired structural/access evidence Unknown; R1/R2 |
| Prospect Fit / Data Coverage / action receipts | Incomplete version/trace metadata | Versioned exact contributions, coverage score and queue sort-key trace; section 15 |
| `CommercialToolSession` | Public/overall risks absent from canonical decision read | Same server-owned wrapper, separate narratives and numeric trace; section 15 |

Tests added rather than weakening existing assertions. The first Tier 3 full run had 863 passes / 3 failures caused by lightweight adapters missing settings/clock methods. Provider-based compatibility fallbacks fix those without changing the tests. Later final results supersede this checkpoint.

- Item 3.3 prioritizes already demonstrated Boeing/Kratos and Medical Device context. No additional real-company risk allegation was fabricated to satisfy the SEC/WARN wish list. The high/low-confidence risk exercises remain explicitly fictional. No SAM.gov, USAspending, SEC or WARN fact is claimed as newly verified for these scenarios.

### Item 3.3 research sources

FDA's September 17, 2026 CDRH update links a draft PMA electronic-submission template guidance, docket FDA-2026-D-9429. Verified https://www.fda.gov/medical-devices/medical-devices-news-and-events/cdrh-new-news-and-updates and https://www.fda.gov/regulatory-information/search-fda-guidance-documents/electronic-submission-template-premarket-approval-applications-pma on 2026-09-20. Publisher: US FDA. Stored as aggregate regulatory context, not an effective legal requirement, customer need, or risk allegation. Scope, report date, record ID, source tier, missing information and freshness are explicit. No direct quote is copied. Together with the Kratos release and Federal Reserve observations, these are the new verified public research records. The unverified historical Kratos references remain history; failed AIM-260/official-ID research is recorded above.

- Item 3.2 adds a read-only fallback for the medical G.17 series only when no persisted series exists. Persisted observations always win. The curated vintage remains explicitly selectable; unknown vintages do not fall back. No refresh, import or database write is performed. Public dates stay historical when the demo clock moves.

### Item 3.2 Medical Device coverage

Three fictional Southwest medical organizations provide one invoiced customer, two prospects (one designated partnership) and a fictional BTX site. The coverage register explicitly denies actual site qualification, predicted demand and M&A recommendation scores. It is separate from the public national series and visible in Medical Market Intelligence.

`medical_market.py` stores 32 verified G.17 N3391 observations, January 2024 through August 2026; August is 91.1064 (seasonally adjusted, 2017=100). Source: Federal Reserve Board, https://www.federalreserve.gov/releases/g17/Current/ipdisk/ip_sa.txt, retrieved 2026-09-20. Publication date 2026-09-18 is independently listed at https://www.federalreserve.gov/recentpostings.htm. Every observation stores source/publisher/event/retrieval dates, with observation month separate from release date. The excerpt hash is explicitly not a complete-download hash. `test_sample_medical_market.py`: 2 passed.

- Item 3.1 keeps reconciled transactions intact and records the missing APM monthly planning feed separately. Unknown feed coverage is not zero sales, a target shortfall, or a forecast. Three distinct fictional sites have resolved ERA invoice evidence. Partnership defaults require no database writes; persisted true/false designations override defaults. A null version explicitly means no persisted designation exists yet.

### Item 3.1 cross-BU planning

`planning_cases.py` supplies the missing-feed register and three sister-BU site histories. `/planning` exposes this context and both fictional strategic partnerships; the existing All/Exclude/Only filters consume that same projection. `test_sample_planning.py`: 1 passed, including override precedence and resolved invoice references.

- Tier 2 full-suite verification exposed two timing-dependent monitor failures (both passed in the focused rerun). Fixed their causes without changing tests: validate the held PostgreSQL session synchronously before starting its keepalive thread; check remaining optional-stage budget before building the briefing environment. Previously a subsecond deadline could enter optional projection after a timed-out collection, and a short cycle could end before its first heartbeat. These are local verification fixes, not integration-stub changes.

- Monitor collection receipts retain an operational timestamp so successive real collection attempts remain ordered. Business evidence age and operational-status evaluation use the configured as-of provider; a collection timestamp never refreshes a publication date.
- The existing API acceptance test expected an internal alert enum while the existing workflow test explicitly prohibited it. Section 15's plain-language requirement resolves this: both now require the existing human label. No scenario or assertion is removed.
- Tier 1 verification also exposed an unresolved-research visibility gap. Added `research_signal_briefs` to the shared Today projection and merged it into the Research library without admitting Kratos to canonical Map/directory records.

1. Used the existing isolated `C:/Users/Aruna/btx-sample-data-enhancement` worktree and branch. Unrelated changes in the original worktree are untouched.
2. Imported the complete supplied Downloads rubric DOCX to Markdown, preserving the original text and tables. The DOCX lacks the promised R1–R10 preamble; explicit user amendments are recorded separately and override its erroneous examples. R9–R10 text is NOT FOUND and has not been invented.
3. Kept the earlier preflight checkpoint as historical evidence, with a superseding status section. The nine-day Signal Confidence target is now 86.25, not 85.75.
4. Baseline backend execution uses the existing Python interpreter with this worktree's `src` first on the import path, an ephemeral SQLite URL, disabled monitor/AI configuration and an audit hook prohibiting socket connections. Existing app/test code can load protected reference files; their contents are not logged or used as new fixture source material.
5. Added opt-in `BTX_SAMPLE_ENHANCEMENT_ENABLED=true` for the new scenario view. This preserves the old release fixture/hash and keeps fixture selection out of CONNECTED mode. No seed/import command or database write is required to select this view. Existing IDs and shared graph catalog remain present; original commercial scenarios remain available with the flag off.
6. Created a separate Docker Desktop PostgreSQL 16 container `btx-sample-enhancement-pg`, bound only to `127.0.0.1:57379`, database `btx_omni_e2e_sample_enhancement`. Applied the existing migration chain through 0040 locally. No new migration was created and no existing database was contacted. This resolves tests that require PostgreSQL rather than SQLite.

## Specification precedence

[Rubric v2.0](BTX_Omni_Scoring_Rubric_v2.0.md), including explicit user amendments, supersedes `docs/scoring/BTX_Account_Scoring_Working_Draft (1).docx`. Historical docs describing proportional reweighting do not specify current behavior. Executive deck slide 15's Action Priority weights and inverse-resilience internal risk formula are superseded by sections 8 and 13.

## Validation

### Item 2.5 remaining scoring vectors

| Vector | Target | Computed / assertion |
|---|---|---|
| Prospect Fit | 80 | 80; `test_private_aerospace_prospect_fit_80_and_low_distribution` |
| PWIN | 66.25 Developing | 66.25 Developing; qualified fictional procurement role, no named influencer |
| Delivery | 72.5 B | 72.5 B |
| Failed mandatory delivery | 78.75 weighted B+, Blocked | 78.75 B+, displayed Blocked; no eligible point score |
| Incomplete | 68–83 | 68–83; requirement-fit 57/80, budget factor missing |
| Data Coverage | 85 | 85; 10-point history and 5-point risk-history inputs missing |
| Public / internal / legal floors | 75 / 80 / 85 | 75 / 80 / 85; legal case blocks execution |
| Convergence | +5 only with linking evidence | 75/75 risks produce 80 with recorded link; 60/60 without link remains 60 |
| Independent vs syndicated origins | 3 vs 1 | 100 vs 25 corroboration factor points; separate evidence IDs retain shared origin for copies |
| Low distribution | Priority <50, Fit <50, Confidence Low | Complete Priority 28.95; Fit 31.25; confidence 37.75 Low |
| Expired / contradictory evidence | Unknown, no reweighting | Stale and Conflicting capacity factors yield ranges, no point score |

Assertions: `test_sample_golden_tier2.py` plus regional/external-risk tests. The live Fictional Watch ledger stores qualified, blocked, incomplete, low, stale and conflicting pursuit variants, and a separately labeled computed what-if lab. Floor examples are explicitly band-table teaching cases, **not measured customer conditions**. The lab includes its input bands, evidence, rule versions and computed receipts in the model's history context.

Before/after (section 11): the old PWIN gate required a named real-person interaction even though the rubric allows a verified role contact without interaction. Now a role can qualify only with current, opportunity-scoped verification and a resolvable source document; removing that proof makes PWIN ineligible. Stale/conflicting pursuit observations now expose their evidence state rather than silently dropping into generic missingness. Tests cover both changes. Existing tests were not weakened.

### Item 2.4 relationship journeys

`relationship_cases.py` authors one fictional manufacturing goal with two older accepted inspection orders and current machining/inspection coordination evidence. The live canonical graph/ranking service produces distinct 2-, 3- and 4-edge routes; the 4-edge route outranks the shorter older route. It stores its separate `BTX_RELATIONSHIP_POC_1` receipt, edge dates/source IDs, factor reasons and explicit weakest link. An unsupported fictional-company/Boeing link is excluded from the graph and displayed separately. `test_j8_j9_longer_evidenced_route_beats_shorter_older_route` verifies ordering, dates, stable IDs and no cycles/duplicates.

Before/after: added a narrowly typed commercial-fit template for an evidenced manufacturing handoff; no personal-access template or probability score was added. New components now have explicit source and facility keys required by the existing graph (missing keys previously crashed the enhanced scenario). Monthly BU allocations are derived from actual synthetic line ownership rather than assigning every new record to ERA. Relationship query defaults now use the business clock. No new account/capability enum value, schema or integration change.

### Item 2.3 external-risk exercises

Added a clearly **UNCONFIRMED fictional** consolidation hypothesis (severity 76.25, confidence 37.75 Low, Validate immediately) alongside the fictional high-confidence exercise (76.25, confidence 88.75 High, Escalate now). Source locators, publisher, dates, scope, mitigation and applicability questions are retained; both carry `curated_monitor_style`, synthetic/SAMPLE and no real-person attribution. `test_sample_external_risk.py` verifies the two dispositions and unconfirmed wording.

Decision: these quantitative adverse cases remain fictional rather than attaching invented affected-revenue/backlog percentages to a real SEC/WARN disclosure. No real adverse filing with the complete required quantitative inputs was verified. This is an explicit research gap, not a live external-risk monitor claim. The product can demonstrate the mechanics but cannot claim sourced adverse intelligence for these fictional subjects.

### Item 2.2 expansion

`providers/sample/expansion.py` joins the verified Kratos/Boeing public development to Boeing's separate synthetic dispatch/program history, a current synthetic inspection-fixture quote and two BU scopes. `commercial_briefing` and the model's history read expose the joined context while explicitly retaining Unknown need and an unsupported BTX/JDAM-LR edge. Fixture assertion: `test_j5_public_signal_and_synthetic_history_join_without_inventing_supply`.

Decision: AIM-260 was not imported. Searches located company and secondary reports and the government release URL https://www.war.gov/News/Releases/Release/Article/4603380/department-of-war-signs-framework-agreement-with-lockheed-martin-to-increase-pr/ (September 17), but government retrieval returned 403 and the defense.gov alias was inaccessible on September 20. The user's primary-government verification condition was not met. Used the already verified Kratos company release instead. No classified program or component assignment was invented.

### Item 2.1 regional prospecting

`providers/sample/regional.py` adds nine explicitly fictional organizations/sites across six markets and a fictional BTX site, surrounding the existing Tier 1 Fictional Watch customer (new fictional Southwest operating-site pin). This supplies ten nearby stops, plus the origin. Map/list ID sets match; HQ and operating sites differ, NAICS/program/website/hypothesis/role-gap context is visible in marker panels. Placeholder `.example` websites are not operating companies. Top 100 membership on Fictional Southwest Aero Partner is explicitly a SAMPLE designation, not membership in the real BTX list. Tests: `test_sample_regional.py`, two passed.

Decision: existing verified-site projections had no Arizona origin. A new Boeing job posting confirms Mesa operations (Boeing, September 3, 2026, retrieved September 20: https://jobs.boeing.com/job/mesa/experienced-or-mid-level-manufacturing-operations-analyst/185/100137880336), but does not verify precise site coordinates. It was therefore **not** used to fabricate a real map pin. The existing fictional customer is the origin instead. No real-site fact was added from protected references. Distances remain straight-line, no travel durations or meeting confirmations are invented.

### Item 1.6 narrative and model evidence

New quote notes, revision reasons, service narratives, function-only CRM notes, fictional program descriptions, capability constraints and mitigation notes live on the source-shaped records. `CommercialToolSession` now passes the engine's exact and displayed numeric contribution, raw observation, evidence state, period, rule version, blocked weighted result and counterfactual text to Gemini; it previously stripped several of these fields. The model is not asked to recalculate totals.

The fixture-backed action queue now uses a leaf-computed RFQ score of 94, the service-computed public-risk disposition, and internal cooling work, in ranks 1/2/3. A different fictional customer has a confirmed synthetic safety-stop class-0 item. There are no invented named contacts or warm introductions. Fictional account briefings explicitly disclaim public verification.

Local PostgreSQL full-run checkpoint: **829 passed, 3 failed**, no collection/setup errors and no expected failures (832 tests collected before later fixture additions). Failures were: an old fallback assertion expecting the enum rather than the friendly alert label; an account-level score-ranking assertion inconsistent with rubric sections 1/6; and a cross-surface test freezing the retired wall clock rather than the business clock. The first is addressed by consistently requiring friendly labels (section 15); the second now asserts scoped-opportunity behavior, and the third freezes the clock provider (R1). No test was removed or deselected. The later final tier run supersedes this checkpoint.

### Item 1.5 golden vectors

| Vector | Target | Computed | Fixture-backed assertion |
|---|---:|---:|---|
| Signal Confidence, 9 days | 86.25 High | 86.25 High | `test_requested_nine_day_confidence_target` |
| Signal Confidence, 3 days | 88.75 High | 88.75 High | `test_three_day_confidence_target` |
| Opportunity Priority | 81.75 High, Qualified/Durable | 81.75, YES/YES, Best Bet | `test_opportunity_81_75_with_independent_qualified_durable_gates` |
| Internal Commercial Risk | 52.5 Moderate | 52.5 Moderate | `test_internal_risk_52_5_from_reconciled_transactions` |
| Public Event Risk | 76.25 High, Escalate | 76.25 High, Escalate | `test_public_internal_and_combined_risk_are_separate` |
| Overall customer risk | 62.00, no uplift/floor | 62.00, no uplift/floor | same assertion |
| Customer Health | 60 Watch | 60 Watch | `test_health_watch_60_from_reconciled_transactions` |
| Other Health bands | Healthy / At risk / Critical | 96.25 / 40 / 17.5 | `test_health_distribution` |
| Queue | class 0, risk, RFQ 94, cooling | same order | `test_action_queue_classes_dominate_raw_score` |

New fictional customers are entirely authored synthetic data. Monthly histories reconcile to orders, dispatches, acceptances, revenue, invoices and payments. Internal risk's raw leaves include 18% bookings decline, 15% overdue open quote value, 2.5 months backlog, one active function, 7.14% BU exposure and one noncritical open case. Historical transactions retain their dates while the observation snapshot is current; shifting actual history to the demo date would destroy the longitudinal model.

The Opportunity Priority target is reachable with a different rule-consistent leaf decomposition than its illustrative example: 23.1 + 19.75 + 12 + 8.4 + 10 + 8.5. The test docstring records this. The rubric omits a make/buy leaf table; retained the existing SOURCES_EXTERNALLY=100, MIXED=60, MOSTLY_CAPTIVE=30 mapping as an explicit implementation decision, not fabricated source text.

Fictional public-risk exercises use `sample://` locators, not counterfeit SEC URLs. The scoring service permits arithmetic for explicitly tagged fictional SAMPLE exercises while retaining `synthetic=True` and refusing canonical real-world seller recommendation eligibility. There is no assertion of a real consolidation. Eight Tier 1 fixture-vector tests pass.

### Items 1.4 and 1.4a

Kratos source event date **2026-08-24**, retrieved **2026-09-20**, publisher **Kratos Defense & Security Solutions**. Required investor URL: https://ir.kratosdefense.com/news-releases/news-release-details/kratos-providing-spartan-j85-engines-support-boeing-jdam-lr (403 on this retrieval). Verified primary corporate mirror: https://www.kratosdefense.com/newsroom/kratos-providing-spartan-j85-engines-to-support-boeing-jdam-lr-production-contract (date and J85 production at Auburn Hills explicitly stated). The company mirror and syndicated release are one origin, not independent corroboration.

Official-source SAM.gov/DLA/USAspending/SBIR CAGE/UEI searches yielded no verified record. Secondary directories surfaced candidates but were not accepted as official proof; IDs stay null. Oxford is retained as superseded stale history, not Conflicting. The older trade and entity URLs supplied by the user remain labeled user-supplied history, not newly verified research. No contact names were imported.

Computed Signal Confidence: source 22.5 + parent identity 12.5 + specificity 20 + one origin 3.75 + 27-day freshness 5 = **63.75 Medium**. No numeric confidence was hand-set. Exact site address/coordinates and authoritative entity ID remain unresolved, so publication stays research-only; no premature canonical prospect or map marker. Need stays Unknown. A separate reviewed parent-identity observation is now usable by the scoring service without pretending the app already has a canonical prospect.

The visible brief labels `curated_monitor_style`, the sourcing-role gap, fit hypothesis and unsupported BTX→JDAM-LR link. Raw source metadata and narrative travel with `seed_context`; the source brief can be inspected without Gemini. Two Kratos fixture assertions pass. Public brief freshness now uses the event's rubric window, not a collector's 48-hour polling policy (R1).

### Items 1.2 and 1.3

New source: `providers/sample/enhancement.py:boeing_recovery`. Two quote revisions, one order/line (292 units at $980), two partial dispatches (100 + 46), 146 remaining and exactly $143,080 open. Dates are relative to the configured anchor. Recovery is as-of +6, PENDING, not buyer accepted; includes owner role, due date, inspection dependency, alternatives and detailed narrative. Every new commercial record is synthetic/SAMPLE. There are no invented people, emails or introductions.

The selected ledger flows through the existing commercial projection, fulfillment, evidence API and Omni read service. API completion is guarded by verified, action-scoped inspection release and buyer-acceptance evidence; the proposed plan alone is insufficient. Four fixture tests pass, covering arithmetic, referential integrity, shifting dates, evidence requirements and preserving canonical IDs. Historical monthly rows are derived from transactions and are not independent invented totals.

### Scoring alignment (amendment 2)

| Owner | Before | After / authority |
|---|---|---|
| `families.assess` | No explicit evidence state; version V2 | V2.0 version on assessments; Stale/Unknown/Conflicting factors contribute no known points; historical IDs retained; section 2 fixed-weight ranges |
| `public_rules`, `public_inputs` | API factor named reversibility despite mitigation bins | Mitigation key throughout; section 7/R3. Existing `risk_mitigation` leaf inputs map unchanged: unavailable=100, no plan=75, not started=50, underway=25, fully mitigated=0. No invented translation of ambiguous legacy prose |
| `public_risk_assessment` | Stale observations retained numeric risk | Expired public risk becomes Unknown with 0–100 range, retained history and no escalation disposition; R1 |
| `health_inputs`, `risk_inputs` | No snapshot expiry | Explicit snapshot observation dates expire transaction factors after two days; employment/access after 30, structural history after 180; R6. Historical transaction age does not erase longitudinal history when freshly reviewed |
| pursuit inputs, qualification gates, commercial observations | Same-day review only | Evaluate dated review against as-of and the applicable 2/30-day window; sections 3, 6, 11, 12 |
| `customer_risk_projection` | Could not forward convergence/override evidence | Explicit optional evidence IDs forwarded; absent inputs produce no uplift/override; R8 |
| `families.assess` | No generic band/counterfactual fields | Add rule version, weighted score/band (including blocked cases), displayed band and factor-specific counterfactuals; sections 12/15 |
| `prospect_fit_projection` | Default evaluation frozen at provenance timestamp | Default evaluation uses the configured clock; explicit historical replay remains supported |

No replacement of the already-correct direct Internal Commercial Risk or triage-class Action Priority formulas. No schema migration or integration-stub changes. The generic API stores factors in dictionaries, so no closed frontend reversibility field existed to rename.

Test changes: the two strict xfails now assert the corrected passing targets (amended section 4 and R3). `test_scoring_v2_completion` checks `mitigation` instead of the retired key, justified by section 7. No test is deleted or weakened. Focused scoring suite: **88 passed** before fixture work. Frontend baseline: typecheck, lint and build passed.

The original no-socket baseline guard was too broad for Windows asyncio's loopback self-pipe. That run was interrupted and is not a valid product baseline. Revised isolation allows loopback only. Its first actual failing assertion concerns the older August cross-BU scenario after the clock shift; fixtures must be integrated before judging final regressions.

### Item 1.1 clock

Added `core/clock.py`, with fixed configurable `DEMO_AS_OF_DATE=2026-09-20`, inclusive expiry and relative fixture dates. Runtime observations previously used August 31; Today mixed that with wall-clock public evaluation. Both now use the provider. Public brief evaluation and catalog provenance default to the same clock. Explicit timestamps remain supported for historical replay. Authentication, provider accounting and retry timers remain operational clocks, not evidence-age clocks.

`test_demo_clock.py` covers advancing evaluation beyond the two-day expiry while preserving the observation, plus a wall-clock prohibition across scoring and provider fixture modules. The final guard also covers business-date API and explanation paths. Clock plumbing is complete for these paths; operational security/collection/deadline timers intentionally remain independent.

Historical pre-implementation checkpoint: focused baseline 73 passed; preflight probes 80 passed, 2 expected failures. Both expected failures now pass under the corrected authority. The final full-suite results above supersede this checkpoint; all tier tags follow successful verification.
