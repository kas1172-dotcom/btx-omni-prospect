from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from btx_omni.core.provenance import Provenance


class AccountRelationship(StrEnum):
    CURRENT_CUSTOMER = "CURRENT_CUSTOMER"
    FORMER_CUSTOMER = "FORMER_CUSTOMER"
    PROSPECT = "PROSPECT"
    TARGET = "TARGET"


@dataclass(frozen=True)
class CanonicalAccount:
    id: str
    legal_name: str
    relationship: AccountRelationship
    domain: str | None
    industries: tuple[str, ...]
    business_units: tuple[str, ...] = ()
    parent_account_id: str | None = None
    contact_role_families: tuple[str, ...] = ()
    provenance: Provenance | None = None
    public_research_state: str = "ELIGIBLE"


@dataclass(frozen=True)
class AccountFacility:
    id: str
    account_id: str
    name: str
    city: str
    region: str
    latitude: Decimal
    longitude: Decimal
    country: str = "US"


@dataclass(frozen=True)
class BtxFacility:
    id: str
    business_unit: str
    name: str
    city: str
    region: str
    latitude: Decimal
    longitude: Decimal
    capability_tags: tuple[str, ...] = ()
