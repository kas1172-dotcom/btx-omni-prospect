"""Strict loader for supplied research inputs; it never invents public facts."""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from btx_omni.core.classification import Classification
from btx_omni.core.provenance import Provenance
from btx_omni.domain.accounts import (
    AccountFacility,
    AccountRelationship,
    CanonicalAccount,
    PublicCompanyIdentity,
    PublicContactResearch,
    PublicIdentityField,
    PublicIdentityVerificationState,
    PublicRelationshipEvidence,
    PublicRelationshipState,
    ResearchProvenance,
)
from btx_omni.domain.common import DataMode, EvidenceState

RESEARCH_DIR = Path(__file__).resolve().parents[5] / "docs" / "research"
ACCOUNT_FILE = RESEARCH_DIR / "btx_researched_account_universe.json"
CONTACT_FILE = RESEARCH_DIR / "btx_researched_contacts.json"
MANIFEST_FILE = RESEARCH_DIR / "btx_research_integration_manifest.json"
FACILITY_FILE = RESEARCH_DIR / "btx_public_facility_feed_enrichment.json"
USASPENDING_RECIPIENT_FILE = RESEARCH_DIR / "btx_usaspending_recipient_identities.json"


@dataclass(frozen=True)
class ResearchAccount:
    research_account_id: str
    display_name: str
    official_domain: str | None
    industries: tuple[str, ...]
    relationship: PublicRelationshipEvidence
    prospect_priority: str
    prospect_rationale: str
    source_ids: tuple[str, ...]
    source_urls: tuple[str, ...]
    aliases: tuple[str, ...]
    watch_profile: dict[str, object]
    contacts: tuple[PublicContactResearch, ...]


@dataclass(frozen=True)
class FacilityFeedEnrichment:
    research_account_id: str
    headquarters: dict[str, object]
    facilities: tuple[dict[str, object], ...]
    newsroom_url: str | None
    investor_relations_url: str | None
    feed_urls: tuple[str, ...]
    source_ids: tuple[str, ...]
    last_verified_at: str | None


@dataclass(frozen=True)
class UsaSpendingRecipientIdentity:
    research_account_id: str
    recipient_legal_name: str
    source_url: str
    source_type: str
    verified_at: str


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_research_accounts() -> tuple[ResearchAccount, ...]:
    accounts_document, contacts_document, manifest = _read(ACCOUNT_FILE), _read(CONTACT_FILE), _read(MANIFEST_FILE)
    if accounts_document.get("schema_version") != "2.0" or contacts_document.get("schema_version") != "2.0" or manifest.get("join_key") != "research_account_id":
        raise ValueError("research input schema or join key is not supported")
    raw_accounts = accounts_document.get("accounts", [])
    if not isinstance(raw_accounts, list):
        raise TypeError("research accounts must be an array")
    ids = [item.get("research_account_id") for item in raw_accounts if isinstance(item, dict)]
    if len(ids) != len(set(ids)) or any(not item for item in ids):
        raise ValueError("research_account_id values must be unique and present")
    sources = accounts_document.get("sources", {})
    contacts_by_account: dict[str, list[PublicContactResearch]] = {item: [] for item in ids}
    for collection, contact_type in ((contacts_document.get("named_public_contacts", []), "NAMED_PUBLIC_CONTACT"), (contacts_document.get("public_contact_channels", []), "PUBLIC_CONTACT_CHANNEL")):
        for raw in collection:
            account_id = raw.get("research_account_id")
            if account_id not in contacts_by_account:
                raise ValueError(f"contact references unknown research account: {account_id}")
            source_ids = tuple(raw.get("source_ids", ()))
            source_urls = tuple(sources[source_id]["url"] for source_id in source_ids if source_id in sources)
            source_url = raw.get("source_url") or (source_urls[0] if source_urls else None)
            if source_url and "linkedin.com" in source_url.casefold():
                continue
            contacts_by_account[account_id].append(PublicContactResearch(contact_type, raw.get("role_family", ""), raw.get("verification_state", "UNVERIFIED"), raw.get("source_type"), source_url, ResearchProvenance(source_ids, source_urls, raw.get("verification_state", "UNVERIFIED"), research_only=True), raw.get("name") or raw.get("channel_name"), raw.get("title") or raw.get("title_or_function"), raw.get("division"), raw.get("location"), raw.get("public_email"), raw.get("public_phone")))
    result: list[ResearchAccount] = []
    for raw in raw_accounts:
        source_ids = tuple(raw.get("source_ids", ()))
        source_urls = tuple(raw.get("source_urls", ()))
        relationship = PublicRelationshipEvidence(
            PublicRelationshipState.NO_RELATIONSHIP_EVIDENCE,
            "NONE",
            "BTX commercial relationship is unavailable without an approved connected BTX source.",
            True,
            ResearchProvenance(source_ids, source_urls, raw["public_identity_state"], research_only=True),
        )
        result.append(ResearchAccount(raw["research_account_id"], raw["display_name"], raw.get("official_domain"), tuple(raw["industries"]), relationship, raw["prospect_priority"], raw["prospect_rationale"], source_ids, source_urls, tuple(raw.get("watch_profile", {}).get("aliases", ())), raw.get("watch_profile", {}), tuple(contacts_by_account[raw["research_account_id"]])))
    return tuple(result)


