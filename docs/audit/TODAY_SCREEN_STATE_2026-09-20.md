# Today Screen Current-State Audit

Audit date: 2026-09-20. Branch: `codex/profile-ux-refinement`. This is a read-only code/runtime audit; the only artifacts written are this report and the requested screenshot.

## 1. Purpose and structure

### 1. Route, entry, and component tree

- Route: hash route `#/today`; unknown routes normalize to Today, and Today filter state is decoded from the URL. `apps/web/src/app/App.tsx:54`, `apps/web/src/app/App.tsx:187`, `apps/web/src/app/App.tsx:278`
- Entry: `App` loads `api.today()` and passes `commandCenter`, alerts, signals, accounts, filters, and navigation callbacks into `Today`. `apps/web/src/app/App.tsx:329`, `apps/web/src/app/App.tsx:411-415`
- API client: `GET /today` under the configured `/api` prefix. `apps/web/src/api/client.ts:45`, `backend/src/btx_omni/app.py:49-74`, `backend/src/btx_omni/api/today.py:13-17`
- Render tree: `App` -> `Today`; normal Today uses shared `Button`, `Disclosure`, `Empty`, `LoadingStatus`, `Panel`, `State`, `HighCardinalitySelector`, `WorklistPagination`, `AttentionBadge`, and `SignalBriefCard`. A commercial item can replace the normal body with `CommercialRecoveryBriefing`. `apps/web/src/features/today/Today.tsx:3-12`, `apps/web/src/features/today/Today.tsx:88-90`, `apps/web/src/features/today/Today.tsx:123-124`

### 2. Render order

| Order | Visible section/control | Evidence |
|---:|---|---|
| 1 | Header: `Today`, subtitle `Your next commercial decisions` | `apps/web/src/features/today/Today.tsx:90-91` |
| 2 | Loading or unavailable notice | `apps/web/src/features/today/Today.tsx:92-93` |
| 3 | All priorities / Public intelligence / Internal intelligence segmented-looking native buttons | `apps/web/src/features/today/Today.tsx:94-97` |
| 4 | Search priorities | `apps/web/src/features/today/Today.tsx:98` |
| 5 | Customer/prospect high-cardinality selector | `apps/web/src/features/today/Today.tsx:99` |
| 6 | Business unit select, then worklist order select | `apps/web/src/features/today/Today.tsx:100-101` |
| 7 | Three top-priority cards, derived from the filtered action-priority list | `apps/web/src/features/today/Today.tsx:103-110` |
| 8 | Lane counts: total, filtered, displayed, validation totals | `apps/web/src/features/today/Today.tsx:112` |
| 9 | Action priorities ranked list, 10 per page | `apps/web/src/features/today/Today.tsx:113-129` |
| 10 | Needs validation lane, hidden only on Internal intelligence | `apps/web/src/features/today/Today.tsx:130-143` |
| 11 | Collapsed `Market watch and source coverage` disclosure | `apps/web/src/features/today/Today.tsx:145` |
| 12 | Inside disclosure: Current public intelligence, Upcoming Radar, then Market Hubs | `apps/web/src/features/today/Today.tsx:146-148` |
| 13 | Recommended Customer watchlist and Watched programs | `apps/web/src/features/today/Today.tsx:149-152` |
| 14 | Coverage/source freshness and curated Public intelligence | `apps/web/src/features/today/Today.tsx:153-155` |

There are no standalone Defense or Commercial Aerospace worklist filters. Those labels are generated market-hub buttons inside the collapsed section; all seven canonical markets are backend-generated. `apps/web/src/features/today/Today.tsx:145-148`, `backend/src/btx_omni/modules/command_center.py:296-348`

### 3. Intended purpose

