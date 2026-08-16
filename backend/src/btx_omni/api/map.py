from decimal import Decimal

from fastapi import APIRouter, Depends

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime

router = APIRouter(prefix="/map", tags=["map"])
BTX_FACILITY = {"id": "btx-southwest", "name": "BTX Southwest", "latitude": Decimal("33.4484"), "longitude": Decimal("-112.0740")}


@router.get("")
def map_data(industry: str | None = None, runtime: PocRuntime = Depends(get_runtime)) -> dict:
    sample = runtime.environment()
    ranks = {(item.account_id, item.industry): item for item in sample.ranks}
    records = []
    for account in sample.accounts:
        if industry and industry not in account.industries:
            continue
        facility = next(item for item in sample.facilities if item.account_id == account.id)
        rank = ranks[(account.id, account.industries[0])]
        distance_input = abs(facility.latitude - BTX_FACILITY["latitude"]) + abs(facility.longitude - BTX_FACILITY["longitude"])
        records.append({"account_id": account.id, "industry": account.industries[0], "relationship": account.relationship, "latitude": facility.latitude, "longitude": facility.longitude, "external_rank": rank.rank, "commercial_state": account.relationship, "nearest_btx_facility": BTX_FACILITY, "proximity_input": str(distance_input), "deep_account": account.id in {item.account_id for item in sample.commercial_contexts}})
    return {"layers": sorted({item.industries[0] for item in sample.accounts}), "records": records, "proximity_note": "Seller planning input only; never an attractiveness input."}
