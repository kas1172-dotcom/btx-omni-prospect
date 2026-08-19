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