- Today is a seller decision queue: show who/what changed, why it matters, evidence/missingness, and a next step. `docs/planning/WORKFLOW.md:169`, `docs/planning/WORKFLOW.md:179`
- Priority cards must precede Market Hubs, while Radar/evidence stay compact. `docs/product/PHASE_21_FIGMA_RECONCILIATION.md:8`
- The Figma target calls for KPI/priority/evidence layout, but static urgency/count examples must be replaced with canonical ordering and actual SAMPLE/public disclosure. `docs/product/FIGMA_IMPLEMENTATION_BASELINE.md:55`, `docs/product/FIGMA_IMPLEMENTATION_BASELINE.md:102`
- Commit history confirms deliberate separation and outcome gating: `55eb7fa` separates the Intelligence library from Today priorities, `76fc7be` separates assessment outcome, `cae86ad` adds validation, `b150a8e` uses the live public clock, and `1a88472` establishes the command center. This is repository history, with current policy implemented at `backend/src/btx_omni/modules/command_center.py:84-103`.

## 2. Data flow

### 4. Sources by section

All Today sections use one frontend request, `api.today()` with no query parameters. Filters/search/sort/pagination are client-side and URL-backed. `apps/web/src/api/client.ts:45`, `apps/web/src/features/today/Today.tsx:17-20`, `apps/web/src/features/today/Today.tsx:50-64`, `apps/web/src/features/today/Today.tsx:72`

| Section | Response field/hook | Backend production path |
|---|---|---|
| Top cards/action list | `command_center.priority_briefing` | `today()` -> `CommercialAlertEngine.evaluate()` + `build_command_center()`; `backend/src/btx_omni/api/today.py:18-41`, `backend/src/btx_omni/modules/command_center.py:191-220` |
| Needs validation | `command_center.needs_validation_assessments` | validation gate and projection; `backend/src/btx_omni/modules/command_center.py:94-103`, `backend/src/btx_omni/modules/command_center.py:221-252` |
| Current/Radar | `current_signal_briefs`, `upcoming_radar` | Monitor health snapshot classified by timing/freshness; `backend/src/btx_omni/api/today.py:27-38`, `backend/src/btx_omni/modules/command_center.py:128-165` |
| Market Hubs/counts | `market_hubs`; count is current IDs + upcoming IDs | canonical market loop; `apps/web/src/features/today/Today.tsx:148`, `backend/src/btx_omni/modules/command_center.py:295-348` |
| Watchlists | `watched_accounts`, `watched_programs` | monitor watch targets; program IDs only from current/upcoming briefs; `backend/src/btx_omni/modules/command_center.py:254-293` |
| Coverage | `source_health_warnings`, `missingness`, hub coverage/gaps | monitor source states; `backend/src/btx_omni/modules/command_center.py:314-375` |
| Curated Public intelligence | `curated_reference_signal_ids`, resolved against separately loaded `signals` | IDs come from `/today`; records come from `/intelligence`; `apps/web/src/features/today/Today.tsx:65-68`, `backend/src/btx_omni/modules/command_center.py:405-409` |

### 5. Priority types, schema, samples

Frontend priority item fields are: `id`, `kind`, optional `outcome_lane`, optional `account_id`, optional `severity`, `reason`, optional `recommended_action`, `evidence_ids`, optional `observed_at`, `data_mode`, optional `lifecycle_state`, optional `watchlist_eligible`, optional `priority_reasons`, optional `signal_brief`, optional `business_unit_ids`, optional `event_id`. `apps/web/src/types/api.ts:96-98`

The nested public `SignalBrief` backend schema has 44 fields: identity/headline/change/why, account/program/market, publication/collection/freshness, evidence/source/data/resolution/promotion, watch/action/missingness/summary, language/summary mode/timing/watch reasons/facility, technical/confidence/risk/event type, analysis/relevance/eligibility/rationale/uncertainties/references/evidence package/revision/generation, assessment/version/geography/context. `backend/src/btx_omni/monitor/briefs.py:61-106`

Actual internal sample from the current runtime:

