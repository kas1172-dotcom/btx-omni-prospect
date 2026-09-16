"""Deterministic seller Command Center composed from existing governed reads."""

from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
from typing import Any

from btx_omni.domain.markets import PRIMARY_MARKET_ORDER
from btx_omni.monitor.briefs import SignalBrief

_SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
SAVED_INTELLIGENCE_WINDOW_DAYS = 60
_VALIDATION_RELEVANCE_STATES = {
    "REVIEW_REQUIRED",
    "ESTABLISHED_ACCOUNT_REVIEW",
    "ESTABLISHED_COMMERCIAL_RELEVANCE",
    "PLAUSIBLE_FIT_REQUIRES_VALIDATION",
}


def _brief_dict(brief: SignalBrief) -> dict[str, Any]:
    return asdict(brief)


def _public_item(brief: SignalBrief, *, outcome_lane: str) -> dict[str, Any]:
    """Project one governed assessment without rebuilding its explanation."""
    return {
        "id": brief.context_id or brief.id,
        "event_id": brief.id,
        "kind": "PUBLIC_SIGNAL",
        "outcome_lane": outcome_lane,
        "account_id": brief.canonical_account_ids[0]
        if brief.canonical_account_ids
        else None,
        "reason": brief.why_it_may_matter,
        "recommended_action": brief.recommended_action,
        "evidence_ids": brief.evidence_ids,
        "observed_at": brief.publication_timestamp,
        "data_mode": brief.data_mode,
        "watchlist_eligible": brief.watchlist_eligible,
        "priority_reasons": tuple(asdict(reason) for reason in brief.priority_reasons),
        "signal_brief": _brief_dict(brief),
        "business_unit_ids": tuple(
            sorted(
                {
                    unit["id"]
                    for match in (brief.technical_opportunity or {}).get("matches", ())
                    if match.get("status")
                    in {"MATCHED", "POSSIBLE_MATCH_REVIEW_REQUIRED"}
                    for unit in match.get("business_units", ())
                    if unit.get("id")
                }
            )
        ),
        "lifecycle_state": "CURRENT"
        if brief.freshness == "CURRENT"
        else "SAVED_RECENT",
    }


