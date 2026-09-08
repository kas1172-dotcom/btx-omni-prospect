from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from btx_omni.modules.command_center import build_command_center
from btx_omni.monitor.briefs import SignalBrief
from btx_omni.monitor.targeting import TargetReason, WatchTarget

NOW = datetime(2026, 8, 28, 12, tzinfo=UTC)


def brief(
    brief_id: str,
    *,
    timing: str = "OBSERVED",
    event_at: datetime | None = None,
    freshness: str = "CURRENT",
    resolved: bool = True,
    watched: bool = False,
) -> SignalBrief:
    return SignalBrief(
        brief_id,
        "Contract update reported",
        "A governed source reported an update.",
        "Review its explicit Customer context.",
        ("acct-1",),
        "program-1",
        ("Defense",),
        event_at,
        NOW,
        freshness,
        ("evidence-1",),
        "https://example.com/evidence",
        "official-source",
        "LIVE_PUBLIC",
        "RESOLVED" if resolved else "UNRESOLVED",
        "RESOLVED_ELIGIBLE" if resolved else "UNRESOLVED",
        "Watch the source-supported date.",
        "Review the evidence.",
        (),
        "Governed summary.",
        event_timing=timing,
        relevant_event_timestamp=event_at,
        watchlist_eligible=watched,
        priority_reasons=(
            TargetReason("WATCH", "Governed watch reason.", "REFERENCE", "ref-1"),
        )
        if watched
        else (),
    )


def projection(*briefs: SignalBrief, alerts: tuple = ()) -> dict:
    account = SimpleNamespace(
        id="acct-1",
        legal_name="Example Customer",
        relationship=SimpleNamespace(value="TARGET"),
    )
    program = SimpleNamespace(id="program-1", name="Example Program", account_id="acct-1")
    target = WatchTarget(
        "acct-1",
        "Example Customer",
        ("Defense",),
        (TargetReason("REFERENCE", "Explicit reference target.", "REFERENCE", "ref-1"),),
        SimpleNamespace(),
    )
    source = SimpleNamespace(
        source_id="official",
        source_name="Official source",
        state=SimpleNamespace(value="NEVER_ATTEMPTED"),
        last_success_at=None,
        failure_summary=None,
    )
    return build_command_center(
        accounts=(account,),
        programs=(program,),
        alerts=alerts,
        monitor_snapshot={
            "signal_briefs": briefs,
            "watch_targets": {"usaspending": (target,)},
            "sources": (source,),
            "source_markets": {"official": ("Defense",)},
            "scheduler_state": "SCHEDULE_NOT_CONFIRMED",
            "worker_runtime_state": "WORKER_READY_FOR_INVOCATION",
        },
        curated_signals=[{"id": "curated-1", "data_mode": "CURATED_PUBLIC"}],
        generated_at=NOW,
    )


def test_current_radar_and_market_hubs_are_governed_and_separate() -> None:
    current = brief("current", event_at=NOW - timedelta(hours=1))
    upcoming = brief(
        "upcoming", timing="UPCOMING", event_at=NOW + timedelta(days=2)
    )
    unknown = brief("unknown", timing="UNKNOWN", event_at=None)
    stale = brief("stale", event_at=NOW - timedelta(days=30), freshness="STALE")
    unresolved = brief("unresolved", event_at=NOW, resolved=False)
    result = projection(current, upcoming, unknown, stale, unresolved)

    assert [item["id"] for item in result["current_signal_briefs"]] == ["current"]
    assert [item["id"] for item in result["upcoming_radar"]] == ["upcoming"]
    defense = next(item for item in result["market_hubs"] if item["market"] == "Defense")
    assert defense["current_signal_ids"] == ("current",)
    assert defense["upcoming_signal_ids"] == ("upcoming",)
    assert len(result["market_hubs"]) == 7


def test_priority_order_is_stable_and_watch_truth_is_read_only() -> None:
    later = brief("z-later", event_at=NOW, watched=False)
    watched = brief("a-watched", event_at=NOW - timedelta(hours=2), watched=True)
    same_time_b = brief("b", event_at=NOW - timedelta(hours=3))
    same_time_a = brief("a", event_at=NOW - timedelta(hours=3))
    result = projection(later, same_time_b, watched, same_time_a)

    assert [item["id"] for item in result["current_signal_briefs"]] == [
        "a-watched",
        "z-later",
        "a",
        "b",
    ]
    assert result["watchlist_mode"] == "SYSTEM_RECOMMENDED_READ_ONLY"
    assert result["user_saved_watch_items"] == ()
    assert result["watched_accounts"][0]["reasons"][0]["source_record_id"] == "ref-1"
    serialized = repr(result).lower()
    assert "rank" not in serialized
    assert "relationship strength" not in serialized


def test_degraded_projection_does_not_claim_live_collection() -> None:
    result = projection()
    assert result["daily_briefing"]["live_intelligence_available"] is False
    assert result["curated_reference_signal_ids"] == ("curated-1",)
    assert "No current eligible live Signal Briefs are available." in result["missingness"]
    assert result["source_health_warnings"][0]["state"] == "NEVER_ATTEMPTED"


def test_filter_consumers_receive_priorities_beyond_old_eight_item_cutoff():
    alerts = tuple(SimpleNamespace(id=f'alert-{index:02}', account_id=f'customer-{index}', severity='HIGH',
        trigger_reason='Actual source reason', recommended_action='Actual next action',
        evidence_ids=(f'source-{index}',), observed_at=NOW, business_unit='bu-scoped' if index == 10 else None)
        for index in range(12))
    items = projection(alerts=alerts)['priority_briefing']
    assert [item['id'] for item in items] == [alert.id for alert in alerts]
    assert items[10]['business_unit_ids'] == ('bu-scoped',)
    assert items[0]['business_unit_ids'] == ()  # No inferred account-level fallback.


def test_priority_projection_is_ordered_and_self_describing() -> None:
    def alert(alert_id: str, severity: str, observed_at: datetime):
        return SimpleNamespace(
            id=alert_id,
            account_id="acct-1",
            severity=severity,
            trigger_reason=f"Reason {alert_id}",
            recommended_action=f"Action {alert_id}",
            evidence_ids=(f"evidence-{alert_id}",),
            observed_at=observed_at,
        )

    alerts = (
        alert("low", "LOW", NOW),
        alert("high-old", "HIGH", NOW - timedelta(hours=1)),
        alert("medium", "MEDIUM", NOW),
        alert("high-new", "HIGH", NOW),
    )
    result = projection(
        brief("public", event_at=NOW - timedelta(minutes=5)), alerts=alerts
    )

    assert [item["id"] for item in result["priority_briefing"]] == [
        "high-new",
        "high-old",
        "medium",
        "low",
        "public",
    ]
    assert [item["data_mode"] for item in result["priority_briefing"]] == [
        "SAMPLE",
        "SAMPLE",
        "SAMPLE",
        "SAMPLE",
        "LIVE_PUBLIC",
    ]
    public = result["priority_briefing"][-1]
    assert public["signal_brief"]["id"] == "public"
    assert public["signal_brief"]["evidence_ids"] == ("evidence-1",)
    defense = next(item for item in result["market_hubs"] if item["market"] == "Defense")
    assert defense["source_coverage"] == (
        {
            "source_id": "official",
            "source_name": "Official source",
            "state": "NEVER_ATTEMPTED",
            "last_success_at": None,
        },
    )