```json
{"id":"alert-bookings_decline-eaton-chandler-industries","kind":"COMMERCIAL_REVIEW","account_id":"eaton","severity":"HIGH","reason":"Bookings declined versus prior period","recommended_action":"Review lost demand and recovery plan.","evidence_ids":["priority-context-eaton-chandler-industries"],"observed_at":"2026-08-31T00:00:00+00:00","data_mode":"SAMPLE","business_unit_ids":["chandler-industries"]}
```

Its shape is produced at `backend/src/btx_omni/modules/command_center.py:191-205`; its exact templates come from `backend/src/btx_omni/modules/alerts/commercial.py:58-61`.

No public priority exists in the current runtime response. Fixture-derived public projection example, using all top-level priority fields that projection emits:

```json
{"id":"public","event_id":"public","kind":"PUBLIC_SIGNAL","outcome_lane":"ACTION_PRIORITIES","account_id":"acct-1","reason":"Review its explicit Customer context.","recommended_action":"Review the evidence.","evidence_ids":["evidence-1"],"observed_at":"2026-08-28T11:55:00+00:00","data_mode":"LIVE_PUBLIC","watchlist_eligible":false,"priority_reasons":[],"business_unit_ids":[],"lifecycle_state":"CURRENT","signal_brief":{"id":"public","headline":"Contract update reported","what_happened":"A governed source reported an update.","why_it_may_matter":"Review its explicit Customer context.","canonical_account_ids":["acct-1"],"canonical_program_id":"program-1","markets":["Defense"],"publication_timestamp":"2026-08-28T11:55:00+00:00","collection_timestamp":"2026-08-28T12:00:00+00:00","freshness":"CURRENT","evidence_ids":["evidence-1"],"source_url":"https://example.com/evidence","source_system":"official-source","data_mode":"LIVE_PUBLIC","resolution_state":"RESOLVED","seller_promotion_state":"RESOLVED_ELIGIBLE","what_to_watch":"Watch the source-supported date.","recommended_action":"Review the evidence.","missing_fields":[],"seller_summary":"Governed summary.","summary_mode":"DETERMINISTIC","event_timing":"OBSERVED","relevant_event_timestamp":"2026-08-28T11:55:00+00:00","watchlist_eligible":false,"priority_reasons":[],"analysis_status":"READY","commercial_relevance_state":"ESTABLISHED_COMMERCIAL_RELEVANCE","priority_eligible":true,"geographic_scope":"ACCOUNT"}}
```

The fixture values and expected public ordering/mode are defined at `backend/tests/test_command_center.py:12-53`, `backend/tests/test_command_center.py:258-278`.

### 6. Unified versus separate state

| Requested value | Actual source |
|---|---|
| Top three cards | First three of filtered `priority_briefing`; `apps/web/src/features/today/Today.tsx:48-53`, `apps/web/src/features/today/Today.tsx:103-104` |
| High-importance header/count | No separate high count exists. Card badges use severity/assessment; lane summary counts all items. `apps/web/src/features/today/Today.tsx:105`, `apps/web/src/features/today/Today.tsx:112` |
| All | `priority_briefing` plus separate validation lane, filtered with kind `ALL`; `apps/web/src/features/today/Today.tsx:17-20`, `apps/web/src/features/today/Today.tsx:48-52` |
| Public | Same two arrays, `kind === PUBLIC_SIGNAL`; `apps/web/src/features/today/Today.tsx:17-20`, `apps/web/src/features/today/Today.tsx:52` |
| Internal | `priority_briefing`, `kind === COMMERCIAL_REVIEW`; validation forced empty; `apps/web/src/features/today/Today.tsx:51-52` |
| Tab counts | No counts on the three tab buttons. Counts appear only in lane summary/panel kickers. `apps/web/src/features/today/Today.tsx:95-96`, `apps/web/src/features/today/Today.tsx:112-114` |
| Defense/Commercial Aerospace counts | Market Hub current + upcoming signal ID lengths, unrelated to `priority_briefing`. `apps/web/src/features/today/Today.tsx:148` |