def build_command_center(
    *,
    accounts: tuple,
    programs: tuple,
    alerts: tuple,
    monitor_snapshot: dict,
    curated_signals: list[dict],
    generated_at,
    public_as_of=None,
) -> dict[str, Any]:
    """Compose seller sections without deriving new facts or priority policy.

    Commercial alerts retain their governed severity order. Current public briefs
    follow alerts, with strategic-watch matches first, then publication timestamp
    descending and stable brief ID. Radar is ordered by its source-supported future
    timestamp and stable ID. Market hubs follow the canonical taxonomy order.
    """
    # Commercial SAMPLE records use the explicit demo clock. Public intelligence
    # retains real publication dates and is evaluated against the real read time.
    public_clock = public_as_of or generated_at
    account_by_id = {item.id: item for item in accounts}
    program_by_id = {item.id: item for item in programs}
    briefs: tuple[SignalBrief, ...] = tuple(monitor_snapshot.get("signal_briefs", ()))
    current = tuple(
        brief
        for brief in briefs
        if brief.resolution_state == "RESOLVED"
        and brief.seller_promotion_state == "RESOLVED_ELIGIBLE"
        and brief.freshness == "CURRENT"
        and brief.event_timing == "OBSERVED"
    )
    # A later collection with no new result must not erase still-relevant saved
    # intelligence. These records passed identity/relevance gates when created;
    # they remain explicitly stale and retain their real publication dates.
    recent_saved = tuple(
        brief
        for brief in briefs
        if brief.resolution_state == "RESOLVED"
        and brief.seller_promotion_state in {"WITHHELD_STALE", "RESOLVED_NEEDS_REVIEW"}
        and brief.freshness == "STALE"
        and brief.event_timing == "OBSERVED"
        and brief.publication_timestamp is not None
        and public_clock - timedelta(days=SAVED_INTELLIGENCE_WINDOW_DAYS)
        <= brief.publication_timestamp
        <= public_clock
    )
    upcoming = tuple(
        sorted(
            (
                brief
                for brief in briefs
                if brief.resolution_state == "RESOLVED"
                and brief.seller_promotion_state == "RESOLVED_ELIGIBLE"
                and brief.freshness == "CURRENT"
                and brief.event_timing == "UPCOMING"
                and brief.relevant_event_timestamp is not None
            ),
            key=lambda item: (item.relevant_event_timestamp, item.id),
        )
    )
    current = tuple(
        sorted(
            current,
            key=lambda item: (
                0 if item.watchlist_eligible else 1,
                -(item.publication_timestamp.timestamp() if item.publication_timestamp else 0),
                item.id,
            ),
        )
    )
    recent_saved = tuple(
        sorted(
            recent_saved,
            key=lambda item: (
                0 if item.watchlist_eligible else 1,
                -item.publication_timestamp.timestamp(),
                item.id,
            ),
        )
    )

    alert_items = [
        {
            "id": item.id,
            "kind": "COMMERCIAL_REVIEW",
            "account_id": item.account_id,
            "severity": item.severity,
            "reason": item.trigger_reason,
            "recommended_action": item.recommended_action,
            "evidence_ids": item.evidence_ids,
            "observed_at": item.observed_at,
            "data_mode": "SAMPLE",
            "business_unit_ids": (item.business_unit,) if getattr(item, 'business_unit', None) else (),
        }
        for item in alerts
    ]
    alert_items.sort(
        key=lambda item: (
            _SEVERITY_ORDER.get(item["severity"].upper(), 9),
            -item["observed_at"].timestamp(),
            item["id"],
        )
    )
    action_briefs = tuple(
        brief for brief in (*current, *recent_saved) if brief.priority_eligible
    )
    signal_items = [
        _public_item(brief, outcome_lane="ACTION_PRIORITIES")
        for brief in action_briefs
    ]
    review_briefs = tuple(
        sorted(
            (
                brief
                for brief in briefs
                if brief.resolution_state == "RESOLVED"
                and brief.seller_promotion_state == "RESOLVED_NEEDS_REVIEW"
                and brief.analysis_status == "READY"
                and brief.commercial_relevance_state
                in _VALIDATION_RELEVANCE_STATES
                and not brief.priority_eligible
                and brief.event_timing == "OBSERVED"
                and (
                    brief.freshness == "CURRENT"
                    or (
                        brief.freshness == "STALE"
                        and brief.publication_timestamp is not None
                        and public_clock - timedelta(days=SAVED_INTELLIGENCE_WINDOW_DAYS)
                        <= brief.publication_timestamp
                        <= public_clock
                    )
                )
            ),
            key=lambda item: (
                0 if item.watchlist_eligible else 1,
                -(item.publication_timestamp.timestamp() if item.publication_timestamp else 0),
                item.context_id or item.id,
            ),
        )
    )
    validation_items = [
        _public_item(brief, outcome_lane="NEEDS_VALIDATION")
        for brief in review_briefs
    ]

    watch_targets = {
        target.canonical_account_id: target
        for targets in monitor_snapshot.get("watch_targets", {}).values()
        for target in targets
    }
    watched_accounts = [
        {
            "account_id": target.canonical_account_id,
            "name": target.legal_name,
            "relationship": account_by_id[target.canonical_account_id].relationship.value,
            "markets": target.markets,
            "watch_type": "SYSTEM_RECOMMENDED",
            "reasons": tuple(asdict(reason) for reason in target.reasons),
        }
        for target in watch_targets.values()
        if target.canonical_account_id in account_by_id
    ]
    watched_accounts.sort(key=lambda item: (item["name"].casefold(), item["account_id"]))

    watched_program_ids = {
        brief.canonical_program_id
        for brief in (*current, *upcoming)
        if brief.canonical_program_id
    }
    watched_programs = [
        {
            "program_id": program_id,
            "name": program_by_id[program_id].name,
            "account_id": program_by_id[program_id].account_id,
            "watch_type": "SYSTEM_RECOMMENDED",
            "reason": "A current or upcoming governed Signal Brief is associated with this program.",
            "provenance": "GOVERNED_SIGNAL_BRIEF",
        }
        for program_id in sorted(watched_program_ids)
        if program_id in program_by_id
    ]

    source_states = tuple(monitor_snapshot.get("sources", ()))
    market_hubs = []
    for market in PRIMARY_MARKET_ORDER:
        market_current = tuple(brief.id for brief in current if market in brief.markets)
        market_upcoming = tuple(brief.id for brief in upcoming if market in brief.markets)
        market_accounts = tuple(
            item["account_id"] for item in watched_accounts if market in item["markets"]
        )
        market_programs = tuple(
            item["program_id"]
            for item in watched_programs
            if any(
                market in brief.markets
                for brief in (*current, *upcoming)
                if brief.canonical_program_id == item["program_id"]
            )
        )
        coverage = tuple(
            source.source_id
            for source in source_states
            if market
            in monitor_snapshot.get("source_markets", {}).get(source.source_id, ())
        )
        coverage_detail = tuple(
            {
                "source_id": source.source_id,
                "source_name": source.source_name,
                "state": source.state.value,
                "last_success_at": source.last_success_at,
            }
            for source in source_states
            if source.source_id in coverage
        )
        gaps = []
        if not market_current:
            gaps.append("No current eligible collected signal")
        if not market_upcoming:
            gaps.append("No source-supported upcoming date")
        if not coverage:
            gaps.append("No configured source coverage declared")
        market_hubs.append(
            {
                "market": market,
                "current_signal_ids": market_current,
                "upcoming_signal_ids": market_upcoming,
                "watched_account_ids": market_accounts,
                "watched_program_ids": market_programs,
                "source_ids": coverage,
                "source_coverage": coverage_detail,
                "gaps": tuple(gaps),
            }
        )

    source_warnings = [
        {
            "source_id": source.source_id,
            "source_name": source.source_name,
            "state": source.state.value,
            "last_success_at": source.last_success_at,
            "message": source.failure_summary
            or (
                "No collection attempt has been recorded."
                if source.state.value == "NEVER_ATTEMPTED"
                else "Current source evidence is unavailable."
            ),
        }
        for source in source_states
        if source.state.value not in {"HEALTHY"}
    ]
    missingness = []
    if not current:
        missingness.append("No current eligible live Signal Briefs are available.")
    if not upcoming:
        missingness.append("No source-supported upcoming dates are available.")
    if not watched_programs:
        missingness.append("No governed watched-program association is available.")
    if monitor_snapshot.get("scheduler_state") != "COLLECTION_OBSERVED_CURRENT":
        missingness.append("A current scheduled collection is not verified.")

    return {
        "generated_at": generated_at,
        "daily_briefing": {
            "headline": "Seller briefing",
            "current_live_signal_count": len(current),
            "upcoming_count": len(upcoming),
            "commercial_attention_count": len(alert_items),
            "scheduler_state": monitor_snapshot.get("scheduler_state"),
            "worker_runtime_state": monitor_snapshot.get("worker_runtime_state"),
            "live_intelligence_available": bool(current),
        },
        "public_intelligence_counts": {
            "action_priorities": len(signal_items),
            "needs_validation": len(validation_items),
        },
        "action_priorities": tuple(signal_items),
        "needs_validation_assessments": tuple(validation_items),
        # Filter consumers need the whole governed sequence, not eight alerts
        # selected before customer/BU scope. Cards are a projection of this list.
        "priority_briefing": (*alert_items, *signal_items),
        "current_signal_briefs": tuple(_brief_dict(item) for item in current),
        "saved_recent_signal_briefs": tuple(_brief_dict(item) for item in recent_saved),
        "upcoming_radar": tuple(_brief_dict(item) for item in upcoming),
        "market_hubs": tuple(market_hubs),
        "watched_accounts": tuple(watched_accounts),
        "watched_programs": tuple(watched_programs),
        "user_saved_watch_items": (),
        "watchlist_mode": "SYSTEM_RECOMMENDED_READ_ONLY",
        "source_health_warnings": tuple(source_warnings),
        "curated_reference_signal_ids": tuple(
            item["id"]
            for item in curated_signals
            if item.get("data_mode") == "CURATED_PUBLIC"
        ),
        "missingness": tuple(missingness),
        "ordering": (
            "Commercial reviews: HIGH, MEDIUM, LOW; then observed timestamp descending; then stable ID.",
            "Current signals: strategic-watch match first; then publication timestamp descending; then stable ID.",
            "Radar: source-supported future timestamp ascending; then stable ID.",
            "Markets: canonical taxonomy order.",
        ),
    }
