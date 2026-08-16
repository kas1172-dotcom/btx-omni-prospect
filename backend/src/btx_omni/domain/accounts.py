from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import DataMode


class AccountRelationship(StrEnum):
    CURRENT_CUSTOMER = "CURRENT_CUSTOMER"
    FORMER_CUSTOMER = "FORMER_CUSTOMER"
    PROSPECT = "PROSPECT"
    TARGET = "TARGET"


class PublicIdentityVerificationState(StrEnum):
    VERIFIED_AUTHORITATIVE = "VERIFIED_AUTHORITATIVE"
    VERIFIED_OFFICIAL_PUBLISHER = "VERIFIED_OFFICIAL_PUBLISHER"
    INFERRED = "INFERRED"
    AMBIGUOUS = "AMBIGUOUS"
    UNVERIFIED = "UNVERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class PublicIdentityField:
    value: str
    verification_state: PublicIdentityVerificationState
    provenance: Provenance
    last_verified_at: datetime
    source_native_identifier: tuple[str, str] | None = None

    def __post_init__(self) -> None:
        if self.verification_state in {
            PublicIdentityVerificationState.VERIFIED_AUTHORITATIVE,
            PublicIdentityVerificationState.VERIFIED_OFFICIAL_PUBLISHER,
        } and (self.provenance.data_mode is not DataMode.CONNECTED or self.provenance.synthetic):
            raise ValueError("verified public identity requires non-synthetic connected provenance")


@dataclass(frozen=True)
class PublicCompanyIdentity:
    verification_state: PublicIdentityVerificationState
    legal_name: PublicIdentityField | None = None
    display_name: PublicIdentityField | None = None
    aliases: tuple[PublicIdentityField, ...] = ()
    former_names: tuple[PublicIdentityField, ...] = ()
    subsidiaries: tuple[PublicIdentityField, ...] = ()
    official_domain: PublicIdentityField | None = None
    official_website: PublicIdentityField | None = None
    newsroom_url: PublicIdentityField | None = None
    investor_relations_url: PublicIdentityField | None = None
    sec_cik: PublicIdentityField | None = None
    ticker: PublicIdentityField | None = None
    exchange: PublicIdentityField | None = None
    source_native_identifiers: tuple[PublicIdentityField, ...] = ()


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
    public_identity: PublicCompanyIdentity | None = None


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
