# POC SAMPLE acceptance matrix

This matrix records the governed SAMPLE evidence used by the current POC. It
does not assert that SAMPLE fields are confirmed BTX production fields.
`CONNECTED` has no fallback to these records.

| Requirement | SAMPLE proof | Backend source | API / frontend surface | Result | Open dependency |
|---|---|---|---|---|---|
| Phase 1 market universe | 600 canonical records; exactly 100 each for Commercial Aerospace, Defense, Space, Semiconductor, Medical Device, and Robotics | `providers/sample/environment.py` | `GET /api/accounts`, `GET /api/map`; Accounts, Map | Pass | Top-100 source/methodology confirmation |
| Identity, state, location, research | Every account has canonical ID, legal name, domain, relationship (current/former/target), US city/state/country facility, coordinates, provenance, all six Contact Research role families, and `ELIGIBLE` public-research state | `environment.py`, `domain/accounts.py` | Accounts, Map | Pass | Live identity/research permissions |
| Rank versus score | `ExternalIndustryRank.methodology_note` explicitly excludes Account Attractiveness; scoring uses separate inputs | `domain/scores.py`, `modules/scoring/` | Accounts, Map, Omni | Pass | Approved production rank methodology and score rubric |
| 17 enriched accounts | 17 canonical deep IDs carry commercial, Paperless Account, CRM-shaped, public-signal, scoring, and provenance records; cross-BU account has two commercial contexts | `environment.py` | Account 360, Today, Intelligence, Map, Actions, Omni | Pass | Production source coverage |
| PRISM-shaped history | TTM revenue/bookings, BU, customer segment, end market, geography through canonical facility, monthly revenue/bookings, and last booking/order where applicable | `domain/commercial.py`, `environment.py` | Account 360, Today, Omni | Pass, synthetic | Monthly/detail fields are explicitly `POC synthetic assumption / pending PRISM confirmation` |
| PRISM program and part | Defense scenario supplies `Defense Platform` and `DP-100` | `environment.py` | Account 360, Intelligence, Omni | Pass, synthetic | PRISM field/grain confirmation |
| Paperless Account distinct from quote | Every deep account has a `PaperlessAccount`; `acct-06-002` has no quote history | `domain/quotes.py`, `environment.py` | Account 360 Commercial & Paperless panel | Pass | Real Paperless account/prospect mapping |
| Paperless quote lifecycle | New open: `acct-01-002`; high-value stale: `acct-01-004`; won: `acct-01-001`; lost: `acct-02-002`; multiple: `acct-02-001`; cross-BU: `acct-01-005` | `environment.py` | Account 360, Today, Actions, Omni | Pass | Quote status/field mapping |
| Quote correlation | `acct-02-001` open/won quotes link to `award-defense-1`; high-value strong-history: Defense; high-value weak-history: `acct-03-001` | `environment.py`, `modules/matching/` | Intelligence, Account 360, Omni | Pass | Paperless/PRISM production linkage |
| Quote safety boundary | Only safe commercial fields are modeled: ID, account, BU, status, quote date, value/currency, contact/facility ID, part family, provenance/evidence | `domain/quotes.py` | Account 360 | Pass | Quote number/revision, due/expiry, digital-view, RFQ, estimator, quantities, export-control flag require approved Paperless mapping; drawings/CAD/RFQ files/specs/restricted notes are excluded |
| CRM context and Contact Research | Each deep account has synthetic CRM-style company/owner/contact-role/deal/activity IDs and provenance; `acct-01-005` is cross-BU | `SampleCrmContext`, `integrations/hubspot/` | Account 360, Actions, Omni | Pass, synthetic | Named contacts, activity types/stages, and live HubSpot associations require approved mapping |
| Human-confirmed actions | SAMPLE actions retain idempotency/audit; CRM execution requires explicit confirmation | `modules/work/`, `api/actions.py` | Actions, Omni | Pass | Live CRM write policy/approval roles |
| Geography | Every account facility has valid coordinates; map returns industry layer, relationship, nearest BTX facility and planning-only proximity | `environment.py`, `api/map.py` | Map | Pass | Production facilities and source geography |
| Commercial alerts | Deterministic inactivity, bookings decline, stale quote, quote follow-up, CRM inactivity, cross-BU, and intelligence-commercial alerts | `modules/alerts/commercial.py` | Today, Account 360, Actions, Omni | Pass | Threshold and source-freshness approval |
| Overdue order | Contract is present; `overdue_order_available()` is false in SAMPLE | `modules/alerts/commercial.py` | Account 360, Omni | Pass/unavailable | Reliable order promised-date/status fields |
| Matching | Defense exact and structured matches; conflict no-match; missing insufficient-data; confirmed/inferred states retained | `modules/matching/`, `environment.py` | Intelligence, Account 360, Omni | Pass | Live approved matching inputs; no BOM is fabricated |
| Truth and provenance | Synthetic internal facts, stored public signals, deterministic derivations, inferred/confirmed/conflicting/missing states, URLs and provenance are explicit | `core/provenance.py`, `modules/intelligence/` | All surfaces and Omni | Pass | Live collector credentials and source policy |
| A. Southwest seller trip | `acct-01-001` plus nearby Semiconductor/Space/Robotics targets; owner/activity, role families and governed action path | `scenario_accounts["southwest-trip"]` | Map, Accounts, Actions, Omni | Pass | Live distance/facility data |
| B. Medical whitespace | `acct-05-001` current customer and `acct-05-002` target within Medical Device Top-100 | `scenario_accounts["medical-whitespace"]` | Map, Accounts, Intelligence, Omni | Pass | Production commercial presence |
| C. Defense award correlation | `acct-02-001`: confirmed award, high-value open quote, PRISM history, exact/structured match | `scenario_accounts["defense-award-quote"]` | Intelligence, Accounts, Today, Actions, Omni | Pass | Live source and Paperless access |
| D. Semiconductor expansion | `acct-04-002`: confirmed expansion, CRM inactivity, commercial context, geographic planning | `scenario_accounts["semiconductor-expansion"]` | Intelligence, Map, Accounts, Omni | Pass | Live source/facility context |
| E–J risk/truth scenarios | Dormant `01-003`; quote follow-up `01-004`; cross-BU `01-005`; external/weak internal `01-006`; internal/weak external `01-007`; conflict/missing `01-008` | `scenario_accounts` and `intelligence_events` | Today, Accounts, Intelligence, Actions, Omni | Pass | Production source validation |

## Truth labels

SAMPLE provenance uses `data_mode=SAMPLE` and `synthetic=true`. Public monitor
records retain URL/evidence-state contracts but are stored SAMPLE evidence; live
public source collection is separately provenance-labelled. Deterministic score,
match, and alert outputs never convert missing or inferred input into confirmed
BTX production fact. Omni is grounded in this context, is not a source of
record, and cannot autonomously write CRM data.
