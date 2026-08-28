"""Small, typed geographic read model for the MapLibre surface."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends

from btx_omni.api.accounts import get_runtime
from btx_omni.api.intelligence_projection import intelligence_signals
from btx_omni.api.runtime import PocRuntime
from btx_omni.domain.alerts import CommercialAlertKind
from btx_omni.domain.markets import PRIMARY_MARKET_ORDER, primary_market_label
from btx_omni.modules.alerts.commercial import CommercialAlertEngine

router = APIRouter(prefix="/map", tags=["map"])


def _coordinates(latitude: Decimal | None, longitude: Decimal | None) -> dict[str, str] | None:
    if latitude is None or longitude is None or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return {"latitude": str(latitude), "longitude": str(longitude)}


def _account_segment(*, account_id: str, active_client_account_ids: set[str], dormant_customer_account_ids: set[str], prospect_account_ids: set[str]) -> str:
    """Project governed SAMPLE commercial state without treating history as active status."""
    if account_id in dormant_customer_account_ids:
        return "DORMANT_CUSTOMER"
    if account_id in active_client_account_ids:
        return "CURRENT_CLIENT"
    if account_id in prospect_account_ids:
        return "PROSPECT"
    return "UNKNOWN"


@router.get("")
def map_data(industry: str | None = None, runtime: PocRuntime = Depends(get_runtime)) -> dict:
    sample = runtime.environment()
    accounts = {account.id: account for account in sample.accounts}
    facilities = tuple(facility for facility in sample.facilities if _coordinates(facility.latitude, facility.longitude))
    btx_facilities = tuple(facility for facility in sample.btx_facilities if _coordinates(facility.latitude, facility.longitude))
    selected_accounts = tuple(account for account in sample.accounts if not industry or industry in account.industries)
    selected_ids = {account.id for account in selected_accounts}
    commercial_accounts = {item.account_id for item in sample.commercial_contexts}
    dormant_customer_accounts = {
        item.account_id
        for item in CommercialAlertEngine().evaluate(
            sample.commercial_contexts,
            sample.quotes,
            observed_at=runtime.observed_at(),
            orders=sample.orders,
        )
        if item.type is CommercialAlertKind.CUSTOMER_INACTIVITY
    }
    active_client_accounts = commercial_accounts - dormant_customer_accounts
    prospect_accounts = {
        item.account_id
        for item in sample.crm_companies
        if item.properties and item.properties.get("btx_customer_segment_console_enriched") == "PROSPECT"
    }
    account_points = []
    for account in selected_accounts:
        candidates = tuple(facility for facility in facilities if facility.account_id == account.id)
        location = next((facility for facility in candidates if facility.id == f"public-hq-{account.id}"), None) or next(iter(candidates), None)
        if location is None:
            continue
        nearest = min(btx_facilities, key=lambda item: abs(location.latitude - item.latitude) + abs(location.longitude - item.longitude), default=None)
        proximity = abs(location.latitude - nearest.latitude) + abs(location.longitude - nearest.longitude) if nearest else None
        account_points.append({"id": f"account:{account.id}", "entity_type": "ACCOUNT", "account_id": account.id, "name": account.legal_name, "primary_markets": account.industries, "industry": primary_market_label(account.industries), "relationship": account.relationship, "account_segment": _account_segment(account_id=account.id, active_client_account_ids=active_client_accounts, dormant_customer_account_ids=dormant_customer_accounts, prospect_account_ids=prospect_accounts), "is_rich_scenario": account.id in sample.rich_scenarios, "btx_top_100": account.btx_top_100, "coordinates": _coordinates(location.latitude, location.longitude), "location_truth_state": location.verification_state, "commercial_state": "SIMULATED_BTX_CONTEXT" if account.id in commercial_accounts else "UNAVAILABLE", "nearest_btx_facility": {"id": nearest.id, "name": nearest.name} if nearest else None, "proximity_input": str(proximity) if proximity is not None else None, "deep_account": account.id in commercial_accounts})
    facility_points = [{"id": f"facility:{facility.id}", "entity_type": "FACILITY", "account_id": facility.account_id, "facility_id": facility.id, "name": facility.name, "primary_markets": accounts[facility.account_id].industries, "city": facility.city, "region": facility.region, "country": facility.country, "location_type": facility.facility_type, "truth_state": facility.verification_state, "coordinates": _coordinates(facility.latitude, facility.longitude), "source_url": facility.source_url, "provenance": facility.provenance} for facility in facilities if facility.account_id in selected_ids]
    btx_points = [{"id": f"btx-facility:{facility.id}", "entity_type": "BTX_FACILITY", "facility_id": facility.id, "business_unit_id": facility.business_unit_id, "name": facility.name, "city": facility.city, "region": facility.region, "country": facility.country, "coordinates": _coordinates(facility.latitude, facility.longitude), "source_url": facility.source_url, "source_type": facility.source_type, "truth_state": facility.verification_state, "verification_state": facility.verification_state, "provenance": facility.provenance} for facility in btx_facilities]
    facility_coordinates = {facility.id: _coordinates(facility.latitude, facility.longitude) for facility in facilities}
    intelligence_points = []
    for signal in intelligence_signals(runtime):
        account_id, facility_id = signal.get("account_id"), signal.get("facility_id")
        if account_id not in selected_ids:
            continue
        coordinates = facility_coordinates.get(facility_id) if facility_id else None
        intelligence_points.append({"id": f"intelligence:{signal['id']}", "entity_type": "INTELLIGENCE", "event_id": signal["id"], "account_id": account_id, "facility_id": facility_id, "title": signal["title"], "primary_markets": accounts[account_id].industries if account_id in accounts else (), "event_date": signal.get("observed_at"), "source_url": signal["source_url"], "relevance": signal.get("relevance_explanation"), "evidence_state": signal.get("evidence_state"), "coordinates": coordinates, "coordinate_derivation": "CANONICAL_FACILITY" if coordinates else None})
    available_markets = {market for account in sample.accounts for market in account.industries}
    return {"layers": [market for market in PRIMARY_MARKET_ORDER if market in available_markets], "accounts": account_points, "facilities": facility_points, "btx_facilities": btx_points, "intelligence": intelligence_points, "records": account_points, "public_locations": facility_points, "intelligence_signals": intelligence_points, "proximity_note": "Seller planning input only; never an attractiveness input."}
