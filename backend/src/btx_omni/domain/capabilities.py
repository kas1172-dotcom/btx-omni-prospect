from __future__ import annotations

from dataclasses import dataclass

from btx_omni.core.provenance import Provenance


@dataclass(frozen=True)
class Capability:
    id: str
    name: str
    business_units: tuple[str, ...]
    description: str | None = None
    processes: tuple[str, ...] = ()
    certifications: tuple[str, ...] = ()
    provenance: Provenance | None = None
