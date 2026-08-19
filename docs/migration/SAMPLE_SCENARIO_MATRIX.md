# BTX Omni Prospect — Sample Scenario Matrix

## Sample environment structure

The POC sample environment has two layers.

| Layer | Scope | Required record shape |
|---|---|---|
| Researched account set | Variable-size, real researched companies; supported overlaps allowed | Identity, industry, available coordinates, domain, public research eligibility, and basic commercial classification |
| Deep scenario accounts | Exactly 17 canonical enriched accounts | PRISM-shaped history, Paperless Accounts/quotes, CRM companies/contacts/deals/activities, facilities, signals, deterministic matches, scores, alerts, actions, provenance, and missingness |

Every lightweight and deep account has coordinates. Proximity supports seller planning only; it must not influence Account Attractiveness or qualification. Public-research candidates use role families or provenanced records—never fabricated named people.

## Primary acceptance scenarios

| Scenario | Persona | Account(s) | Source systems | Required sample fields | Expected deterministic outcome | UI surfaces | Omni questions | Migration dependencies |
|---|---|---|---|---|---|---|---|---|
| A. Southwest Seller Trip Planning | Southwest seller | One current Southwest customer; three Tier 1 Semiconductor/Space targets within ~30 miles | Market universe, facilities, CRM, contact research | Coordinates, nearest facility, owner/deals/activity, role targets, customer/target state, shared BU relationships | Map preserves all locations; proximity ranks planning context only; cross-BU warning is visible; governed Action can be created in context. | Map, Accounts, Actions, Omni | “Which nearby targets should I coordinate around this customer visit?” | Canonical identity, facility distance, CRM read model, action proposal |
| B. Medical Market Penetration Review | Commercial leader | Medical current customers and prospects | Researched accounts, PRISM, CRM, facilities | Geography, invoiced/commercial presence, BU relationships, customer/target state | Map distinguishes present customers from whitespace; any future external rank remains separate from internal attractiveness. | Map, Accounts, Intelligence, Omni | “Where do we have Medical whitespace with existing commercial presence?” | PRISM commercial facts, identity |
| C. Defense Award + Quote Correlation | Account manager | Prime/Tier 1 with major award and open quote | Public monitor, Paperless, PRISM, matching, CRM | Award URL/time, program, component/capability evidence, open quote value/age/status, TTM history, account linkage | Ranked Intelligence card explains deterministic evidence chain; no inferred BOM; stale/open quote alert and Action are available. | Intelligence, Accounts, Today, Actions, Omni | “Why is this award relevant to our open quote?” | Monitor normalization, deterministic matching, Paperless adapter, PRISM adapter |
| D. Semiconductor Expansion + Geographic Opportunity | Regional sales lead | Semiconductor target and nearby priority customer | Public monitor, market universe, facilities, CRM | Expansion source, target rank/coordinates, nearby customer, facility distance, owner/activity | Expansion is an explainable signal; map shows geographic context and recommends a regional human follow-up without creating a score from distance. | Intelligence, Map, Accounts, Actions, Omni | “What is the safest regional follow-up for this expansion?” | Public-source monitoring, distance calculation, CRM context |
| E. Dormant Current Customer | Account owner | Historical high-value current customer | PRISM, CRM, alerts | TTM revenue/bookings history, last booking/order if available, last meaningful contact, owner, missingness | Customer-inactivity alert explains its evidence; Omni distinguishes confirmed history from missing order/contact data; Action can be assigned. | Today, Accounts, Actions, Omni | “Why is this customer marked dormant?” | PRISM history, CRM activity, alert policy |
| F. Quote Follow-Up Risk | Quote owner | Strong historical customer with stale high-value open quote | Paperless, PRISM, CRM, alerts | Quote age/value/status, quote-contact linkage, account history, owner/shared ownership | Stale-quote/follow-up alert is deterministic and evidence-linked; owner coordination is visible before a human-confirmed follow-up. | Today, Accounts, Actions, Omni | “What evidence supports following up on this quote?” | Paperless statuses, PRISM correlation, CRM ownership |
| G. Cross-BU Conflict | Sales manager | Shared account touched by multiple BUs | CRM, PRISM, Paperless, identity | BU identifiers, owners, contacts, deals/quotes, activities, coordination state | One canonical account shows cross-BU activity and coordination warning; no duplicate entity is created. | Accounts, Map, Actions, Omni | “Who else is working this account and what needs coordination?” | Canonical identity, BU relationship model, CRM read model |
| H. Strong External / Weak Internal | Business development | Researched target with little/no BTX history | Researched accounts, public research, CRM/PRISM absence | Coordinates, role families, explicit absent internal history | Target remains visible as a market opportunity; any external rank never becomes Account Attractiveness; no internal relationship is invented. | Map, Accounts, Omni | “What do we know versus what remains unverified?” | Missingness model, contact research |
| I. Strong Internal / Weak External | Account manager | Meaningful customer with lower market rank | PRISM, Paperless, CRM, market universe | TTM revenue/bookings, quote history, owner/activity, lower external rank | Account is surfaced through commercial context and alerts despite lower external rank; concepts remain separate. | Today, Accounts, Omni | “Why does this account matter despite its lower external rank?” | PRISM/Paperless/CRM adapters, score truth |
| J. Missing / Conflicting Evidence | Analyst | Account with contradictory/incomplete signals | Public monitor, Paperless, PRISM, CRM, matching | Conflicting source claims, missing quote/history fields, classification, inference state | No false positive match or ordinary approved score; UI shows missingness and confirmed-versus-inferred evidence; Action is review-only. | Intelligence, Accounts, Actions, Omni | “What prevents us from making a stronger claim?” | Provenance/classification, deterministic matching, score coverage |

## Deep-account coverage plan

The 17 enriched accounts must be allocated so every scenario has at least one primary account and the Southwest scenario has one current customer plus three nearby targets. Accounts may participate in multiple scenarios only where provenance and state stay consistent. The remaining deep accounts provide quote-status, BU, facility, contact-role, and missingness variation needed to exercise all alerts and matching states.

## Migration dependencies

1. Canonical identity and account-to-source linkage.
2. Source adapters for PRISM commercial context, Paperless quote context, CRM read context, and approved public monitoring.
3. Classification/provenance and confirmed-versus-inferred evidence model.
4. Deterministic matching and canonical Account Attractiveness persistence/read path.
5. Market-universe/facility geometry and governed action proposal/audit model.
6. Omni context assembly over the same canonical IDs and evidence packages.

## Open Assumptions Requiring BTX Confirmation

- What is the actual PRISM grain and which fields are governed at account versus BU level?
- Are monthly revenue/bookings available, and can they be supplied for the POC horizon?
- Which part, program/platform, and end-market fields are reliable?
- Are last booking/order dates available, and are order-level dates/statuses reliable enough for overdue alerts?
- Do Paperless Accounts include prospects without quotes, and what quote fields/statuses are actually used?
- How complete and reliable is HubSpot activity history and last meaningful contact?
- What final Phase 1 industries are approved; does Energy belong in a later phase?
- What approved source and methodology should define any future external rank?
