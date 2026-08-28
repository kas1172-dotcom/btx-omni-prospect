# BTX Omni Prospect — POC Capability Manifest

> POC data contract: researched real entities are the complete current account set; no generated market population or rank target exists.
> universe describe a future production feed, not the current POC. The current
> POC has only researched public companies and verified public locations.

## Product boundary

Phase 1 has five top-level surfaces: **Today**, **Accounts**, **Intelligence**, **Map**, and **Actions**. **Omni** is the persistent governed assistant across every surface. Opportunities and Operations remain backend capabilities and contextual views, not Phase 1 tabs.

The POC supports two truthful modes. **SAMPLE** uses the governed synthetic environment described in the scenario matrix. **CONNECTED** uses authorized source adapters and exposes missing or unavailable data explicitly. Omni is grounded in this governed context and is never a source of record.

| Capability | Surface | Backend owner/module | Data source | SAMPLE support | CONNECTED dependency | POC | Acceptance criteria | Jamie validation required |
|---|---|---|---|---|---|---|---|---|
| Commercial briefing and alerts | Today | Alert and commercial-context service | PRISM, Paperless, CRM, public monitor | Yes | Authorized source adapters | Required | Ranked explainable cards show evidence, state, owner context, and a safe next action. | Alert thresholds and production data availability |
| Canonical account profile | Accounts | Identity/account read model | Canonical identity plus all governed sources | Yes, researched public-company universe with curated scenarios | Identity resolution, PRISM, Paperless, CRM | Required | One canonical account ID, relationship state, evidence, missingness, and cross-BU context. | Account hierarchy and BU grain |
| Account Attractiveness | Accounts, Map, Today, Omni | Backend scoring service | Governed commercial context and evidence | Yes | Authorized commercial facts | Required | Deterministic, evidence-linked score with configuration/version, coverage, and missing-data state. | Production score inputs and rubric approval |
| External market rank | Map, Accounts, Omni | Optional ranked-source feed | Approved external methodology | No | Approved ranked-source feed | Deferred | If introduced, rank is visibly separate from Account Attractiveness and never treated as internal commercial history. | Approved source/methodology |
| PRISM commercial context | Accounts, Today, Alerts, Omni | PRISM commercial-context adapter | PRISM | Shaped sample history | PRISM read access | Required | Governed TTM revenue and bookings/orders support BU, segment, end market, platform/program, part number, monthly history, and last booking/order when available. Detail/monthly fields are marked SAMPLE assumptions until confirmed. | Actual grain, monthly availability, program/part/end-market fields, last booking/order availability |
| Paperless quote context | Accounts, Intelligence, Alerts, Omni | Paperless quote adapter | Paperless Parts | Shaped accounts and quotes | Paperless read access | Required | Accounts may be prospects without quotes; rolling feed includes recent/open/won/lost quotes, outstanding value, quote-to-book correlation, and account/contact/facility linkage. | Prospect-account behavior and actual fields/statuses |
| Quote safety boundary | Accounts, Intelligence, Omni | Classification/provenance service | Paperless Parts | Yes | Classification controls | Required | Only safe commercial fields render. Drawings, CAD, restricted technical content, and CUI never enter the POC context. | Field classification policy |
| CRM commercial context | Accounts, Actions, Omni | CRM adapter | HubSpot | Yes | HubSpot read-only demo adapter | Required | Company owner, deals, contacts, activity, last meaningful contact, and cross-BU coordination are visible with provenance. | Activity reliability and ownership conventions |
| Contact research | Accounts, Map, Omni | Contact-research service | CRM and approved public research | Role-family targets and provenanced candidates | Authorized public/CRM research | Required | Procurement, supply chain, supplier management, engineering, manufacturing, and operations roles are available; no fabricated named people. | Permitted sources and review workflow |
| Public intelligence | Intelligence, Today, Accounts, Omni | Monitor and signal-normalization service | Approved public sources | Yes | Approved collectors | Required | Awards/contracts, press, financial reports, and industry updates include source URL, timestamp, vertical, classification, and confirmed/inferred state. | Final approved source list |
| Program/component/capability matching | Intelligence, Accounts, Omni | Deterministic matching engine | Public evidence plus Paperless/PRISM history | Yes | Governed matching inputs | Required | Evidence chain distinguishes confirmed external evidence from inference; deterministic matching runs before any semantic method. | Production source coverage |
| Commercial alerts | Today, Accounts, Actions, Omni | Alert service | PRISM, Paperless, CRM, monitor | Yes | Source freshness and order data | Required | Inactivity, bookings decline, stale quote, follow-up gap, CRM inactivity, ownership conflict, and intelligence-commercial alerts are explainable and actionable. Overdue orders are architecturally supported but depend on order-level PRISM data. | Order dates/statuses and alert thresholds |
| National commercial graph | Map | Market/facility read model | Researched canonical accounts, public facilities, BTX facilities | Yes | Facility and market feeds | Required | Renders only loaded researched locations; canonical industries are Defense, Commercial Aerospace, Space, Robotics, Semiconductor, Medical, and Energy. Proximity informs seller planning only. | Additional verified facility data |
| Actions and governance | Actions, all contextual surfaces, Omni | Work/action service | Governed action proposals | Yes | CRM write boundary later | Required | Review, assign, approve, dismiss, follow up, CRM preview, human confirmation, and audit trail are supported. No autonomous writes. | Approval roles and CRM write policy |
| Omni assistant | Persistent across all surfaces | Assistant orchestration and context service | Governed read models and approved research | Yes | Authenticated context and permitted research | Required | “Ask Omni” explains scores, alerts, signals, matches, history, and next actions; optional reactive public research is provenance-labelled. | Research policy and UX language |
| Opportunities | Account context, Omni | Opportunity service | CRM and commercial matching | Yes | CRM/opportunity source | Backend only | Account-linked opportunities are available to Today, Actions, and Omni without a top-level tab. | Opportunity model/grain |
| Operations | Account context, Omni | Operations/capability service | Facilities and governed operating facts | Deferred | Authorized operating data | Deferred | No Phase 1 tab; only contextual capability/facility information needed for commercial explanation. | Scope and data ownership |

## Sample-data rules

1. The **POC account set** contains only sufficiently researched real entities. Every loaded record has canonical identity and available researched facts; coordinates, rank, and internal commercial classification remain absent when not supported by their governing sources.
2. The **deep scenario layer** contains exactly 17 enriched canonical accounts with shaped PRISM, Paperless, CRM, facilities, intelligence, matching, scoring, alerts, actions, provenance, and missingness.
3. Sample facts carry explicit source, classification, mode, and confirmed/inferred state. No sample record implies a real BTX relationship unless labelled as governed synthetic POC data.
4. All uncertain production fields are labelled `SAMPLE assumption — Jamie validation required`.

## Open Assumptions Requiring BTX Confirmation

- What is PRISM's actual account, BU, customer-segment, and transaction grain?
- Are monthly revenue and bookings/orders available, and for what historical period?
- Which part number, platform/program, and end-market fields are reliable enough to govern?
- Are last booking date and last order date available at account/BU level?
- Are order-level dates and statuses sufficient for overdue-order alerts?
- Can Paperless Accounts exist as prospects without quotes, and how are they identified?
- Which Paperless quote fields and statuses does BTX actually use for open/won/lost/follow-up reporting?
- How reliable and complete are HubSpot activities and “last meaningful contact” data?
- What is the final Phase 1 industry list, and should Energy be deferred?
- What approved source and methodology, if any, should supply an external rank later?
