# Seller-surface contract map

This POC exposes researched public facts alongside clearly simulated BTX
commercial context. The browser formats and filters these DTOs; it does not
calculate commercial decision logic.

| Surface | Backend endpoint | Seller-facing fields | Canonical source | Truth boundary |
| --- | --- | --- | --- | --- |
| Today | `GET /api/today` | public intelligence, commercial alerts, recommended actions | Monitor projection and `CommercialAlertEngine` | Public signals are source-backed; alerts/actions are SAMPLE commercial context |
| Accounts | `GET /api/accounts` | identity, markets, relationship, attractiveness, commercial state | canonical account + scoring inputs + commercial context | Identity/markets are researched; score/context are simulated BTX inputs |
| Account Detail | `GET /api/accounts/{id}` | Account 360, score factors/gaps, quotes, orders, CRM, alerts, intelligence | canonical account, public facilities, commercial adapters, scoring and alerts | Explicit public/BTX truth categories are returned |
| Intelligence | `GET /api/intelligence` | event, source URL/date, account/program/facility resolution, relevance | Monitor observation/event projection | Public-source evidence; unresolved entities stay unresolved |
| Map | `GET /api/map` | canonical account/facility/BTX/intelligence geometry | researched locations and safely resolved monitor facilities | No generated geography; proximity is seller planning only |
| Actions | `GET/POST /api/actions` | evidence-backed, idempotent local work items and audit | governed work service | Session-only SAMPLE workflow; no autonomous CRM writes |
| Omni | `POST /api/omni` | bounded answer, citations, missingness, recommended action, `context_used` | canonical Account 360/scoring/alerts/intelligence reads | Read-only; public facts remain sourced and commercial facts remain SAMPLE |

## Omni context

`context` is typed and optional: `surface` (`TODAY`, `ACCOUNTS`,
`ACCOUNT_DETAIL`, `INTELLIGENCE`, `MAP`, `ACTIONS`), selected event/facility/
program/action/account IDs, bounded filters, visible IDs, and prior turns.
Top-level `account_id` is explicit request scope; `selected_account_id` is
current UI selection; `session_account_id` is conversational continuity.
Lowercase legacy surfaces and the previous context shape remain accepted.
Responses may include `context_used` for passive context that actually
influenced the answer; it never contains conversation transcripts.

On Map, account-point selection supplies the canonical `selected_account_id`.
Research-facility selection supplies `selected_facility_id` and its canonical
parent account only when the facility record has one. BTX facility selection
supplies only its canonical facility ID. Map selections clear on navigation.
Actions sends the currently selected governed work-item `id` as
`selected_action_id`; it clears on navigation. Omni does not yet interpret
that action context semantically.

When an Intelligence event is selected and the question is event-focused,
Omni resolves the canonical event through the Monitor/Intelligence projection.
It returns source-backed event evidence, exact account/program/facility
resolution only where present, and `context_used.event_id`. An unresolved
event remains unresolved: Omni does not fuzzy-match an account or infer event
geography. Any commercial alert, score, or workflow context is identified as
the current SAMPLE commercial dataset.

When a Map facility is selected and the question is facility-focused, Omni
resolves its exact canonical ID through the researched-facility or BTX-facility
read model. Researched facilities identify a parent account only when that
canonical association exists; BTX facilities never imply a prospect/customer
account. Facility answers cite stored provenance, do not infer ownership or
relationships from proximity, and label any parent-account commercial context
as the current SAMPLE commercial dataset. Unknown facility IDs and missing
canonical associations remain explicit limitations.

When an Actions work item is selected and the question is action-focused,
Omni resolves the exact canonical `WorkItem.id` through the current governed
work-service read. It explains the stored summary, status, priority, account,
and evidence IDs, and links public Intelligence only through exact shared
evidence IDs. Current work items do not store a canonical originating alert or
rule ID, so Omni reports that limitation rather than recreating decision logic.
Actions are session-only SAMPLE workflow state; Omni remains read-only and
cannot bypass the separate human-confirmation gate for CRM execution. Unknown
or stale action IDs remain explicit limitations.

