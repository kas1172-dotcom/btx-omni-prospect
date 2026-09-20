# SAMPLE enhancement preflight

## Resumed preflight 2026-09-20

The previous checkpoint below is historical, not the current authority. The supplied Downloads DOCX has now been imported as [Rubric v2.0](../product/BTX_Omni_Scoring_Rubric_v2.0.md). Its full factor and band tables govern; the user's amended nine-day target is 86.25. Scoring changes and local additive migrations are authorized. Existing tests may load the two protected reference files, but this task must not inspect or derive new fixture content from them. The prior collection blocker was an audit-hook restriction, not an application defect.

Confirmed alignment work: public risk still exposes `reversibility`; public risk retains numeric stale inputs; internal snapshots lack two-day expiry; pursuit reviews require same-day dates; risk projection does not expose explicit convergence/override inputs; SAMPLE runtime clock is August 31. Core direct internal risk, queue classes and weighted missing-factor ranges already exist. Preserve those and extend tests rather than replace the scoring engine. No migration is currently required.

The available DOCX lacks the promised R1–R10 preamble. The imported Markdown labels explicit user resolutions R1–R8 and records R9–R10 as unavailable. No absent resolution text is represented as supplied authority. See the report decision log.

## Status and blocking input

Preflight checkpoint only. Tier 1 is not implemented and Tier 2 has not started.
Base commit: `68cb633`; branch: `sample-data-enhancement`; isolated worktree:
`C:/Users/Aruna/btx-sample-data-enhancement`. The original worktree has unrelated
uncommitted network work and was not edited. Current declared schema head is
`0040_network_visibility` (`backend/src/btx_omni/core/release.py`), not the 0038
head in the preceding audit. No database connection or migration was performed.

**The authoritative BTX Omni Scoring Rubric v2.0 is NOT FOUND.** The only
tracked scoring DOCX is `docs/scoring/BTX_Account_Scoring_Working_Draft (1).docx`.
Its section 5 ends with proportional reweighting of missing factors, and its
appendix B describes other scores as future work. It is not the requested v2.0
authority. Consequently a complete factor-by-factor normative diff, definitive
leaf-vector solver and verified grade/band acceptance cannot be completed yet.
Using today's implementation as its own scoring authority would conceal bugs.

There is also a task arithmetic conflict: the unchanged single-primary-source
vector totals 86.25 at nine days, rather than the requested 85.75. See
`docs/product/RUBRIC_ERRATA.md`. The source document or a clarified normative
table is needed before claiming rubric-correct sample results.

The two excluded workbook JSON files were neither opened nor used to derive
content during this task. A guarded full-suite attempt reached application
startup during test collection, then stopped before opening the excluded file.
No sample environment was successfully constructed.

## Live scoring owners and known comparisons

Paths in this section are relative to `backend/src/btx_omni/`.
"Matches" below means matches the explicit task rules, not certification
against the unavailable complete document.

