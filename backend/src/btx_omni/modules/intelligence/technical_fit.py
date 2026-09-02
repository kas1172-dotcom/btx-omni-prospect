"""Deterministic matching of Gemini technical hypotheses to controlled BTX taxonomy."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
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


# Approved terms are deliberately narrow; this map is controlled code, not model output.
APPROVED_ALIASES: dict[str, tuple[str, ...]] = {
    "cc-actuator": ("actuator housing", "actuator housings", "actuation housing"),
    "cc-structural-airframe": ("structural bracket", "structural brackets", "airframe bracket"),
    "cc-gas-manifold": ("hydraulic manifold", "fluid manifold", "hydraulic manifolds"),
    "cc-valve-body": ("valve body", "valve bodies"),
    "cc-sensor-housing": ("sensor housing", "electronics enclosure"),
}


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


class TechnicalDecompositionService:
    """Bounded cache. Call from worker jobs, never a seller read endpoint."""

    def __init__(self, *, components: tuple[ComponentClass, ...], business_units: tuple[BtxBusinessUnit, ...]) -> None:
        self.components = components
        self.business_units = {item.id: item.name for item in business_units}
        self._cache: dict[str, TechnicalOpportunityProjection] = {}

    @staticmethod
    def cache_key(request: TechnicalDecompositionRequest, *, model: str = "") -> str:
        value = "\x1f".join([request.contract_version, request.prompt_version, model, request.event_id, *(
            f"{item.evidence_id}:{item.title}:{item.extract}:{item.source_url or ''}" for item in request.evidence
        )])
        return hashlib.sha256(value.encode()).hexdigest()

    def process(self, request: TechnicalDecompositionRequest, provider: LanguageProvider) -> TechnicalOpportunityProjection:
        key = self.cache_key(request, model=getattr(getattr(provider, "config", None), "model", ""))
        if key in self._cache:
            return self._cache[key]
        if not provider.configured:
            result = TechnicalOpportunityProjection(request.event_id, None, (), ProviderStatus.NOT_CONFIGURED, key)
            self._cache[key] = result
            return result
        try:
            decomposition = provider.decompose_technical_opportunity(request)
        except LanguageProviderError as error:
            result = TechnicalOpportunityProjection(request.event_id, None, (), error.status, key)
        except (RuntimeError, ValueError):
            result = TechnicalOpportunityProjection(request.event_id, None, (), ProviderStatus.UNAVAILABLE, key)
        else:
            result = TechnicalOpportunityProjection(
                request.event_id, decomposition,
                tuple(self.match(item) for item in decomposition.component_candidates),
                ProviderStatus.AVAILABLE, key,
            )
        self._cache[key] = result
        return result

    def match(self, candidate: TechnicalCandidate) -> TechnicalFitMatch:
        value = normalize(candidate.name)
        exact = [item for item in self.components if normalize(item.name) == value]
        aliases = [item for item in self.components if value in {normalize(alias) for alias in APPROVED_ALIASES.get(item.id, ())}]
        candidates = exact or aliases
        if len(candidates) == 1:
            item = candidates[0]
            return TechnicalFitMatch(candidate, TechnicalMatchStatus.MATCHED, item.id, item.name, None,
                tuple((unit, self.business_units[unit]) for unit in item.business_unit_ids if unit in self.business_units),
                "CONTROLLED_EXACT_NAME" if exact else "APPROVED_ALIAS_MATCH")
        # A generic controlled token overlap is directionally useful but never definitive.
        tokens = set(value.split())
        related = [item for item in self.components if len(tokens & set(normalize(item.name).split())) >= 2]
        if related:
            return TechnicalFitMatch(candidate, TechnicalMatchStatus.POSSIBLE_MATCH_REVIEW_REQUIRED)
        if any(word in value for word in ("housing", "bracket", "manifold", "actuator", "valve")):
            return TechnicalFitMatch(candidate, TechnicalMatchStatus.INSUFFICIENT_TAXONOMY)
        return TechnicalFitMatch(candidate, TechnicalMatchStatus.NO_MATCH)


def seller_projection(value: TechnicalOpportunityProjection) -> dict:
    """JSON-safe backend-owned projection; UI never reconstructs match authority."""
    return {
        "provider_status": value.provider_status.value,
        "matches": [
            {"candidate_name": item.candidate.name, "basis": item.candidate.basis.value,
             "status": item.status.value, "component_name": item.component_name,
             "business_units": [{"id": unit_id, "name": name} for unit_id, name in item.business_units],
             "match_rule": item.match_rule, "evidence_ids": list(item.candidate.evidence_ids)}
            for item in value.matches
        ],
        "disclosure": "Technical decomposition is Gemini-assisted. BTX component, capability, and Business Unit matching is deterministic.",
    }
