# SAMPLE enhancement report

Status: Tiers 1 and 2 verified; Tier 3 in progress.

## Tier checkpoints

Tier 2: **856 backend tests passed**, 8 dependency warnings, no deselection/xfail (202.94 seconds). Frontend typecheck, ESLint and production build passed; **84 frontend tests passed**. Ten more backend tests than Tier 1. Tag: `tier2-complete`.

Tier 1: **846 backend tests passed**, 8 dependency deprecation warnings, no deselection/xfail (373.08 seconds). Frontend typecheck, ESLint and production build passed; **84 frontend tests passed**. Compared with the first valid local PostgreSQL checkpoint (829 passed / 3 failed), all failures are resolved and new fixture assertions are included. Tag: `tier1-complete`.

Full backend command (from this worktree's `backend`, using the existing Python 3.11 interpreter): set `PYTHONDONTWRITEBYTECODE=1`, `BTX_DATABASE_URL` to the task-owned loopback PostgreSQL database, `BTX_MONITOR_MODE=disabled`, and an empty `BTX_GEMINI_API_KEY`; prepend the absolute local `src` to `sys.path`; install a Python audit hook rejecting non-loopback `socket.connect`; run `pytest.main(['-q', '--tb=short', '-p', 'no:cacheprovider'])`. Frontend commands: `npm run typecheck`, `npm run lint`, `npm run build`, `node --test --test-reporter=dot tests/*.test.mjs`. Existing reference JSON may be loaded by existing code, but was not printed, copied, edited or used to author additions.

## Decisions made without user input

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
| Low distribution | Priority <50, Fit <50, Confidence Low | Complete low pursuit; Fit 31.25; confidence 37.75 |
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

`test_demo_clock.py`: 2 passed. Covers advancing evaluation beyond the two-day expiry while preserving the observation, plus a wall-clock prohibition across scoring and provider fixture modules. Additional plumbing remains part of scoring alignment and fixture integration.

Previous checkpoint: focused baseline 73 passed; preflight probes 80 passed, 2 expected failures. Full-suite baseline is being established with the user-approved reference-file loading policy. Tier tags will only be created after verification.
