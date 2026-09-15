"""Governed geographic read model for the Google Maps seller workspace."""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from fastapi import APIRouter, Depends

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.domain.alerts import CommercialAlertKind
from btx_omni.domain.markets import PRIMARY_MARKET_ORDER, primary_market_label
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.commercial.briefing import commercial_briefing
from btx_omni.modules.commercial.map_context import map_commercial_context
from btx_omni.modules.scoring.account_attractiveness import (
    seller_attractiveness_projection,
)
from btx_omni.modules.scoring.prospect_fit import (
    prospect_fit_payload,
    prospect_fit_projection,
)
from btx_omni.monitor.briefs import (
    SignalBrief,
    apply_cached_synthesis,
    brief_cache_id,
    governed_content_hash,
    signal_briefs_for_monitor,
)

router = APIRouter(prefix="/map", tags=["map"])
EARTH_RADIUS_MILES = 3958.7613


def _coordinates(
    latitude: Decimal | None, longitude: Decimal | None
) -> dict[str, str] | None:
    if (
        latitude is None
        or longitude is None
        or not (-90 <= latitude <= 90 and -180 <= longitude <= 180)
    ):
        return None
    return {"latitude": str(latitude), "longitude": str(longitude)}


def haversine_miles(
    latitude_a: Decimal,
    longitude_a: Decimal,
    latitude_b: Decimal,
    longitude_b: Decimal,
) -> Decimal:
    """Return straight-line great-circle miles between verified coordinates."""
    lat_a, lon_a, lat_b, lon_b = map(
        radians,
        map(float, (latitude_a, longitude_a, latitude_b, longitude_b)),
    )
    delta_lat, delta_lon = lat_b - lat_a, lon_b - lon_a
    haversine = (
        sin(delta_lat / 2) ** 2 + cos(lat_a) * cos(lat_b) * sin(delta_lon / 2) ** 2
    )
    return Decimal(str(2 * EARTH_RADIUS_MILES * asin(sqrt(haversine)))).quantize(
        Decimal("0.1")
    )


def _seller_briefs(runtime: PocRuntime) -> tuple:
    briefs = []
    for deterministic in signal_briefs_for_monitor(
        runtime.monitor, environment=runtime.environment()
    ):
        cached = (
            runtime.monitor.repository.brief_synthesis(
                brief_cache_id(deterministic), governed_content_hash(deterministic)
            )
            if runtime.monitor.repository
            else None
        )
        briefs.append(apply_cached_synthesis(deterministic, cached))
    return tuple(briefs)


def _map_brief_marker_mode(
    brief: SignalBrief, *, account_id: str | None, coordinates: dict | None
) -> str | None:
    """Admit only governed, resolved Signal Briefs with supplied geography."""
    eligible = (
        account_id is not None
        and brief.resolution_state == "RESOLVED"
        and brief.seller_promotion_state == "RESOLVED_ELIGIBLE"
        and brief.data_mode != "CURATED_PUBLIC"
        and coordinates is not None
    )
    if not eligible:
        return None
    if brief.freshness == "CURRENT" and brief.event_timing == "OBSERVED":
        return "CURRENT_COLLECTED"
    if brief.event_timing == "UPCOMING" and brief.relevant_event_timestamp is not None:
        return "UPCOMING"
    return None


def _map_intelligence_point(
    brief: SignalBrief,
    *,
    account_id: str,
    facility_id: str,
    coordinates: dict,
    marker_mode: str,
) -> dict:
    """Retain the full governed brief while adding only canonical Map identity."""
    return {
        **asdict(brief),
        "id": brief.id,
        "map_id": f"intelligence:{brief.context_id or brief.id}",
        "entity_type": "INTELLIGENCE",
        "event_id": brief.id,
        "account_id": account_id,
        "facility_id": facility_id,
        "program_id": brief.canonical_program_id,
        "title": brief.headline,
        "primary_markets": brief.markets,
        "event_date": brief.relevant_event_timestamp,
        "coordinates": coordinates,
        "coordinate_derivation": "CANONICAL_FACILITY",
        "marker_mode": marker_mode,
    }


