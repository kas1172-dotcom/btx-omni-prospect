from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import create_engine

from btx_omni.ai.contracts import (
    ExplanationType,
    GovernedExplanation,
    GovernedExplanationRequest,
    ProviderStatus,
)
from btx_omni.api.accounts import account_360
from btx_omni.api.runtime import PocRuntime
from btx_omni.core.config import Settings
from btx_omni.modules.federal_procurement import fixture, procurement_projection
from btx_omni.modules.intelligence.governed_explanation_adapters import (
    customer_attractiveness_request,
    customer_attractiveness_subject_key,
    federal_opportunity_request,
    federal_opportunity_subject_key,
    persisted_seller_explanation,
    persisted_seller_explanations,
    process_customer_attractiveness_explanation,
    process_federal_opportunity_explanation,
    process_relationship_path_explanation,
    process_technical_opportunity_explanation,
    relationship_path_request,
    relationship_path_subject_key,
    technical_opportunity_request,
)
from btx_omni.modules.relationships.presentation import (
    SellerRelationshipPresentationService,
)
from btx_omni.modules.relationships.service import RelationshipIntelligenceService
from btx_omni.modules.scoring.account_attractiveness import (
    AccountAttractivenessInputs,
    seller_attractiveness_projection,
)
from btx_omni.monitor.repository import MonitorRepository
from btx_omni.providers.sample.environment import build_sample_environment


class ExplanationProvider:
    configured = True
    name = "fake-gemini"
    config = type("Config", (), {"model": "fake-explanation-v1"})()

    def __init__(self) -> None:
        self.calls = 0

    def explain_governed_result(
        self, request: GovernedExplanationRequest
    ) -> GovernedExplanation:
        self.calls += 1
        return GovernedExplanation(
            "The governed result has the listed drivers and limitations.",
            request.key_drivers[:2],
            request.limiting_factors[:2],
            ("Review governed evidence before outreach.",),
            request.evidence_ids,
            request.explanation_type,
            self.name,
            self.config.model,
            request.contract_version,
        )


def _repository() -> MonitorRepository:
    return MonitorRepository(
        create_engine(__import__("os").environ["BTX_DATABASE_URL"])
    )


