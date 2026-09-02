# Phase 21 — Figma / Application Reconciliation

The Figma target file is a visual and interaction reference only. Runtime projections remain authoritative for identity, ranking, evidence, freshness, providers, permissions, and data mode. Illustrative Figma counts, percentages, dates, scores, probabilities, and connected-provider examples are intentionally not reproduced.

| Surface | Application equivalent | Reconciliation | Intentional boundary |
| --- | --- | --- | --- |
| Shell / navigation | `app/App.tsx`, shared design tokens | Match: persistent desktop rail, mobile navigation, current-route treatment, Settings, and Omni access | Every accepted surface remains reachable; no duplicate navigation was added |
| Today | `features/today/Today.tsx` | Match: primary priorities precede Market Hubs; evidence panels and Radar use compact hierarchy | No static KPI or urgency examples |
| Customers & Prospects | `features/accounts/Accounts.tsx` | Match: searchable/filterable responsive directory and canonical selection | Seller text uses Customer/Prospect; internal `account` symbols remain |
| Customer 360 | `features/accounts/Accounts.tsx` | Partial by design: progressive sections organize identity, commercial context, evidence, facilities, relationships, and Actions | Missingness and SAMPLE/CONNECTED state are never hidden for visual density |
| External Intelligence | `features/intelligence/Intelligence.tsx` | Match: feed, priority treatment, evidence, Radar, source health, and procurement navigation | No ticker percentages or inferred commercial claims |
| Federal Procurement | Intelligence procurement views | Match: filters, density, detail, evidence, relevance, and responsive sheets | No probability-to-win or unavailable historic deltas |
| Relationship Intelligence | Customer relationship projections | Match: readable paths, evidence, validation state, alternatives, and mobile disclosure | No graph, fake strength, or changed path classification |
| Tactical Map | `features/map` | Match: compact controls and selected detail around the governed map canvas | No inferred geography or HQ fallback |
| Actions | `features/actions/Actions.tsx` | Match: compact workbench, filters, drawer, detail/history, and touch layout | No external CRM/export implication; lifecycle remains governed |
| Omni | `components/OmniDrawer.tsx` | Match: floating entry, quick/full progressive disclosure, context chips, evidence panel | Read-only; no assistant-created Action or entity guessing |
| Settings | `features/settings/Settings.tsx` | Match: personal, role/access, integration/provider sections and mobile-safe panels | Role/provider configuration is backend managed; no secrets |

## Validation approach

Screens are covered by the responsive release matrix at 320px, 390px, and 430px, plus desktop shared-shell, Actions, Omni, Customer, Intelligence, Federal Procurement, Relationship, Map, Settings/Communications, seller-scenario, and primitive coverage. The screenshots produced by those Playwright journeys are the visual regression review artifact; they exercise the actual governed runtime rather than Figma placeholder data.

## Intentional Figma divergences

- Runtime provider and data-mode truth overrides illustrative connected states.
- Unsupported monitor controls, CRM writes, exports, scoring, relationship graphs, and opportunity probabilities are not rendered as functional controls.
- The application preserves required public/SAMPLE, missingness, validation, and source disclosures even where Figma examples are visually simpler.
