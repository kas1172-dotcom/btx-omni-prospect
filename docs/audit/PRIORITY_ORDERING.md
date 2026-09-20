# Today Action Priority ordering

Owner: `backend/src/btx_omni/modules/priority_ordering.py`. Integration: `backend/src/btx_omni/modules/command_center.py`. Frontend: `apps/web/src/features/today/Today.tsx` and `todayModel.ts`. This is Phase 3B, after existing admission and before presentation.

## Contract and order

Existing response fields remain intact. `PriorityMetadata` is the backend schema and `CommandPriorityItem` in `apps/web/src/types/api.ts` is the TypeScript contract. All additions are optional; new action projections populate them, while the separate validation lane is unchanged.

| Field | Meaning |
| --- | --- |
| `triage_class` | Integer 0-3; backend computed. |
| `nature` | RISK, OPPORTUNITY, or UNKNOWN; source mappings below. |
| `underlying_score` | Numeric 0-100 assessment value, or explicit range upper bound when incomplete. Null when no numeric assessment exists. Never a blended Action Priority score. |
| `score_kind` | OPPORTUNITY_PRIORITY: governed opportunity priority. RISK_SEVERITY: governed public/internal severity. CUSTOMER_HEALTH: supplied health/trend assessment, not silently inverted into risk. TIER_ONLY: ordinal severity fallback, numeric value null. NONE: no usable score. |
| `assessment_complete` | Known nature and confidence, a usable numeric score or tier, no recorded missing fields and no incomplete/blocked assessment status. |
| `high_importance` | Sole backend-owned High flag; class 0/1/2, or class 3 with known High risk severity or opportunity priority >=75. A range ceiling alone never sets High. |
| `hard_stop` | False by default. Only source `hard_stop is True` sets it. Neither OVERDUE_ORDER nor EXPORT_RESTRICTION automatically implies a stopped shipment/legal prohibition. |
| `alert_kind`, `status` | Internal source `type` and `status` copied only when present. No manufactured public status. |
| `triage_reason` | Short plain-language explanation rendered in rank/badge tooltips. |

1. Exclude COMPLETED, DONE, DISMISSED, HIDDEN, SNOOZED, DUPLICATE, INVALID, NO_LONGER_VALID, CANCELED and CANCELLED states, explicit completed/dismissed/hidden/snoozed/duplicate flags, and `valid=false`. A terminal copy suppresses that deduplication identity. No new dismissal persistence is implied.
2. Class 0: explicit hard stop. Class 1: RISK, severity >=70 or High/Critical tier, confidence >=70 or High tier. Class 2: same severity with explicit Medium/Low confidence. Class 3: every other admitted executable item, including unknown nature/confidence.
3. Complete assessments before missing-input assessments within each class.
4. Underlying numeric score descending. Incomplete assessments use `score_range.high` when available. Tier-only fallback uses Critical=100, High=75, Medium/Moderate=50, Low=25 internally; these are ordinal positions, not returned numeric measurements. Numeric values take precedence over conflicting tier labels. Unknown scores sort last.
5. Due date ascending, missing last; then `created_at` or existing `observed_at`, oldest first, missing last; then stable ID ascending. Offset timestamps are compared as instants. Date-only deadlines use their unshifted calendar order. Source is never an ordering key.

`priority_briefing` is the full open canonical list. `action_priorities` retains its existing public-only shape and follows the public subsequence of that list. Counts use surviving eligible items. Current intelligence, radar, and market contextual ordering remain separate. Validation rules and placement remain unchanged.

## Internal alert mapping

Source enum: `backend/src/btx_omni/domain/alerts.py`. Producer: `modules/alerts/commercial.py`. All current alerts carry severity tiers, source evidence IDs, provenance, status, and observed_at. They do not currently carry quantified risk/opportunity assessments, due dates or original issue creation dates. Numeric assessments are consumed if explicitly supplied, never synthesized from actual_value or monetary amount.

| Alert kind | Nature | Judgment / rationale |
| --- | --- | --- |
| CUSTOMER_INACTIVITY | RISK | Explicit absence of bookings; existing inactivity threshold establishes a negative condition. |
| BOOKINGS_DECLINE | RISK | Explicit decline against prior period. |
| STALE_QUOTE | RISK | Existing stale high-value open quote condition. Does not prove lost revenue. |
| OVERDUE_ORDER | RISK | Explicit promised-date breach. Does not establish a hard stop. |
| QUOTE_FOLLOW_UP | OPPORTUNITY | Follow-up on executable open business; lateness alone is not confirmed severe risk. |
| CRM_INACTIVITY | OPPORTUNITY | Conservative follow-up classification; missing contact is not evidence of lost demand. |
| CROSS_BU_COORDINATION | OPPORTUNITY | Coordination/expansion work, not evidence of commercial harm. |
| INTELLIGENCE_COMMERCIAL_CONTEXT | UNKNOWN | Review request alone does not establish positive or negative direction. Class 3. |
| Missing or future unrecognized kind | UNKNOWN | Class 3; never inferred from ID or reason text. |

Confidence: explicit `evidence_confidence` score/band wins. Otherwise `provenance_state=CONFIRMED` with evidence IDs means High, including governed SAMPLE records. Missing or non-confirmed provenance means unknown, not Low. SAMPLE is still labeled SAMPLE; confidence describes support inside its sample scenario, not a live fact. Explicit missing_fields and score/confidence data_coverage.missing_fields prevent complete status.

