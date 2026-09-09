from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from inspect import getsource

import pytest
from httpx import ASGITransport, AsyncClient

from btx_omni.api.map import (
    _map_brief_marker_mode,
    _map_intelligence_point,
    haversine_miles,
    map_data,
)
from btx_omni.app import create_app
from btx_omni.monitor.briefs import SignalBrief


def _brief(**changes: object) -> SignalBrief:
    now = datetime.now(UTC)
    baseline = SignalBrief(
        id="event-map",
        headline="Facility update reported",
        what_happened="A governed source reported a facility update.",
        why_it_may_matter="The update is linked to a resolved Customer.",
        canonical_account_ids=("boeing",),
        canonical_program_id="program-1",
        markets=("Commercial Aerospace",),
        publication_timestamp=now - timedelta(hours=1),
        collection_timestamp=now,
        freshness="CURRENT",
        evidence_ids=("evidence-1",),
        source_url="https://example.test/evidence",
        source_system="official-source",
        data_mode="LIVE_PUBLIC",
        resolution_state="RESOLVED",
        seller_promotion_state="RESOLVED_ELIGIBLE",
        what_to_watch="Watch for a supported follow-up.",
        recommended_action="Review the governed evidence.",
        missing_fields=(),
        seller_summary="Facility update reported.",
        event_timing="OBSERVED",
        relevant_event_timestamp=now - timedelta(hours=1),
    )
    return replace(baseline, **changes)


def test_haversine_distance_is_straight_line_miles() -> None:
    distance = haversine_miles(
        Decimal("40.7128"),
        Decimal("-74.0060"),
        Decimal("34.0522"),
        Decimal("-118.2437"),
    )
    assert Decimal(2440) < distance < Decimal(2450)


def test_haversine_distance_is_zero_for_same_verified_point() -> None:
    assert haversine_miles(
        Decimal("33.4484"),
        Decimal("-112.0740"),
        Decimal("33.4484"),
        Decimal("-112.0740"),
    ) == Decimal("0.0")


@pytest.mark.asyncio
async def test_map_selection_projection_is_governed_and_uses_miles() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.get("/api/map")
    assert response.status_code == 200
    records = response.json()["records"]
    assert records
    assert all(
        record["nearest_btx_facility"]["distance_method"]
        == "HAVERSINE_STRAIGHT_LINE"
        for record in records
        if record["nearest_btx_facility"]
    )
    assert all("rank" not in record for record in records)
    assert all(
        brief["freshness"] == "CURRENT"
        and brief["resolution_state"] == "RESOLVED"
        for record in records
        for brief in record["current_signal_briefs"]
    )
    assert all(record["selection_missingness"] is not None for record in records)


@pytest.mark.asyncio
async def test_map_lists_accounts_without_verified_sites_without_fake_coordinates() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        result = (await client.get("/api/map")).json()
        accounts = (await client.get("/api/accounts")).json()
    located = {record["account_id"] for record in result["accounts"]}
    pending = result["pending_accounts"]
    pending_ids = {record["account_id"] for record in pending}
    assert not located & pending_ids
    assert len(pending_ids) == len(pending)
    assert all("coordinates" not in record for record in pending)
    assert all(record["location_truth_state"] == "LOCATION_PENDING" for record in pending)
    # Account API may wrap its records; compare canonical identity, not fixture counts.
    listed = accounts if isinstance(accounts, list) else accounts["accounts"]
    assert {record["id"] for record in listed} <= located | pending_ids


def test_map_signal_marker_eligibility_is_governed() -> None:
    coordinates = {"latitude": "33", "longitude": "-112"}
    assert (
        _map_brief_marker_mode(
            _brief(), account_id="boeing", coordinates=coordinates
        )
        == "CURRENT_COLLECTED"
    )
    for brief in (
        _brief(freshness="STALE"),
        _brief(resolution_state="UNRESOLVED"),
        _brief(seller_promotion_state="UNRESOLVED"),
        _brief(data_mode="CURATED_PUBLIC"),
        _brief(event_timing="UNKNOWN"),
    ):
        assert (
            _map_brief_marker_mode(
                brief, account_id="boeing", coordinates=coordinates
            )
            is None
        )
    assert _map_brief_marker_mode(_brief(), account_id=None, coordinates=coordinates) is None
    assert _map_brief_marker_mode(_brief(), account_id="boeing", coordinates=None) is None


def test_upcoming_map_signal_requires_supported_timestamp() -> None:
    coordinates = {"latitude": "33", "longitude": "-112"}
    upcoming = _brief(
        event_timing="UPCOMING",
        relevant_event_timestamp=datetime.now(UTC) + timedelta(days=2),
    )
    assert (
        _map_brief_marker_mode(
            upcoming, account_id="boeing", coordinates=coordinates
        )
        == "UPCOMING"
    )
    assert (
        _map_brief_marker_mode(
            replace(upcoming, relevant_event_timestamp=None),
            account_id="boeing",
            coordinates=coordinates,
        )
        is None
    )


def test_map_read_has_no_model_provider_call_path() -> None:
    source = getsource(map_data)
    assert "Gemini" not in source
    assert "provider" not in source
    assert "synthesize" not in source


def test_map_intelligence_point_retains_full_signal_brief_truth() -> None:
    brief = _brief(missing_fields=("owner",), summary_mode="GEMINI_ASSISTED")
    point = _map_intelligence_point(
        brief,
        account_id="boeing",
        facility_id="public-hq-boeing",
        coordinates={"latitude": "33", "longitude": "-112"},
        marker_mode="CURRENT_COLLECTED",
    )
    assert point["headline"] == "Facility update reported"
    assert point["account_id"] == "boeing"
    assert point["program_id"] == "program-1"
    assert point["facility_id"] == "public-hq-boeing"
    assert point["data_mode"] == "LIVE_PUBLIC"
    assert point["freshness"] == "CURRENT"
    assert point["event_timing"] == "OBSERVED"
    assert point["resolution_state"] == "RESOLVED"
    assert point["seller_promotion_state"] == "RESOLVED_ELIGIBLE"
    assert point["summary_mode"] == "GEMINI_ASSISTED"
    assert point["evidence_ids"] == ("evidence-1",)
    assert point["source_system"] == "official-source"
    assert point["missing_fields"] == ("owner",)