Conclusion: action cards/list share a governed list, but validation, current, Radar, watchlists, and curated reference cards are separate projections/state. `backend/src/btx_omni/modules/command_center.py:387-410`

### 7. Generation rules and signal templates

Internal types/templates:

| Type | Title/reason | Why/next template | Evidence |
|---|---|---|---|
| CUSTOMER_INACTIVITY | No booking within inactivity window | Confirm account status and schedule customer outreach. | `backend/src/btx_omni/modules/alerts/commercial.py:55-56` |
| BOOKINGS_DECLINE | Bookings declined versus prior period | Review lost demand and recovery plan. | `backend/src/btx_omni/modules/alerts/commercial.py:57-61` |
| CRM_INACTIVITY | No CRM activity within follow-up window | Log an account touchpoint and assign an owner. | `backend/src/btx_omni/modules/alerts/commercial.py:62-63` |
| INTELLIGENCE_COMMERCIAL_CONTEXT | External intelligence needs commercial review | Review intelligence against current commercial plan. | `backend/src/btx_omni/modules/alerts/commercial.py:64-65` |
| STALE_QUOTE | Open high-value quote is stale | Escalate quote disposition with the account owner. | `backend/src/btx_omni/modules/alerts/commercial.py:70-73` |
| QUOTE_FOLLOW_UP | Open quote requires follow-up | Contact the quote recipient and record outcome. | `backend/src/btx_omni/modules/alerts/commercial.py:70-75` |
| CROSS_BU_COORDINATION | Multiple business units have active commercial context | Coordinate account strategy across business units. | `backend/src/btx_omni/modules/alerts/commercial.py:76-83` |
| OVERDUE_ORDER | Order is past its promised ship date | Confirm fulfillment status and customer recovery plan. | `backend/src/btx_omni/modules/alerts/commercial.py:84-86` |

Public vocabulary has 29 event types. The mapped title templates are CONTRACT_AWARD, CONTRACT_MODIFICATION, SOLICITATION, FACILITY_EXPANSION, CAPACITY_EXPANSION, NEW_FACILITY, REGULATORY_APPROVAL, REGULATORY_CHANGE, GOVERNMENT_FUNDING, PROGRAM_LAUNCH; every other type uses `Public update reported`. `backend/src/btx_omni/monitor/ontology.py:5-34`, `backend/src/btx_omni/monitor/briefs.py:38-49`, `backend/src/btx_omni/monitor/briefs.py:208-219`

The deterministic public why template is either “linked to a canonical Customer or Prospect in the watch universe” or “organization is not yet resolved ... no relationship is implied.” `backend/src/btx_omni/monitor/briefs.py:216-220`. Later persisted business analysis may replace headline/why with governed package values. `backend/src/btx_omni/monitor/business_briefings.py:584-589`, `backend/src/btx_omni/monitor/business_briefings.py:727-745`

## 3. Specific behaviors

### 8. All has no public items while public cards are highlighted

CONTRADICTS EXPECTATION on this branch. Current runtime has 31 `COMMERCIAL_REVIEW` items, zero public action priorities, and zero validation items; therefore the three top cards are internal because they are `priority.slice(0,3)`. `apps/web/src/features/today/Today.tsx:103-109`, `backend/src/btx_omni/modules/command_center.py:391-395`

Likely source of the perceived mismatch: curated `CURATED_PUBLIC` records are separately shown in the collapsed Public intelligence panel and are intentionally excluded from Today priority queues. `apps/web/src/features/today/Today.tsx:65-68`, `apps/web/src/features/today/Today.tsx:154`, `backend/src/btx_omni/modules/command_center.py:405-409`

Public priority admission requires resolved identity, seller-facing state, observed timing, `analysis_status=READY`, account scope, attributable evidence, and `priority_eligible`; validation instead requires `commercial_relevance_state=REVIEW_REQUIRED` and not eligible. No confidence-score threshold is used. `backend/src/btx_omni/modules/command_center.py:61-103`

