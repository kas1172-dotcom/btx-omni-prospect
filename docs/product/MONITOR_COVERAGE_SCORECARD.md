# Monitor coverage scorecard

Checkpoint 15 is a calibration baseline, not a claim of complete live coverage.
All internal commercial context remains governed `SAMPLE`; public evidence below
is public-source only and cannot imply a real BTX relationship.

The canonical account set is the variable-size researched public-company set.
It contains no synthetic placeholder identities. Any zero source or benchmark
count below reflects a deliberately bounded, evidence-first monitor policy.

| Phase 1 industry | Relevant event classes | Configured source path | Working controlled source | Blocked / unavailable | Verified watch profiles | Verified benchmark events | Recent-event result | Known gap |
|---|---|---|---|---|---:|---:|---|---|
| Aerospace | awards, launches, backlog, facilities | SAM, USAspending, NASA, SEC, official company | SAM, USAspending, NASA | SEC fair-access identity; company URL | 0 | 0 | candidate only, unresolved | Reviewed event-to-account mapping required |
| Defense | awards, solicitations, modifications | SAM, USAspending, Federal Register, DoD, SEC | SAM, USAspending, Federal Register | DoD machine-readable feed; SEC | 0 | 0 | candidate only, unresolved | Verified BTX watch profile required |
| Space Exploration | awards, launches, funding, partnerships | NASA, SAM, USAspending, SEC | NASA, SAM, USAspending | SEC/company URL | 0 | 0 | candidate only, unresolved | No verified commercial entity match |
| Semiconductor | grants, capacity, facilities, capex | SEC, Commerce, company, state | none entity-qualified | SEC fair access; Commerce feed; company/state URLs | 0 | 0 | no qualified candidate | Approved public-company profile required |
| Medical | regulatory, launch, facilities | openFDA, Federal Register, SEC, company | openFDA, Federal Register | SEC/company URL | 0 | 0 | candidate only, unresolved | Regulatory record is not commercial launch proof |
| Energy | capacity, funding, facilities | SEC, company, state | none | SEC fair access; company/state URLs | 0 | 0 | `NO_RECENT_EVENT` | Reviewed source mapping required |

## Benchmark calibration baseline

The approved benchmark schema permits `subject_account_id` to be null, but it
still requires a verified source, entity, event type, date, and review notes.
No benchmark rows have been added because the controlled SEC request was
rejected under fair-access policy and no reviewed event-labeling pass has been
completed. Assigning event types to generic filing metadata would be
fabrication.

| Metric | Baseline | Interpretation |
|---|---:|---|
| Verified benchmark corpus | 0 | Blocked pending reviewed public issuer/watch-profile set and source records |
| Source recall | N/A | No frozen benchmark denominator |
| Event-type accuracy | N/A | No verified labelled events |
| Entity-resolution accuracy | N/A | No verified mapped subjects |
| Duplication rate | 0 fixture duplicates | Deterministic duplicate/version tests pass; no live corroboration pair yet |
| Unresolved rate | 100% of controlled live candidates | Correct false-positive avoidance behavior |
| Ambiguity rate | 0% of controlled live candidates | Ambiguous fixture remains covered |
| False-positive rate | 0% observed | No live account link was created |

## Required next evidence

1. A BTX-reviewed mapping from real public issuers to canonical account IDs (or
   an explicit external-subject benchmark policy).
2. SEC-compliant declared user-agent identity and verified CIK evidence.
3. Approved official company/IR and state economic-development URLs.
4. A reviewed event-labeling pass before freezing the first 60-event benchmark.