| Family | Current factors and weights | Comparison status |
|---|---|---|
| Signal Confidence | source reliability 30, entity match 25, specificity 20, independent corroboration 15, freshness 10 | `modules/scoring/families.py:FAMILIES`; `public_inputs.py:public_signal_assessment`. Quarter freshness matches 10/7.5/5/0. Nine-day target differs by +0.50. Full source/entity/specificity bands need v2.0. |
| Opportunity Priority | durability 30, manufacturing fit 25, addressable work 15, momentum 10, strategic target fit 10, commercial adjacency 10 | `account_attractiveness.py:FACTORS`; selected through `commercial_decisions.py:opportunity_decisions`. Complete leaf bands exist in code, but normative comparison is blocked. |
| Prospect Fit | cohort 30, manufacturing fit 25, scale 15, outsourcing 15, archetype 10, access 5 | `prospect_fit.py:_DEFINITIONS` and `_points`. Uses 30-day access / 180-day other reviewed evidence. Full band comparison blocked. |
| PWIN | buyer access 25, competitive position 20, requirement fit 20, budget/process 15, price 10, track record 10 | `families.py:FAMILIES`, `pursuit_inputs.py`. Scoped evidence and pursuit eligibility checks exist; normative bins blocked. |
| Delivery Feasibility | capability 30, schedule 25, material 15, quality 15, margin 10, coordination 5 | `families.py:FAMILIES`, `pursuit_inputs.py`. Corrected example computes 72.50. Full grade/band comparison blocked. |
| Customer Health | trajectory 30, relationship coverage 20, engagement cadence 20, backlog 15, relationship history 10, risk history 5 | `customer_health.py:health_inputs`; normative thresholds and health labels need v2.0. |
| Internal Commercial Risk | momentum 30, pipeline 20, backlog 15, engagement 15, concentration 10, friction 10 | `internal_risk.py:risk_inputs`; direct risk score, not 100 minus health/resilience. |
| Public Event Risk | impact 30, materiality 20, imminence 15, persistence 15, breadth 10, reversibility 10 | `public_rules.py:risk_points` consumes mitigation observations, but the factor key is still `reversibility`, contrary to the requested `mitigation`. |
| Public risk rollup | maximum confirmed active event, +5/+10 for additional qualifying independent domains | `families.py:public_risk_rollup`; no source-count inflation in this function. Full normative comparison blocked. |
| Overall Customer Risk | 60% internal + 40% public; conditional +5 convergence; public critical floor 75, internal critical floor 80, override floor 85 | `families.py:overall_customer_risk` matches supplied arithmetic/floors. Application wrapper does not pass convergence or critical-override evidence (see below). |
| Action queue | classes 0/1/2/3; scored before incomplete; descending score or upper bound; due, created, ID | `action_priority.py:rank_actions` and `action_sort_key` match supplied queue rules. Excludes completed/canceled/dismissed/snoozed/duplicate/invalid and deduplicates stable keys. |
| Data Coverage | usable configured weight / 100; field presence also returned | `families.py:assess`; missing factors retain weights and ranges, no proportional reweighting. |

The generic assessment stores rule version, per-factor evidence, raw values,
weights, contributions, bounds, reasons and eligibility. It does not universally
emit a dedicated "what would change the result" field; additive narrative
evidence needs to be threaded into existing explanation inputs without changing
response contracts. Source: `families.py:assess`.

### Confirmed gaps against the task

1. **Clock fragmentation.** `api/runtime.py:PocRuntime.observed_at` hardcodes
   2026-08-31. `api/today.py` passes wall time for public assessments;
   `api/relationships.py` defaults the query date to wall time. Commercial
   scoring uses each ledger's `as_of`. `core/config.py:Settings` has no
   DEMO_AS_OF_DATE setting. Authentication and audit clocks must remain separate
   from any future demo evaluation clock.
2. **Internal freshness absent.** `customer_health.py:health_inputs` and
   `internal_risk.py:risk_inputs` do not expire transaction/review evidence at
   two days. Recent transaction dates alone cannot implement the shift-to-Stale
   requirement. Current historical transactions must remain historical; their
   review/snapshot freshness must not be confused with original transaction time.
3. **Pursuit freshness too strict.** `pursuit_inputs.py:pursuit_inputs`,
   `commercial_inputs.py:commercial_attractiveness_inputs` and
   `opportunity_gates.py:opportunity_gates` require review date equal to as-of,
   rather than the task's inclusive two-day internal evidence window.
4. **Public stale evidence remains numeric.** `public_inputs.py` sets freshness
   to zero after the window but retains other Signal Confidence contributions.
   The complete single-source probe remains 78.75 at 31 days. Its seller
   recommendation flag is false. `public_risk_assessment` does not age out its
   risk-factor observations; numeric severity and a disposition can remain.
   This differs from the task's stale-as-Unknown policy and needs scoring-owner
   clarification, especially since the task also explicitly assigns stale
   confidence freshness zero.
5. **Public factor key mismatch.** `risk_severity` exposes `reversibility`,
   although prose says mitigation and inputs use `risk_mitigation`. Renaming
   this key would touch scoring and API contracts, prohibited here.
6. **Rollup evidence is not wired through the application wrapper.**
   `families.py:customer_risk_projection` calls `overall_customer_risk` without
   `convergence_evidence_ids` or `critical_override_evidence_ids`. Direct unit
   vectors could exercise those branches but cannot demonstrate the application
   behavior by adding fixture data alone.