### 9. Market buttons show 0

Counts are not priority counts. Each hub shows `current_signal_ids.length + upcoming_signal_ids.length`; the market field is `SignalBrief.markets`, and backend builds hub membership with `market in brief.markets`. `apps/web/src/features/today/Today.tsx:148`, `backend/src/btx_omni/modules/command_center.py:297-313`

Clicking a hub only filters current signals, Radar, watched accounts/programs, and coverage/gaps. It does not filter top cards or action priorities. `apps/web/src/features/today/Today.tsx:41-45`, `apps/web/src/features/today/Today.tsx:80-87`. Thus zero is expected when no eligible current/upcoming live brief exists even though internal priorities concern Defense/Aerospace accounts.

### 10. Watched Programs empty

There is no separate request. UI reads `command_center.watched_programs` from successful `/api/today`; runtime response status was 200 and body shape was an empty array. Client contract and UI both expect that array. `apps/web/src/api/client.ts:45`, `apps/web/src/types/api.ts:103`, `apps/web/src/features/today/Today.tsx:45`, `apps/web/src/features/today/Today.tsx:151`

Backend only creates watched programs from canonical program IDs on current/upcoming briefs, then drops IDs missing from the program map. `backend/src/btx_omni/modules/command_center.py:277-293`. Emptiness is an empty API projection, not a UI parsing error.

### 11. “Analysis incomplete”

Exact user copy is in `SignalBriefCard` whenever `analysis_status` exists and is not `READY`. `apps/web/src/components/SignalBriefCard.tsx:40`. Enum label mapping also maps `INCOMPLETE` to “Analysis incomplete.” `apps/web/src/components/presentation.ts:12`.

Base briefs default to `PENDING_ANALYSIS`; business briefing becomes `READY` only when public evidence exists, otherwise `INCOMPLETE`. `backend/src/btx_omni/monitor/briefs.py:94`, `backend/src/btx_omni/monitor/business_briefings.py:584-589`. The worker/repository can persist completed analysis, and Today priorities admit only `READY`. `backend/src/btx_omni/monitor/worker.py:457`, `backend/src/btx_omni/modules/command_center.py:84-103`.

### 12. Search

Search is local to the action-priority and validation arrays. It matches account name, reason, recommended action, and signal headline; it does not globally search accounts/programs/signals. `apps/web/src/features/today/Today.tsx:48-52`. It sits after source tabs and before customer/BU/order controls. `apps/web/src/features/today/Today.tsx:94-101`.

### 13. Sizing/styling and available primitives

- Search: flex basis 220px; input min-height 44px, 8px padding, 1px border, 5px radius; font inherits because none is specified. `apps/web/src/features/today/today.css:5-6`
- Business unit/worklist selects: width 100%, max-width 270px, min-height 44px, 8px padding, 5px radius. `apps/web/src/features/today/today.css:5`
- Source controls: native buttons, min-height 48px, padding 10px 8px, 3px active underline. `apps/web/src/features/today/today.css:7`
- Market hub controls use shared compact `Button`; horizontal scrolling and 7px gap. `apps/web/src/features/today/today.css:11`
- Search and the two selects do not use shared `SearchInput`/`SelectInput`; source control is custom buttons. Available shared primitives include `Button`, `TextInput`, `SearchInput`, `SelectInput`, `FilterChip`, fields/panels/status/table/drawer/disclosure. `apps/web/src/components/UI.tsx:29-44`, `apps/web/src/components/UI.tsx:68-69`

### 14. Greeting/header

Header always renders `Today` and `Your next commercial decisions`; there is no greeting or time-of-day logic in Today. `apps/web/src/features/today/Today.tsx:90-91`. Date labels use browser `Date` formatting forced to UTC, not local time. `apps/web/src/features/today/Today.tsx:21`.

