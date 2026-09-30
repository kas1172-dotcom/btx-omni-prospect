from __future__ import annotations

from datetime import date
from decimal import Decimal

from btx_omni.core.classification import Classification
from btx_omni.domain.btx import (
    BtxBusinessUnit, BtxFacility, CertifiedProcess, FacilityCapacity,
    FacilityCertification, WorkCenterCapacity,
)
from btx_omni.domain.common import DataMode
from btx_omni.providers.research._catalog_support import document, source_provenance

FIELD_ALIASES = {
    "business_units": {"display_name": "name"},
    "btx_facilities": {},
}
DROPPED_FIELDS = {
    "business_units": {
        "source_ids": "Validated against catalog sources; individual source IDs are not model fields.",
        "joined_platform_at": "Deferred; revisit when a consumer exists.",
        "primary_geography": "Deferred; revisit when a consumer exists.",
        "specialty": "Deferred; revisit when a consumer exists.",
        "facilities_count": "Public footprint, not available production capacity; deferred.",
        "formed_from": "Deferred; revisit when a consumer exists.",
        "founder": "Deferred; revisit when a consumer exists.",
        "known_case_studies": "Deferred; revisit when a consumer exists.",
        "known_customer_context": "Deferred; revisit when a consumer exists.",
        "known_defense_context": "Deferred; revisit when a consumer exists.",
        "known_medical_products": "Deferred; revisit when a consumer exists.",
        "notable_leadership": "Deferred; revisit when a consumer exists.",
        "tuck_in_acquisitions": "Deferred; revisit when a consumer exists.",
        "workbook_sha256": "Source-provenance bookkeeping, not a BU attribute.",
        "sheet": "Source-provenance bookkeeping, not a BU attribute.",
        "row_number": "Source-provenance bookkeeping, not a BU attribute.",
    },
    "btx_facilities": {
        "workbook_sha256": "Source-provenance bookkeeping, not a facility attribute.",
        "sheet": "Source-provenance bookkeeping, not a facility attribute.",
        "row_number": "Source-provenance bookkeeping, not a facility attribute.",
    },
}


def load_btx_business_units() -> tuple[BtxBusinessUnit, ...]:
    payload = document("btx_company_profile.json")
    source_ids = set(payload["sources"])
    units = []
    for row in payload["business_units"]:
        if not set(row["source_ids"]) <= source_ids:
            raise ValueError(f"business unit {row['id']} has unknown source")
        if any(key in row for key in ("data_mode", "synthetic", "source")) and (
            row.get("data_mode") != "SAMPLE" or row.get("synthetic") is not True or not row.get("source")
        ):
            raise ValueError(f"business unit {row['id']} authored capabilities require SAMPLE/synthetic/source labeling")
        units.append(BtxBusinessUnit(
            row["id"], row["display_name"], row.get("website"), tuple(row.get("processes", ())),
            tuple(row.get("certifications", ())), source_provenance(row, classification=Classification.PUBLIC),
            capacity_signals=tuple(sorted((row.get("capacity_signals") or {}).items())),
            legal_name=row.get("legal_name"), employees=row.get("employees"),
            footprint_sqft=row.get("footprint_sqft"), founded=row.get("founded"),
            industries_served=tuple(row.get("industries_served") or ()),
            known_products=tuple(row.get("known_products") or ()),
            data_mode=DataMode(row["data_mode"]) if row.get("data_mode") else None,
            synthetic=row.get("synthetic"), source=row.get("source"),
        ))
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
        has_operations = any(key in row for key in ("certifications", "certified_processes", "capacity"))
        if has_operations and (
            row.get("data_mode") != "SAMPLE" or row.get("synthetic") is not True or not row.get("source")
        ):
            raise ValueError(f"BTX facility {facility_id} operational fields require SAMPLE/synthetic/source labeling")
        def sample_labels(item: dict, label: str) -> dict:
            if item.get("data_mode") != "SAMPLE" or item.get("synthetic") is not True or not item.get("source"):
                raise ValueError(f"BTX facility {facility_id} {label} requires SAMPLE/synthetic/source labeling")
            return {"data_mode": DataMode.SAMPLE, "synthetic": True, "source": str(item["source"])}

        certifications = tuple(FacilityCertification(
            name=cert["name"], scope=cert["scope"], certifying_body=cert.get("certifying_body"),
            certificate_id=cert.get("certificate_id"),
            issued_on=date.fromisoformat(cert["issued_on"]) if cert.get("issued_on") else None,
            expires_on=date.fromisoformat(cert["expires_on"]) if cert.get("expires_on") else None,
            renewal_lead_days=cert.get("renewal_lead_days"),
            **sample_labels(cert, f"certification {cert['name']!r}"),
        ) for cert in row.get("certifications") or ())
        certification_names = {cert.name for cert in certifications}
        processes = tuple(CertifiedProcess(
            process=process["process"], certification_required=process.get("certification_required"),
            tolerance_capability=process.get("tolerance_capability"),
            materials_supported=tuple(process.get("materials_supported") or ()),
            max_part_envelope=process.get("max_part_envelope"),
            **sample_labels(process, f"process {process['process']!r}"),
        ) for process in row.get("certified_processes") or ())
        for process in processes:
            if process.certification_required and process.certification_required not in certification_names:
                raise ValueError(f"BTX facility {facility_id} process {process.process!r} requires absent certification {process.certification_required!r}")
        capacity_row = row.get("capacity")
        capacity = None
        if capacity_row is not None:
            work_centers = []
            for center in capacity_row["work_centers"]:
                label = f"BTX facility {facility_id} work center {center['work_center_id']}"
                nominal = center["machine_count"] * center["shifts_per_day"] * center["hours_per_shift"] * center["operational_days_per_week"]
                if center["nominal_hours_per_week"] != nominal:
                    raise ValueError(f"{label} nominal_hours_per_week does not equal machine_count * shifts_per_day * hours_per_shift * operational_days_per_week")
                if center["available_hours_next_90d"] > nominal * 90 / 7:
                    raise ValueError(f"{label} available_hours_next_90d exceeds 90-day nominal capacity")
                if not 0.0 <= center["utilisation_pct"] <= 1.0:
                    raise ValueError(f"{label} utilisation_pct must be between 0 and 1")
                if center["available_hours_next_90d"] != nominal * 13 - center["committed_hours_next_90d"]:
                    raise ValueError(f"{label} available_hours_next_90d must equal 13-week nominal hours minus committed hours")
                work_centers.append(WorkCenterCapacity(
                    **{key: value for key, value in center.items() if key not in ("data_mode", "synthetic", "source")},
                    **sample_labels(center, f"work center {center['work_center_id']!r}"),
                ))
            capacity = FacilityCapacity(date.fromisoformat(capacity_row["as_of"]), tuple(work_centers))
        facilities.append(BtxFacility(
            facility_id, business_unit_id, str(row["name"]), row.get("city"), row.get("region"), row.get("country"),
            Decimal(str(latitude)) if latitude is not None else None, Decimal(str(longitude)) if longitude is not None else None,
            str(row.get("verification_state", "MISSING_LOCATION")), source_url, row.get("source_type"),
            source_provenance({"id": facility_id, "source_url": source_url}, classification=Classification.PUBLIC),
            source_ids=tuple(row.get("source_ids") or ()),
            certifications=certifications, certified_processes=processes, capacity=capacity,
            data_mode=DataMode(row["data_mode"]) if row.get("data_mode") else None,
            synthetic=row.get("synthetic"), source=row.get("source"),
        ))
    return tuple(facilities)