## Public event mapping

Source enum: `monitor/ontology.py`; read only. `SignalBrief.risk_severity` is produced by `modules/scoring/public_inputs.py` for negative event types or explicit negative risk-direction evidence. Its presence establishes RISK even for an otherwise ambiguous/opportunity type. No Monitor implementation changed.

| Event type | Default nature | Judgment / rationale |
| --- | --- | --- |
| CONTRACT_REDUCTION | RISK | Explicit reduction. |
| PROGRAM_CANCELLATION | RISK | Explicit cancellation. |
| FACILITY_CLOSURE | RISK | Explicit closure. |
| WORKFORCE_REDUCTION | RISK | Explicit reduction. |
| FINANCIAL_DISTRESS | RISK | Explicit distress. |
| EXPORT_RESTRICTION | RISK | Restriction, but no inferred hard stop. |
| PRODUCTION_DELAY | RISK | Explicit delay. |
| CONTRACT_AWARD | OPPORTUNITY | Potential demand; does not assert a BTX award. |
| SOLICITATION | OPPORTUNITY | Executable pursuit candidate after existing admission. |
| FACILITY_EXPANSION | OPPORTUNITY | Expansion candidate. |
| CAPACITY_EXPANSION | OPPORTUNITY | Expansion candidate. |
| NEW_FACILITY | OPPORTUNITY | New demand candidate. |
| PROGRAM_LAUNCH | OPPORTUNITY | New program candidate. |
| PRODUCTION_RAMP | OPPORTUNITY | Increased production candidate. |
| PRODUCT_LAUNCH | OPPORTUNITY | New product candidate. |
| SUPPLIER_AWARD | OPPORTUNITY | Supplier-related demand candidate; does not assert BTX participation. |
| CAPITAL_INVESTMENT | OPPORTUNITY | Investment candidate. |
| PARTNERSHIP | OPPORTUNITY | Potential pursuit/expansion, subject to explicit risk override. |
| REGULATORY_APPROVAL | OPPORTUNITY | Approval enables possible activity; no regulatory-risk inference. |
| GOVERNMENT_FUNDING | OPPORTUNITY | Funding candidate. |
| GRANT_AWARD | OPPORTUNITY | Funding candidate. |
| UNCLASSIFIED_PUBLIC_UPDATE | UNKNOWN | Direction absent. |
| CONTRACT_MODIFICATION | UNKNOWN | Could increase or reduce scope. |
| SUPPLY_CHAIN_CHANGE | UNKNOWN | Could improve or harm supply. |
| M_AND_A | UNKNOWN | Commercial impact can be positive or negative. |
| REGULATORY_CHANGE | UNKNOWN | Direction and applicability absent. |
| EXECUTIVE_CHANGE | UNKNOWN | Personnel change is not automatically risk/opportunity. |
| EARNINGS_SIGNAL | UNKNOWN | Direction not encoded in type. |
| BACKLOG_CHANGE | UNKNOWN | Direction not encoded in type. |
| Missing or future unrecognized event_type | UNKNOWN | Class 3 unless structured risk_severity establishes risk. |

Confidence comes only from `signal_confidence.score` (High >=70, Medium >=40, otherwise Low) or an explicit supported High/Medium/Low tier. No confidence is inferred from READY, priority_eligible, source URL, watch status, or recommendation text. Missing numeric confidence remains unknown; a partial range is not a High score.

Underlying risk uses `risk_severity`. An opportunity uses an explicit `evidence_package.deterministic_scores.opportunity_priority` assessment, if supplied. The current SignalBrief producer does not guarantee this score; absent scores remain NONE/null/incomplete, Class 3. Neither signal confidence, technical fit, nor account attractiveness substitutes for opportunity priority. Public hard_stop, lifecycle status and due_date are absent from the current SignalBrief schema; they remain unavailable rather than inferred. Existing stale-window admission still determines no-longer-eligible public items.

## Frontend and verification

`isHighImportance(item)` only reads `item.high_importance === true`; header, attention badge and lead-card treatment use it. The first three cards come from the unfiltered canonical list. Canonical worklist mode does not sort. User-selected alternate sorts affect displayed rows only; rank labels remain positions in the full canonical list. Missing metadata stays renderable and does not produce High badges.

`test_priority_ordering.py` covers all class/score boundaries, closed/duplicate exclusion, unknowns, public/internal interleaving, complete before partial, 100 deterministic random shuffles, date/age/ID ties, exhaustive enum mappings, backward-compatible schema and unchanged validation admission. `test_command_center.py::test_priority_projection_is_ordered_and_self_describing` changes its old internal-first/newest-first expectation to risk triage, interleaving and oldest-first ties. Frontend tests verify server-only importance and actual lead/header/row rendering.

## Deck discrepancy

The user reports executive deck slide 15 uses urgency 30, BTX impact 30, dependency 20, age 10, ownership gap 10. The supplied Action Priority rubric instead mandates exclusions, triage class, completeness, underlying score, due date, age and stable ID. This implementation follows the rubric and does not implement those deck weights. No deck file was provided or independently inspected. Owner decision: align the deck with the rubric or issue an explicit future policy revision.