### 15. Cards/list fields

Top card renders source label, attention, account name, headline/reason, what happened/reason, recommended action, and Review button. `apps/web/src/features/today/Today.tsx:104-109`.

List row renders rank, account, source/lifecycle label, related-recommendation count, observed date, headline/reason, why, next, evidence disclosure, and attention. Internal disclosure adds evidence IDs and recovery/customer/create-action buttons; public disclosure renders the full `SignalBriefCard`. `apps/web/src/features/today/Today.tsx:115-128`.

Unrendered at the row/top-card level: `outcome_lane`, raw `data_mode`, `watchlist_eligible`, `priority_reasons`, `business_unit_ids`, `event_id`, most nested brief fields. Public nested data does contain source URL/system, publication timestamp, why-it-may-matter, and no image field. `apps/web/src/types/api.ts:80-98`. `SignalBriefCard` renders source, date, URL and why inside its disclosure, but there is no card image. `apps/web/src/components/SignalBriefCard.tsx:32-40`, `apps/web/src/components/SignalBriefCard.tsx:64-68`.

### 16. Public source metadata/URLs

Schema and seed data contain `source_url`, `source_system`, publication date/timestamp; there is no image URL. `backend/src/btx_omni/monitor/briefs.py:70-75`, `apps/web/src/types/api.ts:80`. Seeded URLs are present and syntactically HTTPS, including a Commerce Department Intel URL; URL well-formedness is asserted without fetching. `backend/tests/test_api_acceptance.py:112-119`.

### 17. Dates/staleness as of 2026-09-20

Internal sample evaluation uses the fixed runtime observed clock and emits that timestamp on alerts. `backend/src/btx_omni/api/today.py:20-25`, `backend/src/btx_omni/modules/alerts/commercial.py:48`. Current runtime alert dates are 2026-08-31, so every displayed internal row is 20 days old as of the audit date. Quote/order overdue status is calculated relative to that sample clock, not 2026-09-20. `backend/src/btx_omni/modules/alerts/commercial.py:21`, `backend/src/btx_omni/modules/alerts/commercial.py:70-75`, `backend/src/btx_omni/modules/alerts/commercial.py:84-86`.

Public freshness uses real `datetime.now(UTC)`, and stale saved public items expire from Today after 60 days. `backend/src/btx_omni/api/today.py:39-41`, `backend/src/btx_omni/modules/command_center.py:13`, `backend/src/btx_omni/modules/command_center.py:140-150`.

### 18. Hide/done/snooze/acknowledge and IDs

Today priorities have no such UI/state, localStorage, table, or endpoint. Today recomputes filters only and backend returns read-only `user_saved_watch_items: ()`. `apps/web/src/features/today/Today.tsx:29-31`, `backend/src/btx_omni/modules/command_center.py:400-403`.

A separate Actions suggestion feedback system supports hidden reasons `WRONG_ACCOUNT`, `ALREADY_DONE`, `NOT_RELEVANT`, and active `SNOOZE`; it is user-scoped but is not connected to Today priorities. `backend/src/btx_omni/persistence/work_feedback.py:102-123`, `backend/src/btx_omni/api/actions.py:144-147`.

Internal priority ID is deterministic `alert-{kind}-{account}-{business_unit}` plus quote subject ID when present; cross-BU/order have deterministic specialized IDs. `backend/src/btx_omni/modules/alerts/commercial.py:38-39`, `backend/src/btx_omni/modules/alerts/commercial.py:83-86`. Public priority ID is stable `context_id` when present, else event ID. `backend/src/btx_omni/modules/command_center.py:25-30`. Stability therefore depends on stable source/context IDs, not page load.

### 19. Identity

Frontend has `Principal {user_id, display_name, role}` and hosted session state; development requests send a principal token from sessionStorage or default salesperson. `apps/web/src/types/api.ts:26-27`, `apps/web/src/api/client.ts:22-25`. Backend resolves development identities or hosted-session principals and exposes `user_id`. `backend/src/btx_omni/api/session.py:40-70`. There is therefore an identity suitable for user-scoped Today state, although Today currently does not consume it.

