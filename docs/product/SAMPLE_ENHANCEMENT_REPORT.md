# SAMPLE enhancement report

Status: implementation in progress; no tier certified complete yet.

## Decisions made without user input

1. Used the existing isolated `C:/Users/Aruna/btx-sample-data-enhancement` worktree and branch. Unrelated changes in the original worktree are untouched.
2. Imported the complete supplied Downloads rubric DOCX to Markdown, preserving the original text and tables. The DOCX lacks the promised R1–R10 preamble; explicit user amendments are recorded separately and override its erroneous examples. R9–R10 text is NOT FOUND and has not been invented.
3. Kept the earlier preflight checkpoint as historical evidence, with a superseding status section. The nine-day Signal Confidence target is now 86.25, not 85.75.
4. Baseline backend execution uses the existing Python interpreter with this worktree's `src` first on the import path, an ephemeral SQLite URL, disabled monitor/AI configuration and an audit hook prohibiting socket connections. Existing app/test code can load protected reference files; their contents are not logged or used as new fixture source material.
5. Added opt-in `BTX_SAMPLE_ENHANCEMENT_ENABLED=true` for the new scenario view. This preserves the old release fixture/hash and keeps fixture selection out of CONNECTED mode. No seed/import command or database write is required to select this view. Existing IDs and shared graph catalog remain present; original commercial scenarios remain available with the flag off.
6. Created a separate Docker Desktop PostgreSQL 16 container `btx-sample-enhancement-pg`, bound only to `127.0.0.1:57379`, database `btx_omni_e2e_sample_enhancement`. Applied the existing migration chain through 0040 locally. No new migration was created and no existing database was contacted. This resolves tests that require PostgreSQL rather than SQLite.

## Specification precedence

[Rubric v2.0](BTX_Omni_Scoring_Rubric_v2.0.md), including explicit user amendments, supersedes `docs/scoring/BTX_Account_Scoring_Working_Draft (1).docx`. Historical docs describing proportional reweighting do not specify current behavior. Executive deck slide 15's Action Priority weights and inverse-resilience internal risk formula are superseded by sections 8 and 13.

## Validation

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
