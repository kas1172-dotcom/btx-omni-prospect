# Monitor controlled live validation

Validated locally on 2026-08-16 with `BTX_MONITOR_MODE=live`,
`BTX_AI_PROVIDER=anthropic`, a configured Anthropic model, and a configured
SAM credential. Secret values were not recorded. Each live request was capped
to one record; no raw payload was written to this repository.

## Source validation matrix

| Source | Tier | Auth | Industry coverage | Live result | Normalization / resolution | Health result | AI used | Limitation |
|---|---|---|---|---|---|---|---|---|
| SAM.gov | T1 authoritative structured | READY | Defense, Space, Commercial Aerospace | 1 record after a 14-day bounded query | Native notice ID, timestamp, URL, hash/evidence retained; deterministic candidate, `UNRESOLVED` | Healthy after bounded query; an earlier unbounded query returned HTTP 400 | No | Source subject did not exactly match a watch profile |
| USAspending | T1 authoritative structured | KEYLESS_READY | Defense, Space, Commercial Aerospace, Semiconductor | 1 record | `Award ID` retained as native ID; deterministic candidate, `UNRESOLVED` | Healthy | No | Returned award was not a canonical-account match |
| Federal Register | T1 authoritative structured | KEYLESS_READY | Defense, Space, Medical Device, Semiconductor | 1 record | Document number, publication time, URL, hash/evidence retained; deterministic candidate, `UNRESOLVED` | Healthy | No | No relevant resolved Phase 1 account in this narrow pull |
| SEC EDGAR | T1 authoritative structured | CONFIG_ERROR | All six | Not requested | N/A | Warning: verified CIK/watch profile required | No | No verified CIK in the controlled configuration |
| NASA official news | T2 authoritative publisher | KEYLESS_READY | Space, Commercial Aerospace | 1 RSS item | Canonical article URL and RFC publication time retained; deterministic candidate, `UNRESOLVED` | Healthy | No | Item was not a resolved commercial account event |
| DoD official contracts | T2 authoritative publisher | KEYLESS_READY | Defense, Space, Commercial Aerospace | 0 | N/A | Failed: HTTP 403 | No | Publisher access/routing blocked this controlled request |
| Department of Commerce | T2 authoritative publisher | KEYLESS_READY | Semiconductor | 0 | N/A | Failed: HTTP 403 | No | Publisher access/routing blocked this controlled request |
| FDA/openFDA | T1 authoritative structured | KEYLESS_READY | Medical Device | 1 record | `k_number` retained as native ID; deterministic candidate, `UNRESOLVED` | Healthy | No | Regulatory record did not resolve to a watch profile |
| Official company newsroom | T2 authoritative publisher | CONFIG_ERROR | All six | Not requested | N/A | Warning: verified newsroom URL required | No | No approved watch-profile newsroom URL |
| State economic development | T2 authoritative publisher | CONFIG_ERROR | Semiconductor, Robotics, Medical Device, Commercial Aerospace | Not requested | N/A | Warning: verified state publisher URL required | No | No approved state publisher URL |

## Structured-first and AI boundary

SAM.gov, USAspending, Federal Register, openFDA, and SEC adapters use
deterministic parsing before normalization. No Claude request was made for those
structured source observations. Native IDs, source tiers, content hashes,
retrieval times, canonical references, and raw evidence references are retained
by `SourceObservation`.

The provider-neutral registry selected the Anthropic adapter and consumed the
configured key only within that adapter. A minimal public-title request was
made through `extract_structured_event`; the configured model returned HTTP 404.
This is an explicit AI-provider configuration/model availability failure, not a
source failure and not canonical truth. No BTX SAMPLE commercial data was sent.

## Industry and downstream outcome

The controlled pull produced real candidates from sources covering Commercial
Aerospace, Defense, Space, Semiconductor, and Medical Device. None carried an
exact approved watch-profile identity, so every live candidate remained
`UNRESOLVED`; no false canonical account link, commercial match, score change,
or autonomous action was created. Robotics has no live candidate in this window:
its approved state/company source URLs are not configured. This is recorded as
`NO_RECENT_EVENT` / configuration unavailable rather than fabricated coverage.

The canonical boundary is intact: a live `SourceObservation` deterministically
becomes an `IntelligenceEvent` candidate, then requires governed entity/program
resolution before entering commercial matching. Existing fixture coverage proves
exact, alias, source-ID, ambiguous, and unresolved resolution states; no live
record met that threshold in this controlled run.

## Clustering, health, and rejection handling

Collection now keys clusters by the deterministic semantic cluster key and
tracks source record hashes by `(source, native ID)`, so repeat records are
matched and content changes increment `records_changed`. The controlled window
did not contain a verified multi-source corroboration pair; no synthetic pair
was introduced. The existing monitor tests cover duplicate suppression and
version-change detection.

`GET /api/monitor/sources` exposes registry metadata. `GET /api/monitor/health`
exposes source health, recent runs (including counts, failures, latency), event
clusters, and rejected observations. Source-health warnings remain separate from
Commercial Alerts. Controlled negative fixtures cover malformed responses,
empty results, unavailable auth, rate limits, conflict/missing match inputs, and
the rejection-state vocabulary; live claims were never fabricated to force a
rejection outcome.

## SAMPLE + LIVE posture

BTX commercial context remains `data_mode=SAMPLE` and `synthetic=true`. Live
public observations normalize as `data_mode=CONNECTED` public provenance and
never masquerade as BTX internal facts. Until a live event resolves through an
approved watch profile, it cannot be correlated to SAMPLE PRISM/Paperless/CRM
context. This preserves the intended cross-system boundary without silently
falling back to SAMPLE or allowing Monitor to calculate Account Attractiveness.