## 4. Quality baseline

### 20. Existing tests

- Backend command-center tests cover current/Radar/hubs, stable ordering, watch truth, degraded state, saved 60-day window/live clock, complete filtering beyond eight items, public/internal ordering, data modes, validation outcome, BU IDs, confidence and evidence. `backend/tests/test_command_center.py:100-167`, `backend/tests/test_command_center.py:169-217`, `backend/tests/test_command_center.py:220-289`, `backend/tests/test_command_center.py:292-369`
- Frontend contract tests assert Today copy, lanes, Market Hubs, unavailable/empty truth, Radar, read-only watchlist, pagination/cards, hub sources, curated separation, and no arbitrary signal slicing. `apps/web/tests/poc-ui.test.mjs:417-446`
- Decision tests assert Intelligence owns research while Today owns priority queues. `apps/web/tests/decision-experience.test.mjs:33-39`
- API acceptance verifies `/api/today` returns 200 and recommended actions. `backend/tests/test_api_acceptance.py:590-604`

### 21. Current checks

- Frontend `typecheck`: PASS; lint: PASS; tests: 82 passed. Commands are defined at `apps/web/package.json:7-12`.
- Backend Ruff: PASS. Focused Today/alerts/API set: 23 passed, 2 unrelated Omni acceptance failures at `backend/tests/test_api_acceptance.py:140` and `backend/tests/test_api_acceptance.py:552`.
- Full backend: 709 passed, 68 failed, 10 errors. Ten PostgreSQL cases cannot start because `BTX_DATABASE_URL` is absent, required at `backend/tests/test_monitor_research_journal.py:24`. Many failures are reviewed-input hash mismatches raised at `backend/src/btx_omni/persistence/import_commercial_sample.py:31` and `backend/src/btx_omni/providers/research/reference_data.py:40`. Baseline supplied by orchestrator: UNKNOWN, so no pass/fail delta can be calculated.

### 22. Screenshot

Desktop Today was run at `http://127.0.0.1:5173/#/today` and captured at `docs/audit/screenshots/TODAY_SCREEN_STATE_2026-09-20_desktop.png`. The route and rendered screen are backed by `apps/web/src/app/App.tsx:411-415` and `apps/web/src/features/today/Today.tsx:90-155`.

## 5. Summary