Relationship-oriented Omni questions use `RelationshipIntelligenceService` for
the existing bounded canonical paths; Omni does not traverse or infer graph
edges itself. It preserves the service's `validated`, `needs_validation`, and
unusable presentation states. Source-less explicit edges remain
`needs_validation`, and no-path answers mean only that the current graph has
no evidence-backed path. Relationship answers keep researched/public edges,
SAMPLE CRM/commercial hops, and BTX context distinct; market similarity and
geographic proximity are never treated as a relationship or warm introduction.
Omni can suggest validation, but is read-only and cannot create tasks, contacts,
CRM records, or relationship edges.

Explicit page-summary questions (for example, `What matters most on this
page?`) use the typed current surface, its active filters, and its bounded
canonical visible IDs. Today, Accounts, Intelligence, and Actions summarize
only supplied visible records; Account Detail summarizes its selected account;
Map summarizes only its selected account or facility and otherwise reports
that no focused canonical map record is available. This deterministic route
does not read the DOM, screenshots, or the unbounded backend universe. More
specific event, facility, action, relationship, cross-account, and general
questions retain their respective routes. Public records remain source-backed;
commercial alerts, scores, and workflow state are labelled as the current
SAMPLE commercial dataset where material.

Omni also supports a bounded deterministic cross-account family: ranking by
the existing Account Attractiveness output; accounts with open governed work;
accounts with canonical Intelligence; their set intersection; open quote or
quote-history presence; exact canonical two-account comparisons; and exact
canonical market filters. Results are capped at five and use stable canonical
ordering. Omni does not add a prioritization score, fuzzy-match entities,
recalculate Monitor relevance, or infer relationships/geography. Cross-account
commercial and workflow facts remain the current SAMPLE dataset; Intelligence
continues to use source-backed canonical events.

## Omni conversational continuation

Omni uses a bounded typed `conversation_referent` rather than treating prior
assistant prose or the display-only `prior_turns` transcript as semantic
authority. It carries only canonical account, event, facility, action, ordered
two-account comparison, or relationship endpoint IDs plus a route label. The
precedence policy is explicit: current-turn named entities and global/screen
queries first; then current relevant UI selection; then a valid canonical
conversational referent; then current surface/filter context; then safe
fallback. A newer selection of the same type supersedes an older referent.
Cleared UI selection may still permit a narrow explicit follow-up, but never
overrides a new screen summary or global query. Missing canonical IDs and
ambiguous “other one” references fail safely. The browser retains this bounded
state for its session and sends it with the next request; the backend remains
stateless, revalidates IDs against canonical reads, performs no prose parsing,
and remains read-only.

| Surface | Current selection | Active filters | Bounded visible IDs |
| --- | --- | --- | --- |
| Today | none | none | rendered alert and intelligence IDs, in display order |
| Accounts | Account Detail only | `account_scope` and canonical `market` when active | filtered/searched account IDs |
| Account Detail | canonical account | none | not supplied |
| Intelligence | canonical event | none currently exposed | rendered canonical event IDs |
| Map | canonical account/facility | none currently exposed | not supplied |
| Actions | canonical work item | priority, canonical `market`, and `action_status` when active | filtered work-item IDs |

Visible IDs are canonical and deterministically limited to the first 50
records represented by the current surface. Route changes clear passive entity,
filter, and list context; browser-session conversation history remains separate.

## Decisioning rules

`Account Attractiveness v1` is a deterministic, intrinsic 0–100 structural
index. It is not rank, urgency, or probability. The backend returns coverage,
factor contributions, and missingness. Current seller priority comes from a
separate combination of governed Monitor intelligence and deterministic
commercial alerts. Public relationship paths may explain a recommended action,
but do not add score points unless represented in the approved scoring input.

`data_mode` identifies the record/provider provenance, not the enclosing POC
environment: public connected/curated facts may therefore coexist with
`synthetic=false` in the SAMPLE commercial environment; simulated internal
commercial records are marked SAMPLE/synthetic.
