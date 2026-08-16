from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BusinessUnit:
    """Canonical BTX commercial business-unit reference."""

    id: str
    name: str
    active: bool = True
