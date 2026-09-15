"""Governed technical-decomposition cache and deterministic BTX taxonomy matching."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from btx_omni.ai.contracts import (
    LanguageProvider,
    LanguageProviderError,
    ProviderStatus,
    TechnicalCandidate,
    TechnicalDecompositionRequest,
    TechnicalDecompositionResult,
)
from btx_omni.domain.btx import BtxBusinessUnit
from btx_omni.domain.programs import ComponentClass


class TechnicalMatchStatus(StrEnum):
    MATCHED = "MATCHED"
    POSSIBLE_MATCH_REVIEW_REQUIRED = "POSSIBLE_MATCH_REVIEW_REQUIRED"
    NO_MATCH = "NO_MATCH"
    INSUFFICIENT_TAXONOMY = "INSUFFICIENT_TAXONOMY"


def normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


APPROVED_ALIASES: dict[str, tuple[str, ...]] = {
    "cc-actuator": ("actuator housing", "actuator housings", "actuation housing"),
    "cc-structural-airframe": (
        "structural bracket",
        "structural brackets",
        "airframe bracket",
    ),
    "cc-gas-manifold": ("hydraulic manifold", "fluid manifold", "hydraulic manifolds"),
    "cc-valve-body": ("valve body", "valve bodies"),
    "cc-sensor-housing": ("sensor housing", "electronics enclosure"),
}


@dataclass(frozen=True)
class TechnicalRetryPolicy:
    auth_failed_seconds: int = 3600
    timeout_seconds: int = 300
    quota_seconds: int = 21600
    unavailable_seconds: int = 900

    def cooldown(self, status: ProviderStatus) -> timedelta | None:
        seconds = {
            ProviderStatus.AUTH_FAILED: self.auth_failed_seconds,
            ProviderStatus.TIMEOUT: self.timeout_seconds,
            ProviderStatus.QUOTA: self.quota_seconds,
            ProviderStatus.UNAVAILABLE: self.unavailable_seconds,
        }.get(status)
        return timedelta(seconds=max(0, seconds)) if seconds is not None else None


@dataclass(frozen=True)
class TechnicalFitMatch:
    candidate: TechnicalCandidate
    status: TechnicalMatchStatus
    component_id: str | None = None
    component_name: str | None = None
    capability_name: str | None = None
    business_units: tuple[tuple[str, str], ...] = ()
    match_rule: str | None = None
    taxonomy_provenance: str = "btx_component_taxonomy_v1"


@dataclass(frozen=True)
class TechnicalOpportunityProjection:
    event_id: str
    decomposition: TechnicalDecompositionResult | None
    matches: tuple[TechnicalFitMatch, ...]
    provider_status: ProviderStatus
    governed_content_hash: str
    language_provider: str | None = None
    language_model: str | None = None


@dataclass(frozen=True)
class TechnicalProcessOutcome:
    projection: TechnicalOpportunityProjection
    should_persist: bool
    attempt_count: int
    next_retry_at: datetime | None
    reused: bool = False
    deferred: bool = False


class TechnicalDecompositionService:
    """Worker-only interpretation. Seller reads consume durable projections."""

    def __init__(
        self,
        *,
        components: tuple[ComponentClass, ...],
        business_units: tuple[BtxBusinessUnit, ...],
    ) -> None:
        self.components = components
        self.business_units = {item.id: item.name for item in business_units}

    @staticmethod
    def provider_model(provider: LanguageProvider) -> str:
        return str(getattr(getattr(provider, "config", None), "model", ""))

    @staticmethod
    def cache_key(request: TechnicalDecompositionRequest, *, model: str = "") -> str:
        fields = [
            request.contract_version,
            request.prompt_version,
            model,
            request.event_id,
            request.event_type,
            request.canonical_customer_name or "",
            request.canonical_program_name or "",
            request.market or "",
        ]
        fields.extend(
            f"{item.evidence_id}:{item.title}:{item.extract}:{item.source_url or ''}:{item.provenance}"
            for item in request.evidence
        )
        return hashlib.sha256("\x1f".join(fields).encode()).hexdigest()

    def process(
        self,
        request: TechnicalDecompositionRequest,
        provider: LanguageProvider,
        *,
        cached: dict | None = None,
        now: datetime | None = None,
        retry_policy: TechnicalRetryPolicy | None = None,
    ) -> TechnicalProcessOutcome:
        clock = now or datetime.now(UTC)
        model = self.provider_model(provider)
        key = self.cache_key(request, model=model)
        attempts = int(cached.get("attempt_count", 0)) if cached else 0
        if (
            cached
            and cached.get("status") == ProviderStatus.AVAILABLE.value
            and cached.get("projection")
        ):
            return TechnicalProcessOutcome(
                TechnicalOpportunityProjection(
                    request.event_id,
                    None,
                    (),
                    ProviderStatus.AVAILABLE,
                    key,
                    cached.get("provider"),
                    cached.get("model"),
                ),
                False,
                attempts,
                cached.get("next_retry_at"),
                reused=True,
            )
        if cached and cached.get("next_retry_at") and cached["next_retry_at"] > clock:
            return TechnicalProcessOutcome(
                TechnicalOpportunityProjection(
                    request.event_id,
                    None,
                    (),
                    ProviderStatus(cached["status"]),
                    key,
                    cached.get("provider"),
                    cached.get("model"),
                ),
                False,
                attempts,
                cached["next_retry_at"],
                deferred=True,
            )
        if not provider.configured:
            projection = TechnicalOpportunityProjection(
                request.event_id,
                None,
                (),
                ProviderStatus.NOT_CONFIGURED,
                key,
                getattr(provider, "name", None),
                model or None,
            )
        else:
            try:
                decomposition = provider.decompose_technical_opportunity(request)
            except LanguageProviderError as error:
                projection = TechnicalOpportunityProjection(
                    request.event_id,
                    None,
                    (),
                    error.status,
                    key,
                    getattr(provider, "name", None),
                    model or None,
                )
            except (RuntimeError, ValueError):
                projection = TechnicalOpportunityProjection(
                    request.event_id,
                    None,
                    (),
                    ProviderStatus.UNAVAILABLE,
                    key,
                    getattr(provider, "name", None),
                    model or None,
                )
            else:
                projection = TechnicalOpportunityProjection(
                    request.event_id,
                    decomposition,
                    tuple(
                        self.match(item) for item in decomposition.component_candidates
                    ),
                    ProviderStatus.AVAILABLE,
                    key,
                    decomposition.provider,
                    decomposition.model,
                )
        cooldown = (retry_policy or TechnicalRetryPolicy()).cooldown(
            projection.provider_status
        )
        return TechnicalProcessOutcome(
            projection, True, attempts + 1, clock + cooldown if cooldown else None
        )

    def match(self, candidate: TechnicalCandidate) -> TechnicalFitMatch:
        value = normalize(candidate.name)
        exact = [item for item in self.components if normalize(item.name) == value]
        aliases = [
            item
            for item in self.components
            if value
            in {normalize(alias) for alias in APPROVED_ALIASES.get(item.id, ())}
        ]
        candidates = exact or aliases
        if len(candidates) == 1:
            item = candidates[0]
            return TechnicalFitMatch(
                candidate,
                TechnicalMatchStatus.MATCHED,
                item.id,
                item.name,
                None,
                tuple(
                    (unit, self.business_units[unit])
                    for unit in item.business_unit_ids
                    if unit in self.business_units
                ),
                "CONTROLLED_EXACT_NAME" if exact else "APPROVED_ALIAS_MATCH",
            )
        tokens = set(value.split())
        if [
            item
            for item in self.components
            if len(tokens & set(normalize(item.name).split())) >= 2
        ]:
            return TechnicalFitMatch(
                candidate, TechnicalMatchStatus.POSSIBLE_MATCH_REVIEW_REQUIRED
            )
        if any(
            word in value
            for word in ("housing", "bracket", "manifold", "actuator", "valve")
        ):
            return TechnicalFitMatch(
                candidate, TechnicalMatchStatus.INSUFFICIENT_TAXONOMY
            )
        return TechnicalFitMatch(candidate, TechnicalMatchStatus.NO_MATCH)


def _candidate(item: TechnicalCandidate) -> dict:
    return {
        "name": item.name,
        "basis": item.basis.value,
        "reason": item.reason,
        "source_support": item.source_support,
        "evidence_ids": list(item.evidence_ids),
        "parent_system": item.parent_system,
        "parent_product": item.parent_product,
        "manufacturing_family": item.manufacturing_family,
    }


def seller_projection(value: TechnicalOpportunityProjection) -> dict:
    """Seller-safe projection: full useful context, never raw Gemini JSON."""
    decomposition = value.decomposition
    return {
        "event_summary": decomposition.event_summary if decomposition else None,
        "product_candidates": [_candidate(x) for x in decomposition.product_candidates]
        if decomposition
        else [],
        "program_candidates": [_candidate(x) for x in decomposition.program_candidates]
        if decomposition
        else [],
        "technical_systems": [_candidate(x) for x in decomposition.technical_systems]
        if decomposition
        else [],
        "uncertainties": list(decomposition.uncertainties) if decomposition else [],
        "provider_status": value.provider_status.value,
        "language_provider": value.language_provider,
        "language_model": value.language_model,
        "matches": [
            {
                "candidate_name": x.candidate.name,
                "basis": x.candidate.basis.value,
                "reason": x.candidate.reason,
                "source_support": x.candidate.source_support,
                "parent_system": x.candidate.parent_system,
                "parent_product": x.candidate.parent_product,
                "manufacturing_family": x.candidate.manufacturing_family,
                "status": x.status.value,
                "component_id": x.component_id,
                "component_name": x.component_name,
                "business_units": [
                    {"id": uid, "name": name} for uid, name in x.business_units
                ],
                "match_rule": x.match_rule,
                "evidence_ids": list(x.candidate.evidence_ids),
            }
            for x in value.matches
        ],
        "disclosure": "Technical decomposition is Gemini-assisted. BTX component, capability, and Business Unit matching is deterministic.",
    }