def build_researched_canonical_accounts() -> tuple[tuple[CanonicalAccount, ...], dict[str, str], tuple[ResearchAccount, ...]]:
    """Build canonical records directly from research, without synthetic placeholders."""
    researched = load_research_accounts()
    verified_at = datetime(2026, 8, 16, tzinfo=UTC)
    accounts: list[CanonicalAccount] = []
    for item in researched:
        source_id = item.source_ids[0] if item.source_ids else item.research_account_id
        source_url = item.source_urls[0] if item.source_urls else None
        provenance = Provenance("research-input", source_id, source_url, verified_at, verified_at, Classification.PUBLIC, EvidenceState.CONFIRMED, DataMode.CONNECTED, False)

        def field(value: str, item_provenance: Provenance = provenance) -> PublicIdentityField:
            return PublicIdentityField(value, PublicIdentityVerificationState.VERIFIED_OFFICIAL_PUBLISHER, item_provenance, verified_at)

        identity = PublicCompanyIdentity(
            PublicIdentityVerificationState.VERIFIED_OFFICIAL_PUBLISHER,
            legal_name=field(item.display_name), display_name=field(item.display_name),
            aliases=tuple(field(value) for value in item.aliases),
            official_domain=field(item.official_domain) if item.official_domain else None,
        )
        accounts.append(CanonicalAccount(
            item.research_account_id, item.display_name, AccountRelationship.PUBLIC_MARKET, item.official_domain,
            item.industries, (), None, ("procurement", "supply_chain", "supplier_management", "engineering", "manufacturing", "operations"),
            provenance, "RESEARCHED_PUBLIC", identity, item.research_account_id, item.relationship,
            item.prospect_priority, item.prospect_rationale, item.contacts,
        ))
    return tuple(accounts), {item.research_account_id: item.research_account_id for item in researched}, researched


def load_facility_feed_enrichment() -> dict[str, FacilityFeedEnrichment]:
    document = _read(FACILITY_FILE)
    if document.get("schema_version") != "1.0" or not isinstance(document.get("accounts"), list):
        raise ValueError("facility/feed enrichment schema is not supported")
    result: dict[str, FacilityFeedEnrichment] = {}
    for raw in document["accounts"]:
        account_id = raw.get("research_account_id")
        if not account_id or account_id in result:
            raise ValueError("facility/feed enrichment research_account_id must be unique and present")
        headquarters = raw.get("headquarters") or {}
        facilities = tuple(raw.get("facilities") or ())
        facility_keys = [(item.get("facility_id"), item.get("latitude"), item.get("longitude")) for item in facilities]
        if len(facility_keys) != len(set(facility_keys)):
            raise ValueError(f"duplicate facilities for {account_id}")
        for location in (headquarters, *facilities):
            latitude, longitude = location.get("latitude"), location.get("longitude")
            if (latitude is None) != (longitude is None) or (latitude is not None and not (-90 <= latitude <= 90 and -180 <= longitude <= 180)):
                raise ValueError(f"invalid coordinates for {account_id}")
        result[account_id] = FacilityFeedEnrichment(account_id, headquarters, facilities, raw.get("official_newsroom_url"), raw.get("investor_relations_url"), tuple(raw.get("official_feed_urls") or ()), tuple(raw.get("source_ids") or ()), raw.get("last_verified_at"))
    return result


