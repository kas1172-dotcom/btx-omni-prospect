from __future__ import annotations

import json

import pytest

from btx_omni.ai.config import AiConfig
from btx_omni.ai.contracts import (
    PublicEvidenceRecord,
    TechnicalBasis,
    TechnicalCandidate,
    TechnicalDecompositionRequest,
    TechnicalDecompositionResult,
)
from btx_omni.ai.gemini import GeminiProvider
from btx_omni.modules.intelligence.technical_fit import (
    TechnicalDecompositionService,
    TechnicalMatchStatus,
)
from btx_omni.providers.sample.environment import build_sample_environment


class _Models:
    def __init__(self, text: str) -> None:
        self.text = text

    def generate_content(self, **_: object) -> object:
        return type("Response", (), {"text": self.text})()


class _Client:
    def __init__(self, text: str) -> None:
        self.models = _Models(text)

    def close(self) -> None:
        pass


def request() -> TechnicalDecompositionRequest:
    return TechnicalDecompositionRequest(
        "award-1", "CONTRACT_AWARD", "Boeing", "Program X", "Defense",
        (PublicEvidenceRecord("ev-1", "Award supports Program X", "Award issued for increased Program X production.", "https://example.test/award", "official"),),
    )


def service() -> TechnicalDecompositionService:
    sample = build_sample_environment()
    return TechnicalDecompositionService(components=sample.component_classes, business_units=sample.business_units)


def candidate(name: str, basis: TechnicalBasis = TechnicalBasis.MODEL_INFERRED) -> TechnicalCandidate:
    return TechnicalCandidate(name, basis, "Engineering relevance.", "Public award evidence supports the program context.", ("ev-1",))


def test_contract_award_candidate_matching_and_bu_derivation() -> None:
    result = TechnicalDecompositionResult("Program X award.", component_candidates=(candidate("actuator housing"), candidate("landing gear structural component"), candidate("mission planning software")))
    class Provider:
        configured = True
        config = type("Config", (), {"model": "fake"})()
        def decompose_technical_opportunity(self, _: object) -> TechnicalDecompositionResult: return result
    projection = service().process(request(), Provider())
    assert projection.provider_status.value == "AVAILABLE"
    assert projection.matches[0].status is TechnicalMatchStatus.MATCHED
    assert projection.matches[0].component_id == "cc-actuator"
    assert projection.matches[0].business_units
    assert projection.matches[1].status is TechnicalMatchStatus.POSSIBLE_MATCH_REVIEW_REQUIRED
    assert projection.matches[2].status is TechnicalMatchStatus.NO_MATCH


def test_only_controlled_aliases_can_match() -> None:
    assert service().match(candidate("hydraulic manifold", TechnicalBasis.SOURCE_STATED)).status is TechnicalMatchStatus.MATCHED
    assert service().match(candidate("precision widget housing")).status is TechnicalMatchStatus.POSSIBLE_MATCH_REVIEW_REQUIRED


def test_cache_hash_changes_with_evidence_and_contract() -> None:
    first = request()
    changed = TechnicalDecompositionRequest("award-1", "CONTRACT_AWARD", "Boeing", "Program X", "Defense", (PublicEvidenceRecord("ev-1", "Award supports Program X", "Changed public evidence.", None),), prompt_version="technical-decomposition-prompt-v2")
    assert TechnicalDecompositionService.cache_key(first) != TechnicalDecompositionService.cache_key(changed)


def test_gemini_schema_rejects_extra_fields_and_preserves_basis() -> None:
    payload = {"event_summary": "Award.", "product_candidates": [], "program_candidates": [], "technical_systems": [], "component_candidates": [{"name": "actuator housing", "basis": "MODEL_INFERRED", "reason": "plausible", "source_support": "not stated", "evidence_ids": ["ev-1"]}], "uncertainties": []}
    provider = GeminiProvider(AiConfig("gemini", "key", "fake", "developer", None, "global", 5), _Client(json.dumps(payload)))
    result = provider.decompose_technical_opportunity(request())
    assert result.component_candidates[0].basis is TechnicalBasis.MODEL_INFERRED
    payload["btx_component_id"] = "cc-actuator"
    bad = GeminiProvider(AiConfig("gemini", "key", "fake", "developer", None, "global", 5), _Client(json.dumps(payload)))
    with pytest.raises(ValueError, match="unsupported fields"):
        bad.decompose_technical_opportunity(request())


def test_bounds_reject_oversized_or_unapproved_gemini_shape() -> None:
    with pytest.raises(ValueError):
        TechnicalDecompositionResult("x" * 1201)
    with pytest.raises(ValueError):
        TechnicalCandidate("x" * 501, TechnicalBasis.SOURCE_STATED, "reason", "support")
