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


class PublicRelationshipState(StrEnum):
    BTX_CONFIRMED = "BTX_CONFIRMED"
    PUBLICLY_EVIDENCED_RELATIONSHIP = "PUBLICLY_EVIDENCED_RELATIONSHIP"
    PUBLIC_INTERACTION_INFERENCE = "PUBLIC_INTERACTION_INFERENCE"
    NO_RELATIONSHIP_EVIDENCE = "NO_RELATIONSHIP_EVIDENCE"


@dataclass(frozen=True)
class ResearchProvenance:
    source_ids: tuple[str, ...]
    source_urls: tuple[str, ...]
    verification_state: str
    last_verified_at: datetime | None = None
    research_only: bool = True


@dataclass(frozen=True)
class PublicRelationshipEvidence:
    state: PublicRelationshipState
    confidence: str
    basis: str
    replaceable_by_internal: bool
    provenance: ResearchProvenance


@dataclass(frozen=True)
class PublicContactResearch:
    contact_type: str
    role_family: str
    verification_state: str
    source_type: str | None
    source_url: str | None
    provenance: ResearchProvenance
    name: str | None = None
    title_or_function: str | None = None
    division: str | None = None
    location: str | None = None
    public_email: str | None = None
    public_phone: str | None = None


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
    official_feed_urls: tuple[PublicIdentityField, ...] = ()
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
    research_account_id: str | None = None
    public_relationship: PublicRelationshipEvidence | None = None
    prospect_research_priority: str | None = None
    prospect_rationale: str | None = None
    public_contacts: tuple[PublicContactResearch, ...] = ()


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
    facility_type: str = "SAMPLE_INTERNAL_LOCATION"
    verification_state: str = "SAMPLE_INTERNAL_LOCATION"
    source_url: str | None = None
    source_type: str | None = None
    last_verified_at: datetime | None = None
    provenance: ResearchProvenance | None = None


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
