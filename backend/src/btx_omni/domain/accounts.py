from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class AccountRelationship(StrEnum):
    CURRENT_CUSTOMER = "CURRENT_CUSTOMER"
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


@dataclass(frozen=True)
class AccountFacility:
    id: str
    account_id: str
    name: str
    city: str
    region: str
    latitude: Decimal
    longitude: Decimal


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