def test_customer_adapter_preserves_deterministic_score_and_missingness() -> None:
    projection = seller_attractiveness_projection(
        AccountAttractivenessInputs(
            {
                "program_durability.expected_production_horizon": "TEN_PLUS_YEARS",
                "program_durability.repeat_production_pattern": "ESTABLISHED_RECURRING",
                "program_durability.commitment_strength": "FUNDED_AWARDED_CONTRACTED",
                "program_durability.industry_specific_maturity_evidence": "STRONG_EVIDENCE",
                "btx_manufacturing_fit.material_match": "ROUTINE",
                "btx_manufacturing_fit.process_tolerance_match": "ROUTINE",
                "btx_manufacturing_fit.certification_compliance_fit": "ALL_MET",
                "btx_manufacturing_fit.volume_compatibility": "NORMAL_RANGE",
                "addressable_btx_work.btx_relevant_component_content": "ONE_FAMILY",
                "strategic_target_fit": "STRONG_TARGET_ARCHETYPE",
            }
        ),
        calculated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    request = customer_attractiveness_request(
        account_id="boeing", account_name="Boeing", projection=projection
    )
    assert request.explanation_type.value == "CUSTOMER_ATTRACTIVENESS"
    assert request.subject_display_name == "Boeing"
    assert str(projection.score) in request.deterministic_result
    assert projection.score_unit in request.deterministic_result
    assert request.numeric_value == str(projection.score)
    assert request.score_unit == projection.score_unit
    assert request.configuration_version == projection.configuration_version
    assert projection.data_mode == request.data_mode
    assert any("program_durability" in driver for driver in request.key_drivers)
    assert any(
        "missing" in limitation.lower() for limitation in request.limiting_factors
    )
    assert "probability" not in request.deterministic_result.lower()


def test_customer_explanation_persists_without_changing_deterministic_projection() -> (
    None
):
    projection = seller_attractiveness_projection(
        AccountAttractivenessInputs(
            {"strategic_target_fit": "STRONG_TARGET_ARCHETYPE"}
        ),
        calculated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    repository = _repository()
    provider = ExplanationProvider()
    account_id = f"customer-{uuid4()}"
    original_score = projection.score
    outcome = process_customer_attractiveness_explanation(
        account_id=account_id,
        account_name="Boeing",
        projection=projection,
        provider=provider,
        repository=repository,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    persisted = persisted_seller_explanation(
        repository,
        subject_key=customer_attractiveness_subject_key(account_id),
        explanation_type=ExplanationType.CUSTOMER_ATTRACTIVENESS,
    )
    assert provider.calls == 1
    assert outcome.provider_status is ProviderStatus.AVAILABLE
    assert projection.score == original_score
    assert persisted and persisted["assisted"] is True
    assert "attempt_count" not in persisted and "next_retry_at" not in persisted
    bulk = persisted_seller_explanations(
        repository,
        subject_keys=(customer_attractiveness_subject_key(account_id), "missing"),
        explanation_type=ExplanationType.CUSTOMER_ATTRACTIVENESS,
    )
    assert list(bulk) == [customer_attractiveness_subject_key(account_id)]
    assert bulk[customer_attractiveness_subject_key(account_id)] == persisted


def test_customer_360_read_attaches_persisted_projection_without_provider_call() -> (
    None
):
    url = __import__("os").environ["BTX_DATABASE_URL"]
    runtime = PocRuntime(Settings(database_url=url, monitor_durable_state_enabled=True))
    account = next(
        item for item in runtime.environment().accounts if item.id == "lockheed-martin"
    )
    scenario = runtime.sample.priority_scenarios.get(
        account.id
    ) or runtime.sample.rich_scenarios.get(account.id)
    projection = seller_attractiveness_projection(
        AccountAttractivenessInputs(runtime.sample.scoring_inputs.get(account.id, {})),
        calculated_at=runtime.observed_at(),
        excluded=bool(scenario and scenario.exclusion_reason),
        exclusion_reason=scenario.exclusion_reason if scenario else None,
    )
    provider = ExplanationProvider()
    process_customer_attractiveness_explanation(
        account_id=account.id,
        account_name=account.legal_name,
        projection=projection,
        provider=provider,
        repository=runtime.monitor.repository,
        now=runtime.observed_at(),
    )
    calls_after_processing = provider.calls
    response = account_360(account.id, runtime)
    assert response["governed_explanation"]
    assert response["governed_explanation"]["assisted"] is True
    assert response["account_attractiveness"]["score"] == projection.score
    assert provider.calls == calls_after_processing


def test_federal_adapter_preserves_relevance_and_calibration_without_probability() -> (
    None
):
    opportunity = fixture(datetime(2026, 9, 1, tzinfo=UTC))[0][0]
    request = federal_opportunity_request(opportunity)
    relevance = opportunity["relevance"]
    assert request.explanation_type.value == "FEDERAL_OPPORTUNITY_RELEVANCE"
    assert str(relevance["score"]) in request.deterministic_result
    assert relevance["calibration_label"] in request.limiting_factors
    assert request.numeric_value == str(relevance["score"])
    assert request.score_unit == relevance["score_range"]
    assert request.configuration_version == relevance["configuration_version"]
    assert opportunity["evidence"]["id"] in request.evidence_ids
    assert "pwin" not in request.deterministic_result.lower()
    assert "probability" not in request.deterministic_result.lower()


def test_federal_explanation_persists_and_projection_read_is_provider_free() -> None:
    now = datetime(2026, 9, 1, tzinfo=UTC)
    opportunity = fixture(now)[0][0]
    repository = _repository()
    provider = ExplanationProvider()
    outcome = process_federal_opportunity_explanation(
        opportunity=opportunity, provider=provider, repository=repository, now=now
    )
    assert outcome.provider_status is ProviderStatus.AVAILABLE
    calls_after_processing = provider.calls

    runtime = SimpleNamespace(
        observed_at=lambda: now,
        monitor=SimpleNamespace(observations={}, repository=repository),
        settings=SimpleNamespace(
            monitor_sam_naics_verification_state="PENDING_VERIFICATION",
            sam_api_key=None,
            federal_procurement_fixture_mode=True,
        ),
    )
    selected = procurement_projection(runtime)["active"]["opportunities"][0]
    assert (
        selected["governed_explanation"]
        and selected["governed_explanation"]["assisted"] is True
    )
    assert provider.calls == calls_after_processing
    assert selected["relevance"]["score"] == opportunity["relevance"]["score"]
    assert "pwin" not in str(selected).lower()
    assert federal_opportunity_subject_key(opportunity).startswith(
        "federal-opportunity:"
    )


def test_technical_adapter_preserves_governed_match_and_bu() -> None:
    projection = {
        "event_summary": "Award supports Program X.",
        "provider_status": "AVAILABLE",
        "product_candidates": [
            {"name": "Program X", "basis": "SOURCE_STATED", "evidence_ids": ["ev-1"]}
        ],
        "program_candidates": [],
        "technical_systems": [
            {"name": "Actuation", "basis": "MODEL_INFERRED", "evidence_ids": ["ev-1"]}
        ],
        "uncertainties": ["System is model inferred."],
        "matches": [
            {
                "candidate_name": "Actuator housing",
                "status": "MATCHED",
                "component_name": "Actuator Housing",
                "business_units": [{"id": "aero", "name": "Aerospace"}],
                "evidence_ids": ["ev-1"],
            },
            {
                "candidate_name": "Software",
                "status": "NO_MATCH",
                "business_units": [],
                "evidence_ids": ["ev-1"],
            },
        ],
    }
    request = technical_opportunity_request(projection, event_id="event-1")
    assert request.explanation_type is ExplanationType.TECHNICAL_OPPORTUNITY_FIT
    assert "SOURCE_STATED" in " ".join(request.key_drivers)
    assert "MODEL_INFERRED" in " ".join(request.key_drivers)
    assert "MATCHED" in " ".join(request.key_drivers)
    assert "Aerospace" in " ".join(request.key_drivers)
    assert request.evidence_ids == ("ev-1",)
    assert "supplier participation" in " ".join(request.limiting_factors).lower()


def test_technical_explanation_persists_without_changing_fit() -> None:
    projection = {
        "event_summary": "Program X",
        "provider_status": "AVAILABLE",
        "product_candidates": [],
        "program_candidates": [],
        "technical_systems": [],
        "uncertainties": [],
        "matches": [
            {
                "candidate_name": "Actuator housing",
                "status": "MATCHED",
                "component_name": "Actuator Housing",
                "business_units": [{"id": "aero", "name": "Aerospace"}],
                "evidence_ids": ["ev-1"],
            }
        ],
    }
    provider = ExplanationProvider()
    repository = _repository()
    outcome = process_technical_opportunity_explanation(
        projection=projection,
        event_id=f"event-{uuid4()}",
        provider=provider,
        repository=repository,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert outcome.assisted and provider.calls == 1
    assert projection["matches"][0]["status"] == "MATCHED"
    assert projection["matches"][0]["business_units"][0]["name"] == "Aerospace"


def test_relationship_adapter_preserves_governed_path_and_caveat() -> None:
    result = RelationshipIntelligenceService(
        build_sample_environment()
    ).account_relationships("boeing")
    path = SellerRelationshipPresentationService().present(result)["seller_projection"][
        "validated"
    ][0]
    request = relationship_path_request(path, customer_id="boeing")
    assert request.explanation_type is ExplanationType.RELATIONSHIP_PATH
    assert str(path["step_count"]) in request.deterministic_result
    assert "willingness to make an introduction" in " ".join(request.limiting_factors)
    assert "probability" not in request.deterministic_result.lower()


def test_relationship_explanation_persists_without_changing_path() -> None:
    result = RelationshipIntelligenceService(
        build_sample_environment()
    ).account_relationships("boeing")
    path = SellerRelationshipPresentationService().present(result)["seller_projection"][
        "validated"
    ][0]
    provider = ExplanationProvider()
    repository = _repository()
    outcome = process_relationship_path_explanation(
        path=path,
        customer_id="boeing",
        provider=provider,
        repository=repository,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    persisted = persisted_seller_explanation(
        repository,
        subject_key=relationship_path_subject_key("boeing", path["path_id"]),
        explanation_type=ExplanationType.RELATIONSHIP_PATH,
    )
    assert outcome.assisted and persisted and persisted["assisted"] is True
    assert path["presentation_state"] == "validated"
