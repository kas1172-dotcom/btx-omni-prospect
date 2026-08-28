# Seller-facing POC operation

The default directory and map focus are the curated researched public-company
universe. Company identity, industry, and public geography carry source URLs
from `docs/research`. They do not establish a BTX customer, CRM, quote, deal,
or commercial relationship. Any BTX commercial, owner, CRM, scoring, quote,
and workflow context in SAMPLE mode is synthetic/demo context.

## Map configuration

The application uses MapLibre with MapTiler and does not change map providers.
Set these frontend environment variables:

```text
VITE_MAP_STYLE_URL=https://api.maptiler.com/maps/streets-v2/style.json
VITE_MAP_API_KEY=your_browser_key
```

The key must be restricted in MapTiler to the deployed frontend domain(s), with
`localhost` added only for local development. Do not commit a key. If either
setting is absent, or the tile request fails, the product shows **Map
unavailable** with this setup guidance; filters and non-map location panels
remain usable.

## Truthful POC boundaries

- Development authentication is labelled as development-only.
- Actions and audit events are held only in API process memory and reset on a
  restart; they are not durable PostgreSQL workflow records yet.
- Omni retains browser-session conversation history. Its fallback is bounded
  deterministic retrieval, not fabricated model output, and is read-only.
- Monitor does not collect from the public UI. A protected manual operational
  run requires durable state, an operator token, and `BTX_MONITOR_MODE=live`.
  “LIVE PUBLIC” is reserved for successful collection output. There is no
  automatic scheduler in this POC.

## Monitor demo script

1. Open **Monitor** and point out the primary **INACTIVE** status: no scheduler,
   configured live source, credentials, durable run history, or collection output
   exists in this POC.
2. Open **Curated POC signal preview**. Explain: “These are stored, sourced
   public scenarios used to demonstrate Monitor output. They are not live
   ingestion.”
3. Open a source or **Account 360** from any preview item to show the evidence
   trail and the separation from simulated BTX context.
4. Close by explaining that production monitoring requires an approved source
   registry, required collection credentials, durable run history, entity
   resolution, and alert policy before any event may be labeled **LIVE PUBLIC**.

## Actions demo flow

1. Open **Actions** and start with the priority inbox. Explain that the suggested
   decisions use simulated BTX commercial context, while any linked event is
   curated public evidence.
2. Add one decision to the queue, then use priority, industry, status, or company
   search to focus the workbench.
3. Select the queued action to show why it is recommended, the public evidence
   where available, and the compact session-only workflow boundary.
4. Use a workflow transition to demonstrate the queue state, then open **Preview
   demo CRM action**. Explain that preview creates no production record and that
   execution requires a separate explicit confirmation.
5. Close by noting that owner, due date, durable audit history, and production
   CRM execution remain unavailable until approved BTX/CRM inputs are connected.

## Omni demo flow

1. Open **Ask Omni** with no Account 360 record selected. Ask **What should I
   review today?** Omni returns deterministic guidance from the curated company
   universe and sourced public events, plus clearly marked simulated workflow
   context.
2. Ask a follow-up or choose **Compare these researched companies.** The
   conversation remains visible only for the current browser session; it is not
   a saved transcript or source of record.
3. Open an Account 360 record, then ask **Explain this score and its gaps.**
   Point out the selected-account ribbon, cited public evidence links, and the
   distinct missing/simulated-context notices.
4. Close by explaining: **Deterministic fallback—not model-generated advice.**
   Omni uses local governed POC read models only, cannot perform CRM writes, and
   would require approved connected data, access controls, retrieval governance,
   model-provider approval, and durable conversation policy before production use.

## Phase 7 seller-scenario acceptance matrix

The curated SAMPLE environment is exercised through the real browser path with
these intentionally bounded scenario anchors. Public company and Intelligence
facts remain source-backed; score, quote, CRM, workflow, and internal
relationship context remain SAMPLE.

| Seller scenario | Canonical anchor | Expected seller path / truth boundary |
| --- | --- | --- |
| Southwest trip planning | Anduril Industries, Rocket Lab USA, General Atomics | Sourced Southern California facilities support a bounded geographic itinerary; proximity remains descriptive, not ownership or a relationship. |
| Medical Device whitespace | Medtronic | Account 360 shows limited simulated score coverage and missing fit context; it does not convert the SEC filing into a sales signal. |
| Defense award + quote history | Lockheed Martin | Account, Intelligence, and quote-related Omni reads retain public-event versus SAMPLE-commercial separation. |
| Semiconductor expansion | Intel | Curated public CHIPS signal is shown with its source-validation limitation. |
| Dormant customer reactivation | Applied Materials | A deliberately stale SAMPLE booking date drives deterministic customer-inactivity review; it is never presented as production BTX activity. |
| Quote follow-up | GE Aerospace | An open, follow-up-aged SAMPLE quote drives the canonical quote-follow-up alert. |
| Cross-BU conflict / overlap | Boeing | Existing canonical alert/workflow context is visible without changing the rule or creating work through Omni. |
| Strong external signal + weak internal history | Intel | The public CHIPS expansion signal is retained, while the SAMPLE environment intentionally has no commercial context for Intel. |
| Strong internal history + weak external signal | Lam Research | Meaningful SAMPLE commercial history is present, but no curated public Intelligence scenario is attached. |
| Missing, unresolved, or conflicting evidence | Symbotic / Intel | Symbotic's scoring exclusion and Intel's automation-blocked official source remain explicit; controlled conflicts stay in deterministic test coverage. |

## Future Monitor worker contract