def load_usaspending_recipient_identities() -> dict[str, tuple[UsaSpendingRecipientIdentity, ...]]:
    """Load only public, source-backed legal recipient mappings for USAspending."""
    document = _read(USASPENDING_RECIPIENT_FILE)
    if document.get("schema_version") != "1.0" or not isinstance(document.get("mappings"), list):
        raise ValueError("USAspending recipient identity schema is not supported")
    known_ids = {account.research_account_id for account in load_research_accounts()}
    result: dict[str, list[UsaSpendingRecipientIdentity]] = {}
    seen_names: dict[str, str] = {}
    for raw in document["mappings"]:
        account_id = raw.get("research_account_id")
        name, source_url, source_type, verified_at = (raw.get("recipient_legal_name"), raw.get("source_url"), raw.get("source_type"), raw.get("verified_at"))
        if account_id not in known_ids or not all(isinstance(item, str) and item for item in (name, source_url, source_type, verified_at)) or not source_url.startswith("https://"):
            raise ValueError("USAspending recipient mapping is incomplete or has an unknown account")
        normalized = "".join(char for char in name.casefold() if char.isalnum())
        if normalized in seen_names and seen_names[normalized] != account_id:
            raise ValueError("USAspending recipient legal name maps to multiple accounts")
        seen_names[normalized] = account_id
        result.setdefault(account_id, []).append(UsaSpendingRecipientIdentity(account_id, name, source_url, source_type, verified_at))
    return {account_id: tuple(items) for account_id, items in result.items()}


def apply_facility_feed_enrichment(accounts: tuple[CanonicalAccount, ...], mappings: dict[str, str]) -> tuple[tuple[CanonicalAccount, ...], tuple[AccountFacility, ...]]:
    enrichment = load_facility_feed_enrichment()
    by_research_id = {account.research_account_id: account for account in accounts if account.research_account_id}
    updated: dict[str, CanonicalAccount] = {}
    public_facilities: list[AccountFacility] = []
    for research_id, account_id in mappings.items():
        account = by_research_id[research_id]
        item = enrichment.get(research_id)
        if item is None:
            continue
        verified_at = datetime.fromisoformat(item.last_verified_at).replace(tzinfo=UTC) if item.last_verified_at else datetime(2026, 8, 16, tzinfo=UTC)
        source_url = item.headquarters.get("source_url") or None
        source_ids = item.source_ids or ((item.headquarters.get("provenance") or {}).get("source_id"),)
        provenance = ResearchProvenance(tuple(value for value in source_ids if value), (source_url,) if source_url else (), str(item.headquarters.get("verification_state", "MISSING_LOCATION")), verified_at)
        public_provenance = Provenance("research-facility-feed", provenance.source_ids[0] if provenance.source_ids else research_id, source_url, verified_at, verified_at, Classification.PUBLIC, EvidenceState.CONFIRMED, DataMode.CONNECTED, False)
        def field(value: str, field_provenance: Provenance = public_provenance, field_verified_at: datetime = verified_at) -> PublicIdentityField:
            return PublicIdentityField(value, PublicIdentityVerificationState.VERIFIED_OFFICIAL_PUBLISHER, field_provenance, field_verified_at)
        identity = account.public_identity
        if identity:
            updated[account_id] = replace(account, public_identity=replace(identity, newsroom_url=field(item.newsroom_url) if item.newsroom_url else None, investor_relations_url=field(item.investor_relations_url) if item.investor_relations_url else None, official_feed_urls=tuple(field(url) for url in item.feed_urls)))
        headquarters = item.headquarters
        if headquarters.get("verification_state") == "VERIFIED_PUBLIC_HQ" and headquarters.get("latitude") is not None:
            public_facilities.append(AccountFacility(f"public-hq-{account_id}", account_id, f"{account.legal_name} headquarters", str(headquarters["city"]), str(headquarters["state_region"]), Decimal(str(headquarters["latitude"])), Decimal(str(headquarters["longitude"])), str(headquarters["country"]), "headquarters", "VERIFIED_PUBLIC_HQ", source_url, headquarters.get("source_type"), verified_at, provenance))
        for facility in item.facilities:
            if facility.get("verification_state") == "VERIFIED_PUBLIC_FACILITY" and facility.get("latitude") is not None:
                public_facilities.append(AccountFacility(str(facility["facility_id"]), account_id, str(facility["facility_name"]), str(facility["city"]), str(facility["state_region"]), Decimal(str(facility["latitude"])), Decimal(str(facility["longitude"])), str(facility["country"]), str(facility.get("facility_type") or "facility"), "VERIFIED_PUBLIC_FACILITY", facility.get("source_url"), facility.get("source_type"), verified_at, provenance))
    return tuple(updated.get(account.id, account) for account in accounts), tuple(public_facilities)
