"""Boeing SAMPLE scope-to-facility classifications; no scorer thresholds change."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from btx_omni.modules.classification import FACILITY_CLASSIFIER_RULE_VERSION as VERSION
from btx_omni.modules.classification.contract import (
    deterministic_bin,
    deterministic_raw,
)

SOURCE_NOTE = "Derived from authored SAMPLE scope and synthetic facility operations; not verified BTX evidence."


def _missing(opportunity: dict, facility: object, field: str) -> tuple[str, ...]:
    if facility is None or opportunity.get("delivery_facility_id") != getattr(facility, "id", None):
        return ("delivery_facility_id",)
    scope = opportunity.get("scope_requirements")
    if not isinstance(scope, dict) or not scope.get(field):
        return (f"scope_requirements.{field}",)
    return ()


def _evidence(opportunity: dict, facility: object, *ids: str) -> tuple[str, ...]:
    return (f"{opportunity['opportunity_id']}:scope_requirements", facility.id, *ids)


def _bin(opportunity: dict, facility: object, factor: str, value: str | None,
         missing: tuple[str, ...], as_of: str, *ids: str):
    return replace(deterministic_bin(
        opportunity_id=opportunity["opportunity_id"], path=f"btx_manufacturing_fit.{factor}",
        bin_value=value if not missing else None,
        evidence_ids=_evidence(opportunity, facility, *ids) if not missing else (),
        missing_fields=missing, as_of=as_of, rule_version=VERSION,
    ), note=SOURCE_NOTE)


def _raw(opportunity: dict, facility: object, factor: str, value: dict | None,
         missing: tuple[str, ...], as_of: str, *ids: str):
    return replace(deterministic_raw(
        opportunity_id=opportunity["opportunity_id"], factor=factor,
        raw_input=value if not missing else None,
        evidence_ids=_evidence(opportunity, facility, *ids) if not missing else (),
        missing_fields=missing, as_of=as_of, rule_version=VERSION,
    ), note=SOURCE_NOTE)


def _material_key(value: str) -> str:
    key = value.casefold().strip().replace(" ", "")
    for prefix in ("aluminum", "aluminium"):
        if key.startswith(prefix):
            return key[len(prefix):]
    if key.startswith("titanium"):
        return "ti-" + key[len("titanium"):]
    return key


def _material_family(value: str) -> str:
    key = _material_key(value)
    if key.startswith(("6", "7", "2")) and len(key) >= 4:
        return "aluminum"
    if key.startswith("ti-"):
        return "titanium"
    if key.startswith("inconel"):
        return "nickel"
    if key.startswith(("316", "304", "17-4", "15-5")):
        return "stainless"
    return key.split("-")[0]


def _tolerance(value: str | None) -> Decimal | None:
    match = re.search(r"(?:±|\+/-)\s*(\d+(?:\.\d+)?)", value or "")
    return Decimal(match.group(1)) if match else None


def _cert_key(value: str) -> str:
    return value.split(":", 1)[0].casefold().strip()


def _required_centers(opportunity: dict, facility: object) -> tuple:
    required = set((opportunity.get("scope_requirements") or {}).get("required_processes") or ())
    return tuple(center for center in getattr(getattr(facility, "capacity", None), "work_centers", ())
                 if center.process in required)


def classify_material_match(opportunity: dict, facility: object, *, as_of: str):
    missing = _missing(opportunity, facility, "required_materials")
    if missing:
        return _bin(opportunity, facility, "material_match", None, missing, as_of)
    required = opportunity["scope_requirements"]["required_materials"]
    supported = {_material_key(material) for process in facility.certified_processes for material in process.materials_supported}
    families = {_material_family(material) for process in facility.certified_processes for material in process.materials_supported}
    if not supported:
        return _bin(opportunity, facility, "material_match", None, ("facility.certified_processes.materials_supported",), as_of)
    exact = all(_material_key(material) in supported for material in required)
    analogous = all(_material_key(material) in supported or _material_family(material) in families for material in required)
    value = "ROUTINE" if exact else "EXTENDED_ANALOGOUS" if analogous else "KNOWN_MISMATCH"
    return _bin(opportunity, facility, "material_match", value, (), as_of,
                *(process.process for process in facility.certified_processes))


def _process_coverage(opportunity: dict, facility: object) -> tuple[str | None, tuple[str, ...]]:
    missing = _missing(opportunity, facility, "required_processes")
    if missing:
        return None, missing
    scope = opportunity["scope_requirements"]
    if not scope.get("required_tolerance_band"):
        return None, ("scope_requirements.required_tolerance_band",)
    required_tolerance = _tolerance(scope["required_tolerance_band"])
    if required_tolerance is None:
        return None, ("scope_requirements.required_tolerance_band",)
    processes = {process.process: process for process in facility.certified_processes}
    if any(name not in processes for name in scope["required_processes"]):
        return "KNOWN_MISMATCH", ()
    tolerances = [_tolerance(processes[name].tolerance_capability) for name in scope["required_processes"]]
    if any(value is None for value in tolerances):
        return None, ("facility.certified_processes.tolerance_capability",)
    if all(value <= required_tolerance for value in tolerances):
        return "ROUTINE", ()
    if all(value <= required_tolerance * Decimal("1.25") for value in tolerances):
        return "EDGE_BUT_ANALOGOUS", ()
    return "KNOWN_MISMATCH", ()


def classify_process_tolerance_match(opportunity: dict, facility: object, *, as_of: str):
    value, missing = _process_coverage(opportunity, facility)
    return _bin(opportunity, facility, "process_tolerance_match", value, missing, as_of,
                *(opportunity.get("scope_requirements") or {}).get("required_processes", ()))


def _cert_coverage(opportunity: dict, facility: object) -> tuple[str | None, tuple[str, ...]]:
    missing = _missing(opportunity, facility, "required_certifications")
    if missing:
        return None, missing
    scope = opportunity["scope_requirements"]
    if not scope.get("required_by_date"):
        return None, ("scope_requirements.required_by_date",)
    due = date.fromisoformat(scope["required_by_date"])
    held = {_cert_key(cert.name): cert for cert in facility.certifications}
    required = [_cert_key(name) for name in scope["required_certifications"]]
    if any(name not in held or held[name].expires_on is None or held[name].expires_on < due for name in required):
        return "MAJOR_GAP", ()
    if any(held[name].expires_on <= due + timedelta(days=90) for name in required):
        return "MINOR_GAP", ()
    return "ALL_MET", ()


def classify_certification_compliance_fit(opportunity: dict, facility: object, *, as_of: str):
    value, missing = _cert_coverage(opportunity, facility)
    return _bin(opportunity, facility, "certification_compliance_fit", value, missing, as_of,
                *(cert.name for cert in getattr(facility, "certifications", ())))


def classify_volume_compatibility(opportunity: dict, facility: object, *, as_of: str):
    missing = _missing(opportunity, facility, "expected_volume_next_12m")
    scope = opportunity.get("scope_requirements") or {}
    if not missing and not scope.get("expected_hours_per_unit"):
        missing = ("scope_requirements.expected_hours_per_unit",)
    if not missing and not scope.get("required_processes"):
        missing = ("scope_requirements.required_processes",)
    centers = _required_centers(opportunity, facility)
    if not missing and not centers:
        missing = ("facility.capacity.required_process_work_centers",)
    if missing:
        return _bin(opportunity, facility, "volume_compatibility", None, missing, as_of)
    required_hours = Decimal(str(scope["expected_volume_next_12m"])) * Decimal(str(scope["expected_hours_per_unit"]))
    available_hours = Decimal(sum(center.available_hours_next_90d for center in centers) * 4)
    value = "NORMAL_RANGE" if required_hours <= available_hours * Decimal("0.8") else "WORKABLE_NOT_IDEAL" if required_hours <= available_hours else "POOR_FIT"
    return _bin(opportunity, facility, "volume_compatibility", value, (), as_of,
                *(center.work_center_id for center in centers))


def classify_delivery_capability_match(opportunity: dict, facility: object, *, as_of: str):
    coverage, missing = _process_coverage(opportunity, facility)
    # Funded remedies and promised dates are not in the facility catalog; do not infer them.
    state = "ALL_AVAILABLE" if coverage == "ROUTINE" else "UNAVAILABLE_BY_NEED"
    return _raw(opportunity, facility, "capability_match", {"state": state} if coverage else None,
                missing, as_of, *(opportunity.get("scope_requirements") or {}).get("required_processes", ()))


def classify_delivery_schedule_feasibility(opportunity: dict, facility: object, *, as_of: str):
    missing = _missing(opportunity, facility, "required_hours_next_90d")
    if not missing and not (opportunity.get("scope_requirements") or {}).get("required_processes"):
        missing = ("scope_requirements.required_processes",)
    centers = _required_centers(opportunity, facility)
    if not missing and not centers:
        missing = ("facility.capacity.required_process_work_centers",)
    if missing:
        return _raw(opportunity, facility, "schedule_feasibility", None, missing, as_of)
    return _raw(opportunity, facility, "schedule_feasibility", {
        "net_available_hours": sum(center.available_hours_next_90d for center in centers),
        "required_hours": opportunity["scope_requirements"]["required_hours_next_90d"],
    }, (), as_of, *(center.work_center_id for center in centers))


def classify_delivery_quality_certification(opportunity: dict, facility: object, *, as_of: str):
    coverage, missing = _cert_coverage(opportunity, facility)
    # Validity alone does not prove buyer approval, a scheduled qualification, or a renewal owner/date.
    state = "MANDATORY_UNAVAILABLE_BY_START" if coverage == "MAJOR_GAP" else "UNDATED_PLAN"
    return _raw(opportunity, facility, "quality_certification", {"state": state} if coverage else None,
                missing, as_of, *(cert.name for cert in getattr(facility, "certifications", ())))
