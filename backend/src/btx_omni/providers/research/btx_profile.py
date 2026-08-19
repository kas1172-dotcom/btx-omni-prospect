from __future__ import annotations

from decimal import Decimal

from btx_omni.core.classification import Classification
from btx_omni.domain.btx import BtxBusinessUnit, BtxFacility
from btx_omni.providers.research._catalog_support import document, source_provenance


def load_btx_business_units() -> tuple[BtxBusinessUnit, ...]:
    payload = document("btx_company_profile.json")
    source_ids = set(payload["sources"])
    units = []
    for row in payload["business_units"]:
        if not set(row["source_ids"]) <= source_ids:
            raise ValueError(f"business unit {row['id']} has unknown source")
        units.append(BtxBusinessUnit(row["id"], row["display_name"], row.get("website"), tuple(row.get("processes", ())), tuple(row.get("certifications", ())), source_provenance(row, classification=Classification.PUBLIC)))
    return tuple(units)


def load_btx_facilities(*, business_unit_ids: set[str]) -> tuple[BtxFacility, ...]:
    """Load only public, source-backed BTX locations suitable for map planning."""
    payload = document("btx_company_profile.json")
    source_ids = set(payload["sources"])
    facilities = []
    for row in payload.get("btx_facilities", []):
        facility_id = str(row["id"])
        business_unit_id = row.get("business_unit_id")
        if business_unit_id is not None and business_unit_id not in business_unit_ids:
            raise ValueError(f"BTX facility {facility_id} references unknown business unit {business_unit_id!r}")
        if not set(row.get("source_ids", ())) <= source_ids:
            raise ValueError(f"BTX facility {facility_id} has unknown source")
        latitude, longitude = row.get("latitude"), row.get("longitude")
        if (latitude is None) != (longitude is None):
            raise ValueError(f"BTX facility {facility_id} must provide both coordinates or neither")
        if latitude is not None and not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError(f"BTX facility {facility_id} has invalid coordinates")
        if latitude is not None and row.get("verification_state") != "VERIFIED_PUBLIC_FACILITY":
            raise ValueError(f"BTX facility {facility_id} coordinates require public verification")
        source_url = row.get("source_url")
        if source_url is not None and not str(source_url).startswith("https://"):
            raise ValueError(f"BTX facility {facility_id} has invalid source URL")
        facilities.append(BtxFacility(
            facility_id, business_unit_id, str(row["name"]), row.get("city"), row.get("region"), row.get("country"),
            Decimal(str(latitude)) if latitude is not None else None, Decimal(str(longitude)) if longitude is not None else None,
            str(row.get("verification_state", "MISSING_LOCATION")), source_url, row.get("source_type"),
            source_provenance({"id": facility_id, "source_url": source_url}, classification=Classification.PUBLIC),
        ))
    return tuple(facilities)
