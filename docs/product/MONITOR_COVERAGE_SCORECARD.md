# Monitor coverage scorecard

Phase 3 is a calibration baseline, not a claim of complete live coverage.
All internal commercial context remains governed `SAMPLE`; public evidence below
is public-source only and cannot imply a real BTX relationship.

The canonical account set is the variable-size researched public-company set.
It contains no synthetic placeholder identities. Any zero source or benchmark
count below reflects a deliberately bounded, evidence-first monitor policy.

| Primary market | Relevant event classes | Configured source path | Live-run result (2026-08-19) | Blocked / unavailable | Frozen evaluation examples | Recent-event result | Known gap |
|---|---|---|---|---|---:|---:|---|---|
| Commercial Aerospace | awards, launches, backlog, facilities | SAM, USAspending, NASA, SEC, official company | USAspending exact-recipient Boeing award | SAM key; SEC CIK; company feeds | 1 | PASS: resolved recent award | Program text absent from award payload |
| Defense | awards, solicitations, modifications | SAM, USAspending, Federal Register, DoD, SEC | USAspending exact-recipient Anduril award | SAM key; DoD feed; SEC CIK | 1 | PASS: resolved recent award | Program text absent from award payload |
| Space | awards, launches, funding, partnerships | NASA, SAM, USAspending, SEC | USAspending exact-recipient Blue Origin award | SAM key; SEC CIK; company feeds | 1 | PASS: resolved recent award | Program text absent from award payload |
| Semiconductor | grants, capacity, facilities, capex | SEC, Commerce, company, state | no credible source result | SEC CIK; Commerce/company/state feeds | 0 | FAIL | Configure an authoritative structured or publisher source |
| Medical | regulatory, launch, facilities | openFDA, Federal Register, SEC, company | openFDA exact-name Intuitive Surgical 510(k) result | SEC CIK; company feeds | 1 | PASS: resolved regulatory event | Regulatory clearance is not commercial launch proof |
| Energy | capacity, funding, facilities | SEC, company, state, USAspending | USAspending public award retained unresolved | SEC CIK; company/state feeds | 1 | PARTIAL: no seller-visible account | Exact recipient identity evidence required |

## Benchmark calibration baseline

The frozen examples in
[`docs/research/monitor_evaluation_examples.json`](../research/monitor_evaluation_examples.json)
record source IDs/URLs, dates, expected canonical resolution, event type, market,
and relevance state. They are regression-review inputs, not a live API test
corpus. The Semiconductor gap intentionally remains an absence rather than a
fabricated benchmark record.

| Metric | Baseline | Interpretation |
|---|---:|---|
| Frozen evaluation examples | 5 | Public-source examples with explicit expected resolution/relevance |
| Source recall | N/A | Small calibration set, not a representative recall denominator |
| Event-type accuracy | N/A | No verified labelled events |
| Entity-resolution accuracy | Calibration only | Exact-recipient and exact-name examples are frozen for review |
| Duplication rate | 0 fixture duplicates | Deterministic duplicate/version tests pass; no live corroboration pair yet |
| Unresolved rate | retained when exact identity is absent | Correct false-positive avoidance behavior |
| Ambiguity rate | 0% of controlled live candidates | Ambiguous fixture remains covered |
| False-positive rate | 0% observed in reviewed examples | No fuzzy or topic-only account link was created |

## Required next evidence

1. A BTX-reviewed mapping from real public issuers to canonical account IDs (or
   an explicit external-subject benchmark policy).
2. SEC-compliant declared user-agent identity and verified CIK evidence.
3. Approved official company/IR and state economic-development URLs.
4. A reviewed event-labeling pass before freezing the first 60-event benchmark.
