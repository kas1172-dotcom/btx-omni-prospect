"""Explicit adapters from governed domain projections to explanation requests.

These adapters deliberately accept only seller-facing deterministic projections.
They are used by bounded processing, never by ordinary seller GET handlers.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from btx_omni.ai.contracts import ExplanationType, GovernedExplanationRequest
from btx_omni.modules.intelligence.governed_explanations import (
    ExplanationProjection,
    GovernedExplanationService,
)
from btx_omni.modules.scoring.account_attractiveness import (
    SellerAttractivenessProjection,
)


def customer_attractiveness_subject_key(account_id: str) -> str:
    return f"account:{account_id}"


def customer_attractiveness_request(
    *, account_id: str, account_name: str, projection: SellerAttractivenessProjection
) -> GovernedExplanationRequest:
    """Adapt the existing deterministic score; never recalculate it."""
    score = str(projection.score) if projection.score is not None else "unavailable"
    drivers = tuple(
        f"{item.key}: score {item.factor_score}; contribution {item.contribution}"
        for item in projection.factors
        if item.factor_score is not None
    )
    factor_gaps = tuple(
        f"{item.key}: {gap} unavailable"
        for item in projection.factors
        for gap in item.missing_subfactors
    )
    evidence_ids = (
        tuple(
            sorted(
                {
                    evidence_id
                    for item in projection.factors
                    for evidence_id in item.evidence_ids
                }
            )
        )
        or projection.evidence_ids
    )
    limitations = (
        *projection.missingness,
        *factor_gaps,
        projection.interpretation_note,
    )[:12]
    return GovernedExplanationRequest(
        ExplanationType.CUSTOMER_ATTRACTIVENESS,
        "CUSTOMER",
        account_name,
        f"Customer Attractiveness: {score} {projection.score_unit}; coverage {projection.coverage}.",
        projection.status,
        numeric_value=score if projection.score is not None else None,
        score_unit=projection.score_unit,
        configuration_version=projection.configuration_version,
        key_drivers=drivers[:12],
        limiting_factors=limitations,
        evidence_ids=evidence_ids,
        data_mode=projection.data_mode,
        hypothesis_or_calibration="Hypothesis inputs"
        if projection.hypothesis
        else None,
    )


def federal_opportunity_subject_key(opportunity: Mapping[str, Any]) -> str:
    return f"federal-opportunity:{opportunity['opportunity_id']}"


def federal_opportunity_request(
    opportunity: Mapping[str, Any],
) -> GovernedExplanationRequest:
    """Adapt deterministic Federal Opportunity Relevance without adding PWin."""
    relevance = opportunity["relevance"]
    factors = tuple(
        f"{item['name']}: {item['points']} of {item['weight']} points; {item['state']}"
        for item in relevance["factors"]
        if item["available"]
    )
    evidence = opportunity.get("evidence", {})
    evidence_ids = (str(evidence["id"]),) if evidence.get("id") else ()
    return GovernedExplanationRequest(
        ExplanationType.FEDERAL_OPPORTUNITY_RELEVANCE,
        "FEDERAL_OPPORTUNITY",
        str(opportunity["title"]),
        f"Federal Opportunity Relevance: {relevance['score']} of {relevance['score_range']}; tier {relevance['tier']}.",
        relevance["tier"],
        numeric_value=str(relevance["score"]),
        score_unit=str(relevance["score_range"]),
        configuration_version=str(relevance["configuration_version"]),
        key_drivers=factors,
        limiting_factors=(
            *tuple(str(item) for item in relevance["missingness"]),
            *tuple(str(item) for item in opportunity.get("missingness", ())),
            str(relevance["calibration_label"]),
        ),
        evidence_ids=evidence_ids,
        data_mode=str(opportunity["data_mode"]),
        hypothesis_or_calibration=str(relevance["calibration_label"]),
    )


def process_customer_attractiveness_explanation(
    *,
    account_id: str,
    account_name: str,
    projection: SellerAttractivenessProjection,
    provider: object,
    repository: object,
    now: datetime,
) -> ExplanationProjection:
    return GovernedExplanationService().process(
        customer_attractiveness_request(
            account_id=account_id, account_name=account_name, projection=projection
        ),
        provider,
        repository,
        subject_key=customer_attractiveness_subject_key(account_id),
        now=now,
    )


def process_federal_opportunity_explanation(
    *,
    opportunity: Mapping[str, Any],
    provider: object,
    repository: object,
    now: datetime,
) -> ExplanationProjection:
    return GovernedExplanationService().process(
        federal_opportunity_request(opportunity),
        provider,
        repository,
        subject_key=federal_opportunity_subject_key(opportunity),
        now=now,
    )


def persisted_seller_explanation(
    repository: object | None, *, subject_key: str, explanation_type: ExplanationType
) -> dict[str, object] | None:
    """Read a persisted, validated seller projection without invoking a provider."""
    if repository is None:
        return None
    record = repository.latest_governed_explanation(subject_key, explanation_type.value)
    if not record:
        return None
    payload = json.loads(record["projection"])
    allowed = {
        "provider_status",
        "assisted",
        "summary",
        "key_drivers",
        "limitations",
        "what_to_consider",
        "evidence_ids",
        "disclosure",
    }
    return {key: payload[key] for key in allowed if key in payload}


def technical_opportunity_subject_key(event_id: str) -> str:
    return f"technical-opportunity:{event_id}"


def technical_opportunity_request(
    projection: Mapping[str, Any], *, event_id: str
) -> GovernedExplanationRequest:
    matches = projection.get("matches", ())
    candidates = (
        *projection.get("product_candidates", ()),
        *projection.get("program_candidates", ()),
        *projection.get("technical_systems", ()),
    )
    drivers = tuple(
        f"{item.get('name')}: {item.get('basis')}" for item in candidates[:6]
    ) + tuple(
        f"{item['candidate_name']}: {item['status']}; {item.get('component_name') or 'no controlled component'}; "
        f"BUs {', '.join(unit['name'] for unit in item.get('business_units', ())) or 'none'}"
        for item in matches[:6]
    )
    limitations = (
        "Controlled BTX taxonomy alignment indicates technical capability fit, not supplier participation.",
        *tuple(
            f"{item['candidate_name']}: {item['status']}"
            for item in matches
            if item["status"] != "MATCHED"
        ),
        *tuple(str(item) for item in projection.get("uncertainties", ())),
    )[:12]
    evidence = tuple(
        dict.fromkeys(
            evidence_id
            for item in (*candidates, *matches)
            for evidence_id in item.get("evidence_ids", ())
        )
    )[:12]
    return GovernedExplanationRequest(
        ExplanationType.TECHNICAL_OPPORTUNITY_FIT,
        "TECHNICAL_OPPORTUNITY",
        str(projection.get("event_summary") or event_id),
        str(projection.get("event_summary") or "Technical fit projection available."),
        str(projection.get("provider_status") or "UNAVAILABLE"),
        key_drivers=drivers[:12],
        limiting_factors=limitations,
        evidence_ids=evidence,
        data_mode="PUBLIC_EVIDENCE",
    )


def relationship_path_subject_key(customer_id: str, path_id: str) -> str:
    return f"relationship-path:{customer_id}:{path_id}"


def relationship_path_request(
    path: Mapping[str, Any], *, customer_id: str
) -> GovernedExplanationRequest:
    evidence_ids = tuple(
        dict.fromkeys(
            source_id
            for item in path.get("evidence", ())
            for source_id in item.get("source_ids", ())
        )
    )[:12]
    limits = [
        "The path shows a possible route; it does not establish willingness to make an introduction."
    ]
    if path.get("presentation_state") != "validated":
        limits.extend(path.get("validation_requirements", ()))
    if not path.get("direct"):
        limits.append("This is an indirect path.")
    return GovernedExplanationRequest(
        ExplanationType.RELATIONSHIP_PATH,
        "RELATIONSHIP_PATH",
        str(path.get("summary") or path["path_id"]),
        f"{path.get('presentation_state')} relationship path with {path.get('step_count')} governed hops.",
        str(path.get("presentation_state")),
        key_drivers=(
            str(path.get("seller_rationale")),
            str(path.get("connection_label")),
        ),
        limiting_factors=tuple(limits[:12]),
        evidence_ids=evidence_ids,
        data_mode="SAMPLE" if "SAMPLE" in str(path.get("truth_label")) else "GOVERNED",
    )


def process_technical_opportunity_explanation(
    *,
    projection: Mapping[str, Any],
    event_id: str,
    provider: object,
    repository: object,
    now: datetime,
) -> ExplanationProjection:
    return GovernedExplanationService().process(
        technical_opportunity_request(projection, event_id=event_id),
        provider,
        repository,
        subject_key=technical_opportunity_subject_key(event_id),
        now=now,
    )


def process_relationship_path_explanation(
    *,
    path: Mapping[str, Any],
    customer_id: str,
    provider: object,
    repository: object,
    now: datetime,
) -> ExplanationProjection:
    return GovernedExplanationService().process(
        relationship_path_request(path, customer_id=customer_id),
        provider,
        repository,
        subject_key=relationship_path_subject_key(customer_id, str(path["path_id"])),
        now=now,
    )