| # | Status | Evidence/result |
|---:|---|---|
| 1 | CONFIRMED | Route/tree identified; `apps/web/src/app/App.tsx:329`, `apps/web/src/app/App.tsx:411-415` |
| 2 | CONFIRMED | Full render order; `apps/web/src/features/today/Today.tsx:90-155` |
| 3 | CONFIRMED | Purpose from workflow/design/history; `docs/planning/WORKFLOW.md:169-179` |
| 4 | CONFIRMED | One Today request plus separate Intelligence records; `apps/web/src/api/client.ts:45` |
| 5 | CONFIRMED | Types/schema/examples documented; `apps/web/src/types/api.ts:80-103` |
| 6 | CONFIRMED | Mixed shared and separate projections; `backend/src/btx_omni/modules/command_center.py:387-410` |
| 7 | CONFIRMED | Eight internal rules, 29 public event types; `backend/src/btx_omni/modules/alerts/commercial.py:55-86`, `backend/src/btx_omni/monitor/ontology.py:5-34` |
| 8 | CONTRADICTS EXPECTATION | Current top cards are internal; curated public is separate; `apps/web/src/features/today/Today.tsx:65-68`, `apps/web/src/features/today/Today.tsx:103-109` |
| 9 | CONTRADICTS EXPECTATION | Market buttons are not worklist filters/counts; `apps/web/src/features/today/Today.tsx:148` |
| 10 | CONFIRMED | Empty API array, not UI error; `backend/src/btx_omni/modules/command_center.py:277-293` |
| 11 | CONFIRMED | Trigger and completion path found; `apps/web/src/components/SignalBriefCard.tsx:40` |
| 12 | CONFIRMED | Local lane search only; `apps/web/src/features/today/Today.tsx:50-52` |
| 13 | CONFIRMED | Exact CSS/component differences; `apps/web/src/features/today/today.css:5-7` |
| 14 | CONTRADICTS EXPECTATION | No greeting/time-of-day logic; `apps/web/src/features/today/Today.tsx:90-91` |
| 15 | CONFIRMED | Rendered/unrendered fields inventoried; `apps/web/src/features/today/Today.tsx:104-128` |
| 16 | CONFIRMED | Public URL/source/date exist, image does not; `backend/src/btx_omni/monitor/briefs.py:70-75` |
| 17 | CONFIRMED | Fixed commercial clock versus live public clock; `backend/src/btx_omni/api/today.py:20-40` |
| 18 | CONFIRMED | No Today state; separate Actions feedback exists; `backend/src/btx_omni/persistence/work_feedback.py:102-123` |
| 19 | CONFIRMED | User/session identity exists; `backend/src/btx_omni/api/session.py:40-70` |
| 20 | CONFIRMED | Frontend/backend coverage inventoried; `backend/tests/test_command_center.py:100-369` |
| 21 | UNKNOWN | Checks recorded, but comparison baseline was not supplied; `apps/web/package.json:7-12` |
| 22 | CONFIRMED | Desktop screenshot saved; screen source `apps/web/src/features/today/Today.tsx:90-155` |

### Surprises not explicitly asked

- The normal Today body is completely replaced by a recovery briefing when the URL selects a commercial recovery item. `apps/web/src/features/today/Today.tsx:37`, `apps/web/src/features/today/Today.tsx:88-89`.
- Selecting a market does not enter the URL-backed Today filters, so market selection is lost on reload/deep link while kind/account/BU/query/sort/pages persist. `apps/web/src/features/today/Today.tsx:30`, `apps/web/src/features/today/Today.tsx:72`, `apps/web/src/features/today/Today.tsx:86`.
- `priority_briefing` deliberately orders all commercial reviews before all public action briefs, regardless of public recency. `backend/src/btx_omni/modules/command_center.py:191-220`, `backend/src/btx_omni/modules/command_center.py:393-395`.
- The displayed rank uses the unsorted filtered array index even after the user selects a non-ranked sort, so visual rank can diverge from row order. `apps/web/src/features/today/Today.tsx:53-59`, `apps/web/src/features/today/Today.tsx:115-120`.

### Files most likely to change

| Goal | Likely files |
|---|---|
| (a) Unify priority data | `backend/src/btx_omni/modules/command_center.py`, `backend/src/btx_omni/api/today.py`, `apps/web/src/types/api.ts`, `apps/web/src/features/today/Today.tsx`, command-center/UI tests |
| (b) Add hide/done state | Today API/module plus a new persistence/API boundary; existing patterns in `backend/src/btx_omni/persistence/work_feedback.py`, `backend/src/btx_omni/api/actions.py`, session principal code, Today UI/types/tests |
| (c) Restyle controls | `apps/web/src/features/today/today.css`, `apps/web/src/features/today/Today.tsx`, `apps/web/src/components/UI.tsx`, `apps/web/src/components/ui.css`, design tokens |
| (d) Redesign cards | `apps/web/src/features/today/Today.tsx`, `apps/web/src/features/today/today.css`, `apps/web/src/components/SignalBriefCard.tsx`, signal-card CSS, API types/tests |
| (e) Add top-level tabs with Market Hubs | `apps/web/src/features/today/Today.tsx`, `today.css`, `apps/web/src/app/navigation.ts`, `apps/web/src/app/App.tsx`, command-center projection/types/tests |
