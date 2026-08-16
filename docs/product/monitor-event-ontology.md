# Monitor Phase 1 event ontology

The stable event classes are: `CONTRACT_AWARD`, `SOLICITATION`, `CONTRACT_MODIFICATION`; `FACILITY_EXPANSION`, `CAPACITY_EXPANSION`, `NEW_FACILITY`; `PROGRAM_LAUNCH`, `PRODUCTION_RAMP`, `PRODUCT_LAUNCH`; `SUPPLIER_AWARD`, `SUPPLY_CHAIN_CHANGE`; `CAPITAL_INVESTMENT`, `M_AND_A`, `PARTNERSHIP`; `REGULATORY_APPROVAL`, `REGULATORY_CHANGE`; `GOVERNMENT_FUNDING`, `GRANT_AWARD`; `EXECUTIVE_CHANGE`, `EARNINGS_SIGNAL`, `BACKLOG_CHANGE`.

| Industry | Primary relevant event classes |
| --- | --- |
| Commercial Aerospace | contract award/modification, supplier award, facility/capacity expansion, program/production ramp, partnership, earnings/backlog |
| Defense | contract award, solicitation, modification, supplier/supply-chain change, government funding, program/production ramp, facility/capacity expansion |
| Space | award/solicitation, program launch, production ramp, partnership, funding/grant, facility expansion |
| Semiconductor | capacity/new facility, capital investment, government funding/grant, supply-chain change, M&A, earnings/backlog |
| Medical Device | regulatory approval/change, product launch, facility/capacity expansion, M&A/partnership, supply-chain change, earnings |
| Robotics | product/program launch, supplier award, partnership, capital investment/M&A, facility expansion, earnings/backlog |

An event class describes an externally supported occurrence, not commercial value. A contract modification remains a modification even if its amount is large; a cancelled solicitation is not an active solicitation event.
