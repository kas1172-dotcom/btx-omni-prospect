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
    PublicEvidenceRecord,
    TechnicalCandidate,
    TechnicalDecompositionRequest,
    TechnicalDecompositionResult,
    TechnicalEvidenceLayer,
)
from btx_omni.domain.btx import BtxBusinessUnit
from btx_omni.domain.capabilities import Capability
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

CATEGORY_COMPONENTS: dict[str, tuple[str, ...]] = {
    "GUIDANCE_ELECTRONICS": ("cc-sensor-housing",),
    "CONTROL_ACTUATION": ("cc-actuator",),
    "MISSILE_BODY": ("cc-missile-body-section", "cc-structural-airframe"),
    "WARHEAD_BODY": ("cc-warhead-body",),
    "LAUNCH_TUBE_HARDWARE": ("cc-missile-body-section", "cc-structural-airframe"),
    "LAUNCH_AND_TARGETING": ("cc-c5isr-hardware",),
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
    capabilities: tuple[tuple[str, str], ...] = ()
    facilities: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class TechnicalOpportunityProjection:
    event_id: str
    decomposition: TechnicalDecompositionResult | None
    matches: tuple[TechnicalFitMatch, ...]
    provider_status: ProviderStatus
    governed_content_hash: str
    language_provider: str | None = None
    language_model: str | None = None
    citations: tuple[PublicEvidenceRecord, ...] = ()


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
        capabilities: tuple[Capability, ...] = (),
        facilities: tuple[object, ...] = (),
    ) -> None:
        self.components = components
        self.business_units = {item.id: item.name for item in business_units}
        self.capabilities = capabilities
        self.facilities = facilities

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
            request.account_id or "",
            request.source_revision or "",
        ]
        fields.extend(
            f"{item.evidence_id}:{item.title}:{item.extract}:{item.source_url or ''}:{item.provenance}"
            for item in request.evidence
        )
        fields.extend(
            f"reviewed:{item.name}:{item.parent_component or ''}:{item.component_category or ''}:{item.evidence_layer.value}:{','.join(item.evidence_ids)}"
            for item in request.reviewed_components
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
                    request.evidence,
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
                    request.evidence,
                ),
                False,
                attempts,
                cached["next_retry_at"],
                deferred=True,
            )
        if not provider.configured:
            reviewed = self._reviewed_fallback(
                request, provider="reviewed-public-sources", model="reviewed-catalog"
            )
            projection = TechnicalOpportunityProjection(
                request.event_id,
                reviewed,
                tuple(self.match(item) for item in reviewed.component_candidates)
                if reviewed
                else (),
                ProviderStatus.NOT_CONFIGURED,
                key,
                getattr(provider, "name", None),
                model or None,
                request.evidence,
            )
        else:
            try:
                decomposition = provider.decompose_technical_opportunity(request)
            except LanguageProviderError as error:
                reviewed = self._reviewed_fallback(
                    request,
                    provider="reviewed-public-sources",
                    model="reviewed-catalog",
                )
                projection = TechnicalOpportunityProjection(
                    request.event_id,
                    reviewed,
                    tuple(self.match(item) for item in reviewed.component_candidates)
                    if reviewed
                    else (),
                    error.status,
                    key,
                    getattr(provider, "name", None),
                    model or None,
                    request.evidence,
                )
            except (RuntimeError, ValueError):
                reviewed = self._reviewed_fallback(
                    request,
                    provider="reviewed-public-sources",
                    model="reviewed-catalog",
                )
                projection = TechnicalOpportunityProjection(
                    request.event_id,
                    reviewed,
                    tuple(self.match(item) for item in reviewed.component_candidates)
                    if reviewed
                    else (),
                    ProviderStatus.UNAVAILABLE,
                    key,
                    getattr(provider, "name", None),
                    model or None,
                    request.evidence,
                )
            else:
                if request.reviewed_components:
                    reviewed_names = {
                        normalize(item.name) for item in request.reviewed_components
                    }
                    decomposition = TechnicalDecompositionResult(
                        event_summary=decomposition.event_summary,
                        product_candidates=decomposition.product_candidates,
                        program_candidates=decomposition.program_candidates,
                        technical_systems=decomposition.technical_systems,
                        component_candidates=tuple(request.reviewed_components)
                        + tuple(
                            item
                            for item in decomposition.component_candidates
                            if normalize(item.name) not in reviewed_names
                        ),
                        uncertainties=tuple(
                            dict.fromkeys(
                                (
                                    *decomposition.uncertainties,
                                    *(
                                        uncertainty
                                        for item in request.reviewed_components
                                        for uncertainty in item.material_uncertainties
                                    ),
                                )
                            )
                        )[:8],
                        provider=decomposition.provider,
                        model=decomposition.model,
                    )
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
                    request.evidence,
                )
        cooldown = (retry_policy or TechnicalRetryPolicy()).cooldown(
            projection.provider_status
        )
        return TechnicalProcessOutcome(
            projection, True, attempts + 1, clock + cooldown if cooldown else None
        )

    @staticmethod
    def _reviewed_fallback(
        request: TechnicalDecompositionRequest, *, provider: str, model: str
    ) -> TechnicalDecompositionResult | None:
        if not request.reviewed_components:
            return None
        return TechnicalDecompositionResult(
            event_summary="Reviewed public sources establish a high-level program and component hierarchy; possible BTX fit remains subject to validation.",
            component_candidates=request.reviewed_components,
            uncertainties=tuple(
                dict.fromkeys(
                    uncertainty
                    for item in request.reviewed_components
                    for uncertainty in item.material_uncertainties
                )
            )[:8],
            provider=provider,
            model=model,
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
        category = CATEGORY_COMPONENTS.get(candidate.component_category or "", ())
        category_matches = [item for item in self.components if item.id in category]
        candidates = exact or aliases or category_matches
        if len(candidates) == 1:
            item = candidates[0]
            capabilities = tuple(
                (
                    f"{capability.id}:{index}",
                    process,
                )
                for capability in self.capabilities
                if set(capability.business_units) & set(item.business_unit_ids)
                for index, process in enumerate(
                    capability.processes or (capability.name,)
                )
            )
            facilities = tuple(
                (str(facility.id), str(facility.name))
                for facility in self.facilities
                if getattr(facility, "business_unit_id", None) in item.business_unit_ids
            )
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
                "CONTROLLED_EXACT_NAME"
                if exact
                else "APPROVED_ALIAS_MATCH"
                if aliases
                else "CONTROLLED_CATEGORY_MAPPING",
                capabilities=capabilities,
                facilities=facilities,
            )
        if len(candidates) > 1 and category_matches:
            # More than one governed manufacturing family is a hypothesis set,
            # not a stronger match. Keep each alternative visible downstream.
            item = candidates[0]
            capabilities = tuple(
                (f"{capability.id}:{index}", process)
                for capability in self.capabilities
                if set(capability.business_units) & set(item.business_unit_ids)
                for index, process in enumerate(
                    capability.processes or (capability.name,)
                )
            )
            return TechnicalFitMatch(
                candidate,
                TechnicalMatchStatus.POSSIBLE_MATCH_REVIEW_REQUIRED,
                item.id,
                item.name,
                None,
                tuple(
                    (unit, self.business_units[unit])
                    for unit in item.business_unit_ids
                    if unit in self.business_units
                ),
                "CONTROLLED_CATEGORY_MAPPING_REVIEW_REQUIRED",
                capabilities=capabilities,
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


def _candidate(item: TechnicalCandidate, *, context_key: str = "") -> dict:
    stable_id = (
        "component-"
        + hashlib.sha256(
            "\x1f".join(
                (
                    context_key,
                    item.evidence_layer.value,
                    item.parent_component or "",
                    normalize(item.name),
                )
            ).encode()
        ).hexdigest()[:16]
    )
    return {
        "component_id": stable_id,
        "name": item.name,
        "basis": item.basis.value,
        "reason": item.reason,
        "source_support": item.source_support,
        "evidence_ids": list(item.evidence_ids),
        "parent_system": item.parent_system,
        "parent_product": item.parent_product,
        "manufacturing_family": item.manufacturing_family,
        "parent_component": item.parent_component,
        "component_category": item.component_category,
        "evidence_layer": item.evidence_layer.value,
        "confidence_state": item.confidence_state,
        "material_uncertainties": list(item.material_uncertainties),
        "validation_questions": list(item.validation_questions),
        "source_publication_dates": list(item.source_publication_dates),
        "research_methods": list(item.research_methods),
    }


def seller_projection(value: TechnicalOpportunityProjection) -> dict:
    """Seller-safe projection: full useful context, never raw Gemini JSON."""
    decomposition = value.decomposition
    components = (
        [
            _candidate(x, context_key=value.event_id)
            for x in decomposition.component_candidates
            if x.basis.value == "SOURCE_STATED"
        ]
        if decomposition
        else []
    )
    component_names = {item["name"] for item in components}
    parent_by_name = {
        item["name"]: item.get("parent_component") for item in components
    }
    for item in components:
        parent = item.get("parent_component")
        if not parent or parent not in component_names or parent == item["name"]:
            item["parent_component"] = None
            continue
        visited = {item["name"]}
        cursor = parent
        while cursor:
            if cursor in visited:
                item["parent_component"] = None
                break
            visited.add(cursor)
            cursor = parent_by_name.get(cursor)
    fit_hypotheses = []
    for match in value.matches:
        if not match.component_id or match.candidate.basis.value != "SOURCE_STATED":
            continue
        fit_hypotheses.append(
            {
                "component_name": match.candidate.name,
                "evidence_layer": TechnicalEvidenceLayer.BTX_FIT_HYPOTHESIS.value,
                "fit_state": "HYPOTHESIS_REQUIRES_VALIDATION",
                "candidate_component_class": match.component_name,
                "candidate_capabilities": [
                    {"id": item_id, "name": name}
                    for item_id, name in match.capabilities
                ],
                "candidate_business_units": [
                    {"id": item_id, "name": name}
                    for item_id, name in match.business_units
                ],
                "candidate_facilities": [
                    {"id": item_id, "name": name} for item_id, name in match.facilities
                ],
                "material_uncertainties": list(match.candidate.material_uncertainties),
                "validation_questions": list(match.candidate.validation_questions),
                "evidence_ids": list(match.candidate.evidence_ids),
                "statement": f"{match.component_name} is a possible manufacturing-family fit for {match.candidate.name}; program participation, qualification, capacity, and an award are not established.",
            }
        )
    return {
        "event_summary": decomposition.event_summary if decomposition else None,
        "product_candidates": [
            _candidate(x, context_key=value.event_id)
            for x in decomposition.product_candidates
        ]
        if decomposition
        else [],
        "program_candidates": [
            _candidate(x, context_key=value.event_id)
            for x in decomposition.program_candidates
        ]
        if decomposition
        else [],
        "technical_systems": [
            _candidate(x, context_key=value.event_id)
            for x in decomposition.technical_systems
        ]
        if decomposition
        else [],
        "components": components,
        "fit_hypotheses": fit_hypotheses,
        "citations": [
            {
                "evidence_id": item.evidence_id,
                "title": item.title,
                "url": item.source_url,
                "provenance": item.provenance,
            }
            for item in value.citations
        ],
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
                "capabilities": [
                    {"id": uid, "name": name} for uid, name in x.capabilities
                ],
                "facilities": [{"id": uid, "name": name} for uid, name in x.facilities],
            }
            for x in value.matches
        ],
        "disclosure": "Technical decomposition is Gemini-assisted. BTX component, capability, and Business Unit matching is deterministic.",
    }
