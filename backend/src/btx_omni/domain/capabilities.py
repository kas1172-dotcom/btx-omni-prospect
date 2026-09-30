from __future__ import annotations

from dataclasses import dataclass

from btx_omni.core.provenance import Provenance


@dataclass(frozen=True)
class CapabilityProcessFamily:
    process: str
    envelope_directional: str | None = None
    materials_supported: tuple[str, ...] = ()
    tolerance_capability: str | None = None
    certifications_applicable: tuple[str, ...] = ()
    specialty_note: str | None = None


@dataclass(frozen=True)
class Capability:
    id: str
    name: str
    business_units: tuple[str, ...]
    description: str | None = None
    processes: tuple[str, ...] = ()
    certifications: tuple[str, ...] = ()
    provenance: Provenance | None = None
    volume_profile: tuple[str, ...] = ()
    process_families: tuple[CapabilityProcessFamily, ...] = ()
    industries_served: tuple[str, ...] = ()
    materials_specialty: str | None = None
    unique_capabilities: tuple[str, ...] = ()
    geography_advantage: str | None = None
