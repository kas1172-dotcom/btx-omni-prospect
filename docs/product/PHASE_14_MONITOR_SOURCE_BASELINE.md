# Phase 14 Monitor source baseline

Captured 2026-09-01 through `python -m btx_omni.monitor.live_validation`.
This is a bounded manual operator validation, not a schedule.

| Source | Implementation | Credentials | Config/runnable state | Manual result |
| --- | --- | --- | --- | --- |
| SAM.gov | `monitor/sources.py:SamAdapter` | API key | `BTX_SAM_API_KEY` absent; NAICS list is empty and `PENDING_VERIFICATION` | `WARNING`, not requested |
| USAspending | `UsaSpendingAdapter` | No | Account-targeted from verified recipient mappings | `HEALTHY`: 3 fetched/observed/events, 3 resolved, 0 seller eligible |
| Federal Register | `FederalRegisterAdapter` | No | Enabled keyless API | `HEALTHY`: 3 fetched/observed/events, 3 ambiguous, 0 seller eligible |
| SEC EDGAR | `SecEdgarAdapter` | Identifying User-Agent | Verified CIK targets are loaded from the governed research profiles; `BTX_SEC_USER_AGENT` is absent | `WARNING`, not requested |
| NASA | `NasaAdapter` | No | Enabled keyless official RSS | `HEALTHY`: 3 fetched/observed/events, 2 resolved, 1 unresolved, 2 seller eligible |
| openFDA | `FdaAdapter` | No | Enabled keyless API | `HEALTHY`: 3 fetched/observed/events, 3 ambiguous, 0 seller eligible |
| DoD contracts | `DodAdapter` | No | Not implemented as a verified machine-readable feed | `NOT_CONFIGURED`; collection disabled |
| Commerce CHIPS | `CommerceAdapter` | No | Not implemented as a verified machine-readable feed | `NOT_CONFIGURED`; collection disabled |
| Company newsroom | `CompanyNewsAdapter` | No | Needs per-target verified feed URL | `NOT_CONFIGURED`; collection disabled |
| State economic development | `StateEconomicAdapter` | No | Needs verified state publisher feed URL | `NOT_CONFIGURED`; collection disabled |

The monitor does not currently implement Air Force, Navy, Army, BIS, DDTC,
Congress.gov, or a defense-trade RSS collector. No scraped substitute is used.

## SAM.gov configuration

`BTX_MONITOR_SAM_NAICS` is the sole named list and is only appended to the
official query when `BTX_MONITOR_SAM_NAICS_VERIFICATION_STATE=VERIFIED`.
The shipped list is empty with `PENDING_VERIFICATION`; no NAICS is inferred.
The required activation input is an approved BTX NAICS list plus the SAM API key.

## SEC EDGAR configuration

SEC uses `data.sec.gov/submissions/CIK##########.json` for governed targets,
retains only recent 10-K and 10-Q metadata, uses accession numbers as stable
source IDs, preserves an official archive URL as evidence, and requests at no
more than four target submissions per second. Source-version hashes provide
the existing durable idempotency behavior; no separate cache is introduced.

Set `BTX_SEC_USER_AGENT` to a real organization/contact value to activate it.
SEC metadata does not generate future filing or earnings dates.

## Deferred

Alpha Vantage and other ticker-market data are not a current Monitor dependency
and remain deferred. Scheduler configuration remains manual trigger only with
`BTX_MONITOR_SCHEDULE_CONFIGURED=false`.