Monitor collection remains disabled in the seller UI. Before a manual operator
run or future scheduler is authorized, apply the database migrations and configure these names
only: `BTX_MONITOR_DURABLE_STATE_ENABLED`, `BTX_MONITOR_OPERATOR_TOKEN`, and
`BTX_MONITOR_MODE=live`, plus only the approved source-specific configuration.
The operator calls `POST /api/monitor/internal/collect` with the
`X-BTX-Monitor-Operator-Token` header to collect every registered source through
the single canonical runner. `POST /api/monitor/internal/collect/{source_id}`
is available for a controlled one-source retry. Both routes fail closed when the
token or durable-state configuration is absent; `/api/monitor/collect/{source_id}`
stays blocked for seller-facing use. A future scheduler need only invoke the
same all-source endpoint with these configuration values; no scheduler is
enabled by this repository.

Each durable event stores the source publication date separately from the BTX
collection timestamp and latest update timestamp. Only an event produced by a
successful collection run is `LIVE_PUBLIC`; curated POC events remain a separate
`CURATED_PUBLIC` preview. Sources with no successful run are `UNAVAILABLE`; a
source whose last success exceeds its registry cadence (with
`BTX_MONITOR_STALE_AFTER_HOURS`, 48 by default, as the upper bound) is `STALE`,
never silently current. Recovery is: stop the scheduler,
inspect the durable run failure and source health, correct approved source
configuration, run one authenticated worker collection, then verify the saved
run counts, source health, and timestamps before resuming the schedule.

### NASA local validation

For the one-source local NASA Official News RSS validation only, confirm the
four Monitor environment variable names above are configured locally and run
`uv run alembic upgrade head`. Start the local backend, call the protected
NASA internal collection route once with the configured operator-token header,
then inspect `/api/monitor/health`. Verify its NASA run counts, source health,
last successful check, publication/collection/update timestamps, source URL,
and unresolved or rejected results. Do not treat unresolved NASA observations
as seller Intelligence; only resolved, evidence-backed current events are
eligible for the live seller projection.

### Future USAspending source policy

USAspending is prepared but is not enabled or collected in this POC task. Each
run is bounded to curated researched companies in the supported primary markets
(Commercial Aerospace, Defense, Semiconductor, Space, Robotics, Energy, and Medical).
The eligible set is variable and is derived from loaded research. Queries use a researched
company's legal display name and any separately documented, authoritative
USAspending recipient name; no UEI, CAGE, recipient ID, parent, subsidiary, or
alias is invented. There are currently no USAspending-specific identifiers in
the research inputs because none has been independently recorded with an
authoritative source.

Only current prime-award observations (USAspending award codes `A`–`D`) within
90 days can become seller-visible. They require an exact governed recipient
match, a direct official evidence URL, an action date, a positive award amount,
description, collection timestamp, and no identity conflict. Exact but
incomplete or 91–180-day observations are retained as `RESOLVED_NEEDS_REVIEW`;
aliases, parents, and subsidiaries are `AMBIGUOUS`; unmatched recipients are
`UNRESOLVED`; non-material/unsupported or over-180-day awards are `REJECTED`.
All five outcomes are durable, but only `RESOLVED_ELIGIBLE` is projected as
`LIVE_PUBLIC` seller intelligence. A collected award is public federal evidence,
never evidence of a BTX relationship or opportunity.

USAspending expects a daily successful check. No success is `UNAVAILABLE`; a
missed expected cadence is `STALE`; an API or parsing failure is `FAILED` and
does not make old awards current. Before one authenticated local collection,
apply migrations through `0007_usaspending_relevance_state`, confirm the same
three Monitor variables named in the worker contract plus `BTX_MONITOR_MODE=live`,
review the approved target list and USAspending request fields, then make one
protected worker call. Inspect durable run counts, source health, action and
collection timestamps, resolution/relevance outcome, and seller projection
before scheduling any recurring run.

The collector uses only documented USAspending API contracts: `POST
/api/v2/search/spending_by_award/` supplies the filtered award identifier,
recipient name, award amount, description, and award type; then `POST
/api/v2/transactions/` with that award's `generated_internal_id` supplies the
latest `action_date`, action description, and transaction context. The stable
evidence locator is the documented `GET /api/v2/awards/<AWARD_ID>/` API URL,
constructed only from the generated internal award ID. A row is durably
`REJECTED` before relevance evaluation when it lacks a generated award ID,
recipient name, action date, direct official evidence URL, or positive award
amount. This is a source-contract rejection, not a claim about a BTX
relationship.

Recipient resolution accepts a name only after case, punctuation, and whitespace
normalization; it never removes or adds legal-name tokens. The 11 exact
recipient mappings and their public provenance are recorded in
`docs/research/btx_usaspending_recipient_identities.json`. The mappings are
legal-identity evidence only: they do not assert a customer, prospect, parent,
or BTX commercial relationship.

#### USAspending local-run outcome — 2026-08-17

One authorized local USAspending run completed successfully at
`2026-08-17T12:13:22.009379Z`. It evaluated seven returned observations: zero
were `RESOLVED_ELIGIBLE`, `RESOLVED_NEEDS_REVIEW`, ambiguous, or rejected; all
seven were `UNRESOLVED`, so zero became seller-visible. The response shape
included the requested field names, but these returned rows had no usable source
action date or direct official award-detail URL, and no recipient exactly matched
the approved canonical target roster. The run is therefore retained as healthy,
durable operational evidence only; it is not an Intelligence recommendation.
The next controlled run must validate this corrected two-stage contract against
the live response before any scheduling decision. It must produce a generated
award ID, transaction action date, direct official award-detail URL, positive
amount, and exact mapped recipient before an observation may be seller-visible.
