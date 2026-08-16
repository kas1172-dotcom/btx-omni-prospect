from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    id: str
    name: str
    business_units: tuple[str, ...]
    description: str | None = None