7. **Uniform counterfactual traces absent.** Existing scores have evidence and
   arithmetic, but not a common stored counterfactual field; narrative wiring
   must use supported payloads and explanation contracts.

These are requests for the scoring/integration owner, not changes made here.
No scoring file, response shape, cross-module signature, account ID or
capability value was modified. No migration has been established as necessary.

## Entity and persistence map

All paths below are under `backend/src/btx_omni/` unless stated otherwise.

| Entity | Existing representation and required fit |
|---|---|
| Account / prospect / site | `domain/accounts.py:CanonicalAccount`, `AccountFacility`; public identity and relationship provenance are separate. Durable promotion uses `persistence/durable_accounts.py` and `monitor/promotion.py`. A stale location must not become a canonical pin. |
| Program / component / capability / BU | `domain/programs.py`, `domain/capabilities.py`, `domain/btx.py`; catalog IDs must remain stable. Enriched commercial programs/components have source payloads in `persistence/commercial_schema.py`. |
| Quote / revisions / line items | `domain/quotes.py:CommercialQuote` and `CommercialQuoteLineItem` for projections; ledger collections `quotes`, `quote_revisions`, `quote_lines` own accepted/current revision links. Integer minor units, currency, quantities and exact line totals are validated by `modules/commercial/ledger.py:validate_commercial_account`. |
| Order / lines / partial shipments | `domain/orders.py:Order`; detailed ledger collections `orders`, `order_lines`, `shipments`, `cancellations`, `acceptances` support partial fulfillment. Shipment dates must follow order dates, accepted revisions must exist, shipped plus canceled cannot exceed ordered. |
| Revenue / invoices / payments / monthly history | Ledger requires linked acceptance/revenue/invoice/payment records and reconciled monthly backlog continuity. Do not rewrite historical events to make review evidence fresh. |
| Service event / recovery plan | Ledger `service_events`, `fulfillment_plans`; lifecycle in `modules/commercial/lifecycle.py`. A proposal and its proposed date must remain separate from an accepted commitment. Boeing target implies 146 open units at 98,000 minor units each = 14,308,000 cents. |
| CRM company / contact / deal / activity | `domain/crm.py` dataclasses and `persistence/models.py` tables. Detailed ledger uses `contacts`, `role_targets`, `interactions`, `opportunities`; role placeholders can express gaps without fabricated people. |
| Capacity / pursuit inputs | Opportunity payload `scoring_inputs` holds raw scoped observations; `pursuit_inputs.py` requires linked evidence and a known delivery facility. No dedicated capacity table is necessary for these reviewed observations. |
| Signal / observation / evidence | `monitor/contracts.py:SourceObservation`, `RawEvidenceReference`, `NormalizedClaim`, `IntelligenceEvent`. Observation has publication/capture timestamps and structured payload; source metadata must preserve publisher, URL, event and retrieval dates. No dedicated `seed_type` dataclass field; curated provenance needs compatible payload storage/projection. |
| Relationships | `domain/relationships.py`; canonical projections and rubric under `modules/relationships/`. Keep unsupported fit/access assertions out of evidenced paths. Network schema additions in this base are unrelated and remain untouched. |
| Action / owner / due / completion evidence | `domain/work.py:Action` supports owner, due date, evidence IDs and typed context referents; database owner is `persistence/actions.py`. Additive fixture plans do not themselves prove completion enforcement. |
| Score / trace / explanation | `modules/scoring/families.py:FactorInput` / `assess`, `domain/scores.py`; adapters under `modules/intelligence/governed_explanation_adapters.py`. Trace must come from existing scoring functions, never hand-authored model numbers. |

The existing release import is byte-hash locked and account-crosswalk locked
(`persistence/import_commercial_sample.py:load_release_sample`). An additive
fixture therefore needs an explicit local composition path; editing that old
fixture would violate this task. The default sample builder reads an excluded
workbook file, so it cannot be the authoring/verification entry point here.

## Golden-vector readiness