def _account_segment(
    *,
    account_id: str,
    relationship: str,
    active_client_account_ids: set[str],
    dormant_customer_account_ids: set[str],
    prospect_account_ids: set[str],
) -> str:
    """Project governed SAMPLE commercial state without treating history as active status."""
    # Canonical account classification wins over the presence of SAMPLE context.
    # A scenario record must not silently turn a researched public-market company
    # into a current Customer.
    if relationship == "FORMER_CUSTOMER" or account_id in dormant_customer_account_ids:
        return "DORMANT_CUSTOMER"
    if relationship in {"PUBLIC_MARKET", "PROSPECT", "TARGET"}:
        return "PROSPECT"
    if relationship == "CURRENT_CUSTOMER" or account_id in active_client_account_ids:
        return "CURRENT_CLIENT"
    if account_id in prospect_account_ids:
        return "PROSPECT"
    return "UNKNOWN"


@router.get("")
def map_data(
    industry: str | None = None, runtime: PocRuntime = Depends(get_runtime)
) -> dict:
    sample = runtime.environment()
    accounts = {account.id: account for account in sample.accounts}
    # Map points require a canonical, verified facility.  In particular, do not
    # turn an account's HQ (or any other facility) into a fallback location.
    facilities = tuple(
        facility
        for facility in sample.facilities
        if (
            facility.verification_state.startswith("VERIFIED_PUBLIC")
            or facility.verification_state == "SANITIZED_REFERENCE_LOCATION"
        )
        and _coordinates(facility.latitude, facility.longitude)
    )
    btx_facilities = tuple(
        facility
        for facility in sample.btx_facilities
        if _coordinates(facility.latitude, facility.longitude)
    )
    selected_accounts = tuple(
        account
        for account in sample.accounts
        if not industry or industry in account.industries
    )
    selected_ids = {account.id for account in selected_accounts}
    commercial_accounts = {item.account_id for item in sample.commercial_contexts}
    commercial_alerts = CommercialAlertEngine().evaluate(
        sample.commercial_contexts,
        sample.quotes,
        observed_at=runtime.observed_at(),
        orders=sample.orders,
    )
    dormant_customer_accounts = {
        item.account_id
        for item in commercial_alerts
        if item.type is CommercialAlertKind.CUSTOMER_INACTIVITY
    }
    active_client_accounts = commercial_accounts - dormant_customer_accounts
    prospect_accounts = {
        item.account_id
        for item in sample.crm_companies
        if item.properties
        and item.properties.get("btx_customer_segment_console_enriched") == "PROSPECT"
    }
    briefs = _seller_briefs(runtime)
    current_briefs_by_account = {
        account_id: tuple(
            asdict(brief)
            for brief in briefs
            if account_id in brief.canonical_account_ids
            and brief.resolution_state == "RESOLVED"
            and brief.analysis_status == "READY"
            and brief.event_timing == "OBSERVED"
        )[:5]
        for account_id in selected_ids
    }
    upcoming_briefs_by_account = {
        account_id: tuple(
            asdict(brief)
            for brief in briefs
            if account_id in brief.canonical_account_ids
            and brief.resolution_state == "RESOLVED"
            and brief.seller_promotion_state == "RESOLVED_ELIGIBLE"
            and brief.freshness == "CURRENT"
            and brief.event_timing == "UPCOMING"
            and brief.relevant_event_timestamp is not None
        )
        for account_id in selected_ids
    }
    account_points = []
    pending_accounts = []
    for account in selected_accounts:
        candidates = tuple(
            sorted(
                (
                    facility
                    for facility in facilities
                    if facility.account_id == account.id
                ),
                key=lambda item: item.id,
            )
        )
        if not candidates:
            pending_accounts.append(
                {
                    "id": f"account:{account.id}:location-pending",
                    "account_id": account.id,
                    "name": account.legal_name,
                    "primary_markets": account.industries,
                    "account_segment": _account_segment(
                        account_id=account.id,
                        relationship=account.relationship.value,
                        active_client_account_ids=active_client_accounts,
                        dormant_customer_account_ids=dormant_customer_accounts,
                        prospect_account_ids=prospect_accounts,
                    ),
                    "is_rich_scenario": account.id in sample.rich_scenarios
                    or account.id in sample.priority_scenarios,
                    "btx_top_100": account.btx_top_100,
                    "location_truth_state": "LOCATION_PENDING",
                    "reason": "No source-supported canonical site with verified coordinates is available.",
                }
            )
        scenario = sample.priority_scenarios.get(
            account.id
        ) or sample.rich_scenarios.get(account.id)
        score = (
            seller_attractiveness_projection(
                sample.attractiveness_inputs(account.id),
                calculated_at=runtime.observed_at(),
                excluded=bool(scenario and scenario.exclusion_reason),
                exclusion_reason=scenario.exclusion_reason if scenario else None,
            )
            if candidates
            else None
        )
        for location in candidates:
            nearest = min(
                btx_facilities,
                key=lambda item: haversine_miles(
                    location.latitude, location.longitude, item.latitude, item.longitude
                ),
                default=None,
            )
            distance = (
                haversine_miles(
                    location.latitude,
                    location.longitude,
                    nearest.latitude,
                    nearest.longitude,
                )
                if nearest
                else None
            )
            account_alerts = tuple(
                item for item in commercial_alerts if item.account_id == account.id
            )
            segment = _account_segment(
                account_id=account.id,
                relationship=account.relationship.value,
                active_client_account_ids=active_client_accounts,
                dormant_customer_account_ids=dormant_customer_accounts,
                prospect_account_ids=prospect_accounts,
            )
            account_points.append(
                {
                    "id": f"account:{account.id}:facility:{location.id}",
                    "entity_type": "ACCOUNT",
                    "account_id": account.id,
                    "facility_id": location.id,
                    "name": account.legal_name,
                    "primary_markets": account.industries,
                    "industry": primary_market_label(account.industries),
                    "relationship": account.relationship,
                    "account_segment": segment,
                    "is_rich_scenario": account.id in sample.rich_scenarios
                    or account.id in sample.priority_scenarios,
                    "btx_top_100": account.btx_top_100,
                    "btx_top_100_provenance": account.btx_top_100_provenance,
                    "coordinates": _coordinates(location.latitude, location.longitude),
                    "location_truth_state": location.verification_state,
                    "location_name": location.name,
                    "location_type": location.facility_type,
                    "location_provenance": location.provenance,
                    "commercial_state": "SIMULATED_BTX_CONTEXT"
                    if account.id in commercial_accounts
                    else "UNAVAILABLE",
                    "attractiveness_score": score.score,
                    "attractiveness_coverage": score.coverage,
                    "score_status": score.status,
                    "score_missingness": score.missingness,
                    "prospect_fit": prospect_fit_payload(
                        prospect_fit_projection(
                            account, applicable=segment == "PROSPECT"
                        )
                    ),
                    "nearest_btx_facility": {
                        "id": nearest.id,
                        "name": nearest.name,
                        "distance_miles": str(distance),
                        "distance_method": "HAVERSINE_STRAIGHT_LINE",
                    }
                    if nearest and distance is not None
                    else None,
                    "proximity_input": str(distance) if distance is not None else None,
                    "current_signal_briefs": current_briefs_by_account.get(
                        account.id, ()
                    ),
                    "upcoming_signal_briefs": upcoming_briefs_by_account.get(
                        account.id, ()
                    ),
                    "governed_next_step": account_alerts[0].recommended_action
                    if account_alerts
                    else None,
                    "selection_missingness": tuple(
                        item
                        for item, missing in (
                            (
                                "Applicable score inputs",
                                (segment == "PROSPECT" and not account.industries)
                                or (segment != "PROSPECT" and score.score is None),
                            ),
                            (
                                "current eligible Signal Brief",
                                not current_briefs_by_account.get(account.id),
                            ),
                            (
                                "upcoming governed date",
                                not upcoming_briefs_by_account.get(account.id),
                            ),
                            (
                                "commercial context",
                                account.id not in commercial_accounts,
                            ),
                        )
                        if missing
                    ),
                    "deep_account": account.id in commercial_accounts,
                }
            )
    facility_points = [
        {
            "id": f"facility:{facility.id}",
            "entity_type": "FACILITY",
            "account_id": facility.account_id,
            "facility_id": facility.id,
            "name": facility.name,
            "primary_markets": accounts[facility.account_id].industries,
            "city": facility.city,
            "region": facility.region,
            "country": facility.country,
            "location_type": facility.facility_type,
            "truth_state": facility.verification_state,
            "coordinates": _coordinates(facility.latitude, facility.longitude),
            "source_url": facility.source_url,
            "provenance": facility.provenance,
        }
        for facility in facilities
        if facility.account_id in selected_ids
    ]
    btx_points = [
        {
            "id": f"btx-facility:{facility.id}",
            "entity_type": "BTX_FACILITY",
            "facility_id": facility.id,
            "business_unit_id": facility.business_unit_id,
            "name": facility.name,
            "city": facility.city,
            "region": facility.region,
            "country": facility.country,
            "coordinates": _coordinates(facility.latitude, facility.longitude),
            "source_url": facility.source_url,
            "source_type": facility.source_type,
            "truth_state": facility.verification_state,
            "verification_state": facility.verification_state,
            "provenance": facility.provenance,
        }
        for facility in btx_facilities
    ]
    facility_coordinates = {
        facility.id: _coordinates(facility.latitude, facility.longitude)
        for facility in facilities
    }
    facility_accounts = {facility.id: facility.account_id for facility in facilities}
    intelligence_points = []
    for brief in briefs:
        account_id = next(
            (item for item in brief.canonical_account_ids if item in selected_ids), None
        )
        facility_id = brief.canonical_facility_id
        if facility_id and facility_accounts.get(facility_id) != account_id:
            # A multi-company or account-wide event cannot borrow another
            # subject's facility merely because that facility was resolved on
            # the shared public event.
            continue
        coordinates = facility_coordinates.get(facility_id) if facility_id else None
        marker_mode = _map_brief_marker_mode(
            brief, account_id=account_id, coordinates=coordinates
        )
        if marker_mode is None:
            continue
        intelligence_points.append(
            _map_intelligence_point(
                brief,
                account_id=account_id,
                facility_id=facility_id,
                coordinates=coordinates,
                marker_mode=marker_mode,
            )
        )
    # Map and Account360 consume the same current commercial-case owner. Generic
    # portfolio alerts must not overwrite an account-specific proposed next step.
    commercial_briefs = {
        account_id: commercial_briefing(
            ledger, canonical_account_id=account_id, revision=sample.commercial_revision
        )
        for account_id, ledger in sample.commercial_ledgers.items()
        if account_id in selected_ids
    }
    commercial_facets = {
        account_id: map_commercial_context(
            sample.commercial_ledgers.get(account_id),
            canonical_account_id=account_id,
            revision=sample.commercial_revision,
        )
        for account_id in {
            point["account_id"] for point in [*account_points, *pending_accounts]
        }
    }
    for point in [*account_points, *pending_accounts]:
        point.update(commercial_facets[point["account_id"]])
        brief = commercial_briefs.get(point["account_id"])
        if brief:
            point["governed_next_step"] = brief["next_action"]
            point["commercial_briefing"] = brief
    available_markets = {
        market for account in sample.accounts for market in account.industries
    }
    return {
        "layers": [
            market for market in PRIMARY_MARKET_ORDER if market in available_markets
        ],
        "accounts": account_points,
        "pending_accounts": pending_accounts,
        "facilities": facility_points,
        "btx_facilities": btx_points,
        "intelligence": intelligence_points,
        "records": account_points,
        "public_locations": facility_points,
        "intelligence_signals": intelligence_points,
        "proximity_note": "Seller planning input only; never an attractiveness input.",
    }
