# SAMPLE Data Contract

SAMPLE is a deterministic, demo-only environment. It is not a migration
rehearsal, CRM approval queue, or claim that BTX has a relationship with any
named organization.

## Required demo journeys

The SAMPLE experience must support the J1–J9 journeys in
`docs/migration/SAMPLE_SCENARIO_MATRIX.md`: regional prospecting, cross-BU
planning, medical coverage, researched lead review, expansion, external-risk
exercise, recovery, relationship discovery, and relationship comparison.

Each journey must preserve explicit SAMPLE/synthetic labels and distinguish
researched public context from simulated BTX context.

## Minimum reachable environment

These are floors for the permanently enhanced runtime, not ceilings. The
load-bearing test parses this table and compares it with the loaded SAMPLE
environment.

| Entity collection | Minimum count |
|---|---:|
| accounts | 323 |
| facilities | 441 |
| public_facilities | 49 |
| btx_facilities | 6 |
| watch_profiles | 309 |
| commercial_ledgers | 15 |
| programs | 47 |
| component_classes | 47 |
| researched_accounts | 34 |

## Truth and provenance

Synthetic records use `data_mode=SAMPLE` and `synthetic=true`. Public or
researched records retain their source identity and source URL; public
identity is not evidence of a BTX relationship. Inferred or hypothetical
relationships remain labeled as hypotheses or fictional scenarios. Unknown
values remain unknown and are never completed by inference.

No screen may present synthetic commercial values, fictional locations,
inferred relationships, simulated risk events, or researched public identity
as a verified BTX fact. Public evidence must not be fabricated, and SAMPLE
must not alter CONNECTED behavior or safety boundaries.

## Validation

The contract is enforced by `backend/tests/test_sample_data_contract.py`.
If the required-count test fails, merge is blocked.
