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
