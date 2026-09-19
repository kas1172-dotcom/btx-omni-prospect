"""Durable public Prospect Accounts composed into the canonical runtime universe."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import Connection, Engine, delete, insert, select

from btx_omni.core.classification import Classification
from btx_omni.core.provenance import Provenance
from btx_omni.domain.accounts import (
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
from btx_omni.monitor.resolution import AccountWatchProfile, resolve_entity
from btx_omni.persistence.models import durable_public_accounts


@dataclass(frozen=True)
class DurablePublicProspect:
    """A complete canonical Account plus governed durable-origin metadata."""

    account: CanonicalAccount
    identity_key: str
    source_identifiers: tuple[tuple[str, str], ...]
    originating_candidate_id: str | None
    created_at: datetime
    promoted_at: datetime | None = None
    promotion_provenance: Provenance | None = None


def _normal(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _identity_key(name: str, source_identifiers: tuple[tuple[str, str], ...], provenance: Provenance) -> str:
    identifiers = tuple(sorted((kind.casefold(), value.casefold()) for kind, value in source_identifiers if kind and value))
    if identifiers:
        return "identifier:" + "|".join(f"{kind}={value}" for kind, value in identifiers)
    return f"source-name:{provenance.source_system}:{_normal(name)}"


def _account_id(identity_key: str) -> str:
    return f"prospect-{sha256(identity_key.encode()).hexdigest()[:24]}"


def _provenance_payload(value: Provenance) -> dict[str, object]:
    return {
        "source_system": value.source_system,
        "source_record_id": value.source_record_id,
        "source_url": value.source_url,
        "observed_at": value.observed_at.isoformat(),
        "recorded_at": value.recorded_at.isoformat(),
        "classification": value.classification.value,
        "evidence_state": value.evidence_state.value,
        "data_mode": value.data_mode.value,
        "synthetic": value.synthetic,
        "sensitivity_tags": sorted(item.value for item in value.sensitivity_tags),
        "missing_fields": list(value.missing_fields),
    }


def _provenance(value: dict[str, object]) -> Provenance:
    from btx_omni.core.classification import SensitivityTag

    return Provenance(
        str(value["source_system"]), str(value["source_record_id"]), value.get("source_url") if isinstance(value.get("source_url"), str) else None,
        datetime.fromisoformat(str(value["observed_at"])), datetime.fromisoformat(str(value["recorded_at"])),
        Classification(str(value["classification"])), EvidenceState(str(value["evidence_state"])), DataMode(str(value["data_mode"])), bool(value["synthetic"]),
        frozenset(SensitivityTag(str(item)) for item in value.get("sensitivity_tags", [])), tuple(str(item) for item in value.get("missing_fields", [])),
    )


def _field_payload(value: PublicIdentityField | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "value": value.value,
        "verification_state": value.verification_state.value,
        "provenance": _provenance_payload(value.provenance),
        "last_verified_at": value.last_verified_at.isoformat(),
        "source_native_identifier": list(value.source_native_identifier) if value.source_native_identifier else None,
    }


def _field(value: dict[str, object] | None) -> PublicIdentityField | None:
    if value is None:
        return None
    identifier = value.get("source_native_identifier")
    return PublicIdentityField(
        str(value["value"]), PublicIdentityVerificationState(str(value["verification_state"])), _provenance(value["provenance"]),
        datetime.fromisoformat(str(value["last_verified_at"])), tuple(identifier) if isinstance(identifier, list) else None,
    )


def _account_payload(value: CanonicalAccount) -> str:
    identity = value.public_identity
    return json.dumps({
        "id": value.id, "legal_name": value.legal_name, "relationship": value.relationship.value, "domain": value.domain,
        "industries": list(value.industries), "business_units": list(value.business_units), "parent_account_id": value.parent_account_id,
        "contact_role_families": list(value.contact_role_families), "provenance": _provenance_payload(value.provenance) if value.provenance else None,
        "public_research_state": value.public_research_state, "research_account_id": value.research_account_id,
        "prospect_research_priority": value.prospect_research_priority, "prospect_rationale": value.prospect_rationale,
        "secondary_classifications": list(value.secondary_classifications),
        "prospect_fit_evidence": value.prospect_fit_evidence,
        "public_identity": None if identity is None else {
            "verification_state": identity.verification_state.value,
            "legal_name": _field_payload(identity.legal_name), "display_name": _field_payload(identity.display_name),
            "aliases": [_field_payload(item) for item in identity.aliases], "former_names": [_field_payload(item) for item in identity.former_names],
            "subsidiaries": [_field_payload(item) for item in identity.subsidiaries], "official_domain": _field_payload(identity.official_domain),
            "official_website": _field_payload(identity.official_website), "newsroom_url": _field_payload(identity.newsroom_url),
            "investor_relations_url": _field_payload(identity.investor_relations_url), "official_feed_urls": [_field_payload(item) for item in identity.official_feed_urls],
            "sec_cik": _field_payload(identity.sec_cik), "ticker": _field_payload(identity.ticker), "exchange": _field_payload(identity.exchange),
            "source_native_identifiers": [_field_payload(item) for item in identity.source_native_identifiers],
        },
    }, sort_keys=True)


def _account_from_payload(payload: str) -> CanonicalAccount:
    value = json.loads(payload)
    raw_identity = value.get("public_identity")
    identity = None
    if raw_identity:
        identity = PublicCompanyIdentity(
            PublicIdentityVerificationState(raw_identity["verification_state"]), _field(raw_identity["legal_name"]), _field(raw_identity["display_name"]),
            tuple(item for raw in raw_identity["aliases"] if (item := _field(raw))), tuple(item for raw in raw_identity["former_names"] if (item := _field(raw))),
            tuple(item for raw in raw_identity["subsidiaries"] if (item := _field(raw))), _field(raw_identity["official_domain"]), _field(raw_identity["official_website"]),
            _field(raw_identity["newsroom_url"]), _field(raw_identity["investor_relations_url"]), tuple(item for raw in raw_identity["official_feed_urls"] if (item := _field(raw))),
            _field(raw_identity["sec_cik"]), _field(raw_identity["ticker"]), _field(raw_identity["exchange"]),
            tuple(item for raw in raw_identity["source_native_identifiers"] if (item := _field(raw))),
        )
    provenance = _provenance(value["provenance"]) if value.get("provenance") else None
    public_relationship = PublicRelationshipEvidence(
        PublicRelationshipState.NO_RELATIONSHIP_EVIDENCE, "NONE", "No BTX commercial relationship is created by public Prospect account composition.", True,
        ResearchProvenance((provenance.source_record_id,) if provenance else (), (provenance.source_url,) if provenance and provenance.source_url else (), identity.verification_state.value if identity else "UNVERIFIED", research_only=True),
    )
    return CanonicalAccount(
        value["id"], value["legal_name"], AccountRelationship(value["relationship"]), value.get("domain"), tuple(value["industries"]),
        tuple(value["business_units"]), value.get("parent_account_id"), tuple(value["contact_role_families"]), provenance,
        value["public_research_state"], identity, value.get("research_account_id"), public_relationship,
        value.get("prospect_research_priority"), value.get("prospect_rationale"), (), tuple(value["secondary_classifications"]),
        prospect_fit_evidence=value.get('prospect_fit_evidence', {}),
    )


def _timestamp(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class DurablePublicAccountRepository:
    """The sole durable-account read/write boundary; it never creates commercial data."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def accounts(self) -> tuple[DurablePublicProspect, ...]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(durable_public_accounts).order_by(durable_public_accounts.c.id)).mappings()
            return tuple(
                DurablePublicProspect(
                    _account_from_payload(row["account_payload"]), row["identity_key"], tuple(tuple(item) for item in json.loads(row["source_identifiers"])),
                    row["originating_candidate_id"], _timestamp(row["created_at"]), _timestamp(row["promoted_at"]) if row["promoted_at"] else None,
                    _provenance(json.loads(row["promotion_provenance"])) if row["promotion_provenance"] else None,
                ) for row in rows
            )

    def create_public_prospect(
        self, *, legal_name: str, industries: tuple[str, ...], provenance: Provenance, aliases: tuple[str, ...] = (),
        domain: str | None = None, source_identifiers: tuple[tuple[str, str], ...] = (), originating_candidate_id: str | None = None,
        curated_accounts: tuple[CanonicalAccount, ...] = (), created_at: datetime | None = None,
        promoted_at: datetime | None = None, promotion_provenance: Provenance | None = None, connection: Connection | None = None,
    ) -> DurablePublicProspect:
        if not legal_name.strip() or not industries or not set(industries) <= PRIMARY_MARKETS:
            raise ValueError("durable public prospects require an evidence-backed legal name and canonical industry.")
        if provenance.data_mode is not DataMode.CONNECTED or provenance.synthetic:
            raise ValueError("durable public prospects require non-synthetic connected public provenance.")
        identity_key = _identity_key(legal_name, source_identifiers, provenance)
        now = created_at or provenance.recorded_at
        field_state = PublicIdentityVerificationState.VERIFIED_AUTHORITATIVE
        def field(value: str, identifier: tuple[str, str] | None = None) -> PublicIdentityField:
            return PublicIdentityField(value, field_state, provenance, now, identifier)
        identity = PublicCompanyIdentity(
            field_state, field(legal_name), field(legal_name), tuple(field(alias) for alias in aliases),
            official_domain=field(domain) if domain else None, source_native_identifiers=tuple(field(value, (kind, value)) for kind, value in source_identifiers),
        )
        account = CanonicalAccount(
            _account_id(identity_key), legal_name, AccountRelationship.PROSPECT, domain, tuple(sorted(set(industries))), (), None,
            ("procurement", "supply_chain", "supplier_management", "engineering", "manufacturing", "operations"), provenance,
            "DURABLE_PUBLIC_PROSPECT", identity, None, None, None, None, (), (),
        )
        result = DurablePublicProspect(account, identity_key, tuple(sorted(source_identifiers)), originating_candidate_id, now, promoted_at, promotion_provenance)
        profiles = tuple(AccountWatchProfile(item.id, item.legal_name, aliases=tuple(field.value for field in item.public_identity.aliases) if item.public_identity else (), domain=item.domain, source_native_identifiers=tuple(field.source_native_identifier for field in item.public_identity.source_native_identifiers if field.source_native_identifier)) for item in curated_accounts)
        if connection is None:
            existing = self.accounts()
        else:
            rows = connection.execute(select(durable_public_accounts).order_by(durable_public_accounts.c.id)).mappings()
            existing = tuple(DurablePublicProspect(
                _account_from_payload(row["account_payload"]), row["identity_key"], tuple(tuple(item) for item in json.loads(row["source_identifiers"])),
                row["originating_candidate_id"], _timestamp(row["created_at"]), _timestamp(row["promoted_at"]) if row["promoted_at"] else None,
                _provenance(json.loads(row["promotion_provenance"])) if row["promotion_provenance"] else None,
            ) for row in rows)
        existing_by_key = {item.identity_key: item for item in existing}
        if identity_key in existing_by_key:
            matched = existing_by_key[identity_key]
            if matched.account.legal_name == legal_name and matched.source_identifiers == tuple(sorted(source_identifiers)):
                return matched
            raise ValueError("exact canonical identity collision prevents durable prospect creation.")
        profiles += tuple(AccountWatchProfile(item.account.id, item.account.legal_name, aliases=tuple(field.value for field in item.account.public_identity.aliases) if item.account.public_identity else (), domain=item.account.domain, source_native_identifiers=tuple(field.source_native_identifier for field in item.account.public_identity.source_native_identifiers if field.source_native_identifier)) for item in existing)
        resolutions = tuple(
            resolve_entity(mention, profiles, source_identifiers=source_identifiers)
            for mention in (legal_name, *aliases)
        )
        if any(item.state.value in {"RESOLVED", "AMBIGUOUS"} for item in resolutions) or account.id in {item.id for item in curated_accounts}:
            raise ValueError("exact canonical identity collision prevents durable prospect creation.")
        def persist(target: Connection) -> None:
            target.execute(delete(durable_public_accounts).where(durable_public_accounts.c.id == account.id))
            target.execute(insert(durable_public_accounts).values(
                id=account.id, identity_key=identity_key, legal_name=legal_name, domain=domain, industries=json.dumps(account.industries),
                account_payload=_account_payload(account), source_identifiers=json.dumps(source_identifiers), originating_candidate_id=originating_candidate_id,
                created_at=now, promoted_at=promoted_at, promotion_provenance=json.dumps(_provenance_payload(promotion_provenance)) if promotion_provenance else None,
            ))
        if connection is None:
            with self.engine.begin() as target:
                persist(target)
        else:
            persist(connection)
        return result
