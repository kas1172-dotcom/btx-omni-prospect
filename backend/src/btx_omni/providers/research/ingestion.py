"""Strict loader for supplied research inputs; it never invents public facts."""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from btx_omni.core.classification import Classification
from btx_omni.core.provenance import Provenance
from btx_omni.domain.accounts import (
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
            contacts_by_account[account_id].append(PublicContactResearch(contact_type, raw.get("role_family", ""), raw.get("verification_state", "UNVERIFIED"), raw.get("source_type"), raw.get("source_url") or (source_urls[0] if source_urls else None), ResearchProvenance(source_ids, source_urls, raw.get("verification_state", "UNVERIFIED"), research_only=True), raw.get("name") or raw.get("channel_name"), raw.get("title") or raw.get("title_or_function"), raw.get("division"), raw.get("location"), raw.get("public_email"), raw.get("public_phone")))
    result: list[ResearchAccount] = []
    for raw in raw_accounts:
        source_ids = tuple(raw.get("source_ids", ()))
        source_urls = tuple(raw.get("source_urls", ()))
        relationship = PublicRelationshipEvidence(PublicRelationshipState(raw["relationship_state"]), raw["relationship_confidence"], raw["relationship_basis"], bool(raw["replaceable_by_internal"]), ResearchProvenance(source_ids, source_urls, raw["public_identity_state"], research_only=True))
        result.append(ResearchAccount(raw["research_account_id"], raw["display_name"], raw.get("official_domain"), tuple(raw["industries"]), relationship, raw["prospect_priority"], raw["prospect_rationale"], source_ids, source_urls, tuple(raw.get("watch_profile", {}).get("aliases", ())), raw.get("watch_profile", {}), tuple(contacts_by_account[raw["research_account_id"]])))
    return tuple(result)


def apply_research_overlay(accounts: tuple[CanonicalAccount, ...]) -> tuple[tuple[CanonicalAccount, ...], dict[str, str], tuple[ResearchAccount, ...]]:
    """Maps supplied identities only onto lightweight synthetic targets, in input order."""
    researched = load_research_accounts()
    available: dict[str, list[CanonicalAccount]] = {}
    for account in accounts:
        if account.legal_name.endswith("Market Target " + account.id[-3:]):
            available.setdefault(account.industries[0], []).append(account)
    mappings: dict[str, str] = {}
    replacements: dict[str, CanonicalAccount] = {}
    verified_at = datetime(2026, 8, 16, tzinfo=UTC)
    for item in researched:
        industry = next((value for value in item.industries if available.get(value)), None)
        if industry is None:
            continue
        placeholder = available[industry].pop(0)
        source_id = item.source_ids[0] if item.source_ids else item.research_account_id
        source_url = item.source_urls[0] if item.source_urls else None
        provenance = Provenance("research-input", source_id, source_url, verified_at, verified_at, Classification.PUBLIC, EvidenceState.CONFIRMED, DataMode.CONNECTED, False)
        def field(value: str, item_provenance: Provenance = provenance) -> PublicIdentityField:
            return PublicIdentityField(value, PublicIdentityVerificationState.VERIFIED_OFFICIAL_PUBLISHER, item_provenance, verified_at)
        identity = PublicCompanyIdentity(PublicIdentityVerificationState.VERIFIED_OFFICIAL_PUBLISHER, legal_name=field(item.display_name), display_name=field(item.display_name), aliases=tuple(field(value) for value in item.aliases), official_domain=field(item.official_domain) if item.official_domain else None)
        replacements[placeholder.id] = replace(placeholder, legal_name=item.display_name, domain=item.official_domain, public_identity=identity, research_account_id=item.research_account_id, public_relationship=item.relationship, prospect_research_priority=item.prospect_priority, prospect_rationale=item.prospect_rationale, public_contacts=item.contacts, public_research_state="RESEARCHED_PUBLIC")
        mappings[item.research_account_id] = placeholder.id
    return tuple(replacements.get(item.id, item) for item in accounts), mappings, researched