| Requested vector | Verified current calculation | Status |
|---|---|---|
| Confidence 85.75 High at 9 days | 86.25 from 30 + 25 + 20 + 3.75 + 7.5 | Strict expected failure; requested arithmetic conflicts. |
| Confidence 88.75 High at 3 days | 88.75 from 30 + 25 + 20 + 3.75 + 10 | Arithmetic verified, full Monitor fixture still pending. |
| Opportunity 81.75, Qualified/Durable Yes | NOT VERIFIED | Need authoritative leaf bands before certification and end-to-end fixture. |
| Internal 52.5 / public 76.25 | NOT VERIFIED from raw scenario records | Both supplied totals are plausible weighted sums; this is not a solved fixture. |
| Overall 62.00 without floors/uplift | 62.00 | Exact Decimal computation verified. |
| Health 60 Watch; Healthy / At risk / Critical | NOT VERIFIED | Complete normative labels/bands and scenarios pending. |
| Queue risk / RFQ 94 / cooling + class 0 | Comparator inspected; underlying fixture scores NOT VERIFIED | Queue code matches supplied ordering rules. |
| Delivery corrected example 72.5 | 72.50 from raw band inputs | Arithmetic verified only; grade B is supplied by task. Tier 2 not implemented. |
| Other Tier 2 golden vectors | NOT VERIFIED | Authority blocked; no Tier 2 implementation started. |

No target was silently changed. Tests document the exact +0.50 discrepancy.
Full reachability search against v2.0 remains incomplete because its complete
band tables are absent.

## Bounded Kratos retrieval

Requested primary URL found:
https://ir.kratosdefense.com/news-releases/news-release-details/kratos-providing-spartan-j85-engines-support-boeing-jdam-lr

Publisher: Kratos Defense & Security Solutions. Event/publication date:
2026-08-24. Retrieval date: 2026-09-20. This retrieval was limited to locating
the requested release; no contact research was performed. The release supports
the supplied statement that expanded Spartan capacity is allocated to Boeing
JDAM LR. It identifies Auburn Hills as the J85 production facility, while the
supplied historical reference names Oxford. Preserve the stale Oxford reference
and flag site reconciliation; do not silently replace it or invent coordinates.
No executives, contacts or $35M unrelated-award associations were imported.
The URL is recorded here but the curated signal is not yet loaded in the app.

## Validation checkpoint

Before changes, 73 selected existing scoring tests passed in 2.98 seconds:
`test_public_signal_assessment.py`, `test_account_attractiveness.py`,
`test_customer_health_v2.py`, `test_internal_risk_v2.py`,
`test_pursuit_scoring_v2.py`. The interpreter was the existing backend venv,
with this worktree's `backend/src` first in `sys.path`; no dependency install.
Network access, `.env`, and both excluded JSON basenames were denied through
a Python audit hook. Database environment variables were set to in-memory
SQLite. Pytest plugin autoload and cache output were disabled.

New preflight tests use only pure scoring functions and fictional evidence
tokens. They do not load the application or sample environment. Full-suite
validation cannot truthfully pass while preserving the no-read rule: existing
application tests invoke `build_sample_environment`, which reads an excluded
file. Do not claim a full baseline from the 73-test subset.

After additions, the same 73 tests plus `test_sample_enhancement_preflight.py`
returned **80 passed, 2 xfailed in 3.75 seconds**. Expected failures are the
requested nine-day 85.75 target (current 86.25) and the mitigation factor key
(current `reversibility`). These expected failures document discrepancies;
they are not acceptance of Tier 1 or permission to change scoring code.

The guarded full-suite command (`pytest -q -p no:cacheprovider --maxfail=1 tests`)
stopped with **one collection error in 4.13 seconds**:
`test_api_acceptance.py` imports `app.py`, which constructs `PocRuntime`, calls
`build_sample_environment`, and attempts to read the excluded sanitized JSON.
The audit hook raised PermissionError before the file was opened. No full-suite
pass/fail baseline is available under that constraint. One pre-existing
Starlette/httpx deprecation warning was emitted during collection.

This checkpoint is a request for the missing v2.0 authority and resolution of
the nine-day confidence arithmetic before committing to normative fixture
generation. Tier 1 features and its end-to-end acceptance remain incomplete.
