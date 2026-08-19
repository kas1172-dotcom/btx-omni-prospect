"""BTX company reference records loaded from the public company profile."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from btx_omni.core.provenance import Provenance


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


@dataclass(frozen=True)
class BtxBusinessUnit:
    id: str
    name: str
    website: str | None
    processes: tuple[str, ...]
    certifications: tuple[str, ...]
    provenance: Provenance
