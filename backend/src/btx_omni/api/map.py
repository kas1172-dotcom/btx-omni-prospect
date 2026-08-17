from decimal import Decimal

from fastapi import APIRouter, Depends

from btx_omni.api.accounts import get_runtime
from btx_omni.api.intelligence_projection import intelligence_signals
from btx_omni.api.runtime import PocRuntime

router = APIRouter(prefix="/map", tags=["map"])
BTX_FACILITY = {"id": "btx-southwest", "name": "BTX Southwest", "latitude": Decimal("33.4484"), "longitude": Decimal("-112.0740")}


@router.get("")
def map_data(industry: str | None = None, runtime: PocRuntime = Depends(get_runtime)) -> dict:
    sample = runtime.environment()
    records = []
    for account in sample.accounts:
        if industry and industry not in account.industries:
            continue
        facility = next((item for item in sample.facilities if item.account_id == account.id), None)
        if facility is None:
            continue
        distance_input = abs(facility.latitude - BTX_FACILITY["latitude"]) + abs(facility.longitude - BTX_FACILITY["longitude"])
        records.append({"account_id": account.id, "industry": account.industries[0], "relationship": account.relationship, "is_rich_scenario": account.id in sample.rich_scenarios, "latitude": facility.latitude, "longitude": facility.longitude, "commercial_state": "SIMULATED_BTX_CONTEXT" if account.id in {item.account_id for item in sample.commercial_contexts} else "UNAVAILABLE", "location_truth_state": facility.verification_state, "nearest_btx_facility": BTX_FACILITY, "proximity_input": str(distance_input), "deep_account": account.id in {item.account_id for item in sample.commercial_contexts}})
    account_coordinates = {item["account_id"]: {"latitude": item["latitude"], "longitude": item["longitude"]} for item in records}
    signals = [{**signal, "coordinates": account_coordinates.get(signal["account_id"])} for signal in intelligence_signals(runtime)]
    public_locations = [{"account_id": item.account_id, "location_id": item.id, "location_name": item.name, "location_type": item.facility_type, "truth_state": item.verification_state, "city": item.city, "region": item.region, "country": item.country, "latitude": item.latitude, "longitude": item.longitude, "provenance": item.provenance, "source_url": item.source_url} for item in sample.public_facilities]
    return {"layers": sorted({item.industries[0] for item in sample.accounts}), "records": records, "public_locations": public_locations, "intelligence_signals": signals, "proximity_note": "Seller planning input only; never an attractiveness input."}
