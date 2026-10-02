"""BTX company reference records loaded from the public company profile."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import DataMode


@dataclass(frozen=True)
class FacilityCertification:
    name: str
    scope: str
    certifying_body: str | None
    certificate_id: str | None
    issued_on: date | None
    expires_on: date | None
    renewal_lead_days: int | None
    data_mode: DataMode | None = None
    synthetic: bool | None = None
    source: str | None = None


@dataclass(frozen=True)
class CertifiedProcess:
    process: str
    certification_required: str | None
    tolerance_capability: str | None
    materials_supported: tuple[str, ...]
    max_part_envelope: str | None
    data_mode: DataMode | None = None
    synthetic: bool | None = None
    source: str | None = None


@dataclass(frozen=True)
class WorkCenterCapacity:
    work_center_id: str
    process: str
    machine_count: int
    shifts_per_day: int
    hours_per_shift: int
    operational_days_per_week: int
    nominal_hours_per_week: int
    committed_hours_next_90d: int
    available_hours_next_90d: int
    utilisation_pct: float
    data_mode: DataMode | None = None
    synthetic: bool | None = None
    source: str | None = None


@dataclass(frozen=True)
class FacilityCapacity:
    as_of: date
    work_centers: tuple[WorkCenterCapacity, ...]


@dataclass(frozen=True)
class BtxFacility:
    id: str
    business_unit_id: str | None
    name: str
    city: str | None
    region: str | None
    country: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    verification_state: str
    source_url: str | None
    source_type: str | None
    provenance: Provenance
    source_ids: tuple[str, ...] = ()
    certifications: tuple[FacilityCertification, ...] = ()
    certified_processes: tuple[CertifiedProcess, ...] = ()
    capacity: FacilityCapacity | None = None
    # These label the authored operational overlay; provenance above labels public location identity.
    data_mode: DataMode | None = None
    synthetic: bool | None = None
    source: str | None = None


@dataclass(frozen=True)
class BtxBusinessUnit:
    id: str
    name: str
    website: str | None
    processes: tuple[str, ...]
    certifications: tuple[str, ...]
    provenance: Provenance
    capacity_signals: tuple[tuple[str, str | bool], ...] = ()
    legal_name: str | None = None
    employees: int | None = None
    footprint_sqft: int | None = None
    founded: int | None = None
    industries_served: tuple[str, ...] = ()
    known_products: tuple[str, ...] = ()
    # These label any authored additions to a public BU capability list.
    data_mode: DataMode | None = None
    synthetic: bool | None = None
    source: str | None = None
