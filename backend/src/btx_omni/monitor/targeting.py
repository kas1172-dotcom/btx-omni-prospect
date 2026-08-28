"""Governed, deterministic Monitor watch-universe policy."""

from __future__ import annotations

from dataclasses import dataclass

from btx_omni.domain.accounts import AccountFacility, CanonicalAccount
from btx_omni.monitor.resolution import AccountWatchProfile
from btx_omni.monitor.sources import SourceDefinition


@dataclass(frozen=True)
class TargetReason:
    code: str
    detail: str
    source_system: str
    source_record_id: str | None = None


@dataclass(frozen=True)
class WatchTarget:
    canonical_account_id: str
    legal_name: str
    markets: tuple[str, ...]
    reasons: tuple[TargetReason, ...]
    profile: AccountWatchProfile


class StrategicWatchUniverse:
    """Select source targets without deriving commercial or relationship truth."""

    def __init__(
        self,
        *,
        accounts: tuple[CanonicalAccount, ...],
        profiles: tuple[AccountWatchProfile, ...],
        facilities: tuple[AccountFacility, ...] = (),
        scenario_account_ids: frozenset[str] = frozenset(),
    ) -> None:
        self._accounts = {item.id: item for item in accounts}
        self._profiles = {item.canonical_account_id: item for item in profiles}
        self._facility_accounts = frozenset(item.account_id for item in facilities)
        self._scenario_ids = scenario_account_ids

    def targets_for(
        self, source: SourceDefinition, *, cap: int
    ) -> tuple[WatchTarget, ...]:
        candidates: list[WatchTarget] = []
        source_markets = frozenset(source.industries_supported)
        for account_id, account in self._accounts.items():
            profile = self._profiles.get(account_id)
            markets = tuple(
                market for market in account.industries if market in source_markets
            )
            if profile is None or not markets:
                continue
            reasons: list[TargetReason] = []
            if account.btx_top_100 and account.btx_top_100_provenance:
                provenance = account.btx_top_100_provenance
                reasons.append(
                    TargetReason(
                        "BTX_TOP_100_REFERENCE",
                        "Membership in the governed sanitized POC watch list.",
                        "SANITIZED_REFERENCE",
                        provenance.source_ids[0]
                        if provenance.source_ids
                        else account_id,
                    )
                )
            if account_id in self._scenario_ids:
                reasons.append(
                    TargetReason(
                        "EXISTING_GOVERNED_WATCH_PROFILE",
                        "Existing governed seller scenario/watch profile.",
                        "SAMPLE_SCENARIO",
                        account_id,
                    )
                )
            if account_id in self._facility_accounts:
                reasons.append(
                    TargetReason(
                        "VERIFIED_REFERENCE_LOCATION",
                        "A governed public or sanitized-reference location is available.",
                        "CANONICAL_FACILITY",
                        account_id,
                    )
                )
            if profile.source_native_identifiers:
                reasons.append(
                    TargetReason(
                        "SOURCE_NATIVE_IDENTIFIER",
                        "A governed source-native organization identifier is available.",
                        "CANONICAL_IDENTITY",
                        account_id,
                    )
                )
            if not reasons:
                continue
            candidates.append(
                WatchTarget(
                    account_id, account.legal_name, markets, tuple(reasons), profile
                )
            )

        def ordering(item: WatchTarget) -> tuple[int, int, str, str]:
            codes = {reason.code for reason in item.reasons}
            return (
                0 if "EXISTING_GOVERNED_WATCH_PROFILE" in codes else 1,
                0 if "BTX_TOP_100_REFERENCE" in codes else 1,
                item.legal_name.casefold(),
                item.canonical_account_id,
            )

        return tuple(sorted(candidates, key=ordering)[: max(0, cap)])
