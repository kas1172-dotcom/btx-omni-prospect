"""Governed loader for normalized, user-sanitized reference workbooks.

The committed fixture contains only allow-listed reference fields. Original
workbooks and prohibited BTX columns never enter the runtime or repository.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from btx_omni.core.classification import Classification
from btx_omni.core.provenance import Provenance
from btx_omni.domain.accounts import (
    AccountFacility,
    AccountRelationship,
    CanonicalAccount,
    PublicCompanyIdentity,
    PublicIdentityField,
    PublicIdentityVerificationState,
    PublicRelationshipEvidence,
    PublicRelationshipState,
    ResearchProvenance,
)
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.domain.markets import PRIMARY_MARKETS

REFERENCE_FILE = Path(__file__).resolve().parents[5] / "docs" / "research" / "btx_sanitized_reference_data.json"
PRIVATE_REFERENCE_FILE = REFERENCE_FILE.with_name('btx_original_workbook_references.json')
PRIVATE_REFERENCE_SHA256 = 'd0e4a1ca28d5f6ec38edd457b81fe98177d5b9d5396ac582b6bf34e9901e55d7'


def load_private_reference_fields() -> dict:
    """Separate private appendix: never added to public identity or score inputs."""
    raw = PRIVATE_REFERENCE_FILE.read_bytes()
    if len(raw) > 5_000_000 or sha256(raw).hexdigest() != PRIVATE_REFERENCE_SHA256:
        raise ValueError('Private reference data differs from the reviewed runtime input.')
    result = json.loads(raw)
    if result.get('schema_version') != 'BTX_WORKBOOK_REFERENCE_1' or result.get('classification') != 'PRIVATE_USER_PROVIDED_REFERENCE':
        raise ValueError('Private reference schema/classification is not supported.')
    return result


@dataclass(frozen=True)
class ReferenceImport:
    accounts: tuple[CanonicalAccount, ...]
    facilities: tuple[AccountFacility, ...]
    identity_audit: tuple[dict[str, object], ...]
    sources: tuple[dict[str, object], ...]


def _read() -> dict[str, object]:
    document = json.loads(REFERENCE_FILE.read_text(encoding="utf-8"))
    if document.get("schema_version") != "1.0":
        raise ValueError("sanitized reference fixture schema is not supported")
    return document


def load_reference_import() -> ReferenceImport:
    document = _read()
    observed_at = datetime.fromisoformat(str(document["observed_at"])).replace(tzinfo=UTC)
    sources = tuple(document.get("sources", ()))
    source_ids = {str(item["source_id"]) for item in sources}
    accounts: list[CanonicalAccount] = []
    for raw in document.get("accounts", ()):
        industries = tuple(str(value) for value in raw.get("industries", ()))
        if not set(industries) <= PRIMARY_MARKETS:
            raise ValueError(f"reference account has unsupported market: {raw['canonical_account_id']}")
        references = tuple(str(value) for value in raw.get("source_references", ()))
        if not references or any(value.split(":", 1)[0] not in source_ids for value in references):
            raise ValueError("reference account has missing or unknown provenance")
        source_id = references[0]
        provenance = Provenance("sanitized-reference-workbook", source_id, None, observed_at, observed_at, Classification.PUBLIC, EvidenceState.CONFIRMED, DataMode.CONNECTED, False)
        research_provenance = ResearchProvenance(references, (), "SANITIZED_REFERENCE_SOURCE", observed_at)

        def field(value: str, native_kind: str, item_provenance: Provenance = provenance) -> PublicIdentityField:
            return PublicIdentityField(value, PublicIdentityVerificationState.UNVERIFIED, item_provenance, observed_at, (native_kind, value))

        display_name = str(raw["display_name"])
        domain = str(raw["domain"])
        aliases = tuple(str(value) for value in raw.get("aliases", ()) if value and value != display_name)
        identity = PublicCompanyIdentity(
            PublicIdentityVerificationState.UNVERIFIED,
            legal_name=field(display_name, "SANITIZED_REFERENCE_ORGANIZATION_NAME"),
            display_name=field(display_name, "SANITIZED_REFERENCE_ORGANIZATION_NAME"),
            aliases=tuple(field(value, "SANITIZED_REFERENCE_ALIAS") for value in aliases),
            official_domain=field(domain, "SANITIZED_REFERENCE_CORPORATE_DOMAIN"),
            official_website=field(str(raw["website"]), "SANITIZED_REFERENCE_CORPORATE_WEBSITE"),
            source_native_identifiers=tuple(field(value, "SANITIZED_REFERENCE_ROW") for value in references),
        )
        relationship = PublicRelationshipEvidence(
            PublicRelationshipState.NO_RELATIONSHIP_EVIDENCE,
            "NONE",
            "BTX commercial relationship is unavailable from sanitized market-reference sources.",
            True,
            research_provenance,
        )
        top_100 = bool(raw.get("btx_top_100"))
        top_references = tuple(str(value) for value in raw.get("btx_top_100_references", ()))
        if top_100 != bool(top_references):
            raise ValueError("BTX Top 100 membership requires explicit source provenance")
        accounts.append(CanonicalAccount(
            str(raw["canonical_account_id"]), display_name, AccountRelationship.PUBLIC_MARKET, domain,
            industries, (), None, (), provenance, "SANITIZED_REFERENCE", identity, None, relationship,
            None, None, (), tuple(str(value) for value in raw.get("source_segments", ())),
            top_100, ResearchProvenance(top_references, (), "SANITIZED_BTX_TOP_100_POC", observed_at) if top_100 else None,
        ))

    account_ids = {item.id for item in accounts}
    facilities: list[AccountFacility] = []
    for raw in document.get("facilities", ()):
        account_id = str(raw["canonical_account_id"])
        if account_id not in account_ids:
            raise ValueError("reference facility points to unknown account")
        latitude, longitude = Decimal(str(raw["latitude"])), Decimal(str(raw["longitude"]))
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("reference facility has invalid coordinates")
        references = tuple(str(value) for value in raw.get("source_references", ()))
        provenance = ResearchProvenance(references, (), "SANITIZED_REFERENCE_LOCATION", observed_at)
        facilities.append(AccountFacility(
            str(raw["facility_id"]), account_id, str(raw["name"]), str(raw.get("city") or ""),
            str(raw.get("region") or ""), latitude, longitude, str(raw.get("country") or ""),
            str(raw.get("facility_type") or "Reference facility"), "SANITIZED_REFERENCE_LOCATION",
            str(raw.get("website") or "") or None, "SANITIZED_REFERENCE_WORKBOOK", observed_at, provenance,
        ))
    if len({item.id for item in accounts}) != len(accounts) or len({item.id for item in facilities}) != len(facilities):
        raise ValueError("normalized reference IDs must be unique")
    return ReferenceImport(tuple(accounts), tuple(facilities), tuple(document.get("identity_audit", ())), sources)
