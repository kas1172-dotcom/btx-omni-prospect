import pytest
from httpx import ASGITransport, AsyncClient

from btx_omni.app import create_app
from btx_omni.domain.common import EvidenceState
from btx_omni.modules.relationships.service import (
    RelationshipIntelligenceService,
    presentation_state,
)
from btx_omni.providers.research import relationships
from btx_omni.providers.sample.environment import build_sample_environment


def test_explicit_edges_are_resolved_and_classified() -> None:
    sample = build_sample_environment()
    accounts = {item.id for item in sample.accounts}
    programs = {item.id for item in sample.programs}
    assert len(sample.relationship_edges) == 35
    assert {item.edge_type for item in sample.relationship_edges} == {"PARENT_CHILD", "SHARED_PROGRAM", "COMPETITOR_ON_PROGRAM", "SHARED_PRIME", "GEOGRAPHIC_CLUSTER"}
    assert all(item.from_account_id in accounts and item.to_account_id in accounts and (item.program_id is None or item.program_id in programs) for item in sample.relationship_edges)
    assert all(item.provenance.source_record_id for item in sample.relationship_edges)


def test_relationship_loader_rejects_semantic_duplicates(monkeypatch) -> None:
    payload = {"sources": {"S": {}}, "edges": [
        {"edge_id": "one", "from_account_id": "a", "to_account_id": "b", "edge_type": "SHARED_PROGRAM", "direction": "bidirectional", "strength": "STRONG", "evidence_state": "CONFIRMED", "source_ids": ["S"]},
        {"edge_id": "two", "from_account_id": "b", "to_account_id": "a", "edge_type": "SHARED_PROGRAM", "direction": "bidirectional", "strength": "STRONG", "evidence_state": "CONFIRMED", "source_ids": ["S"]},
    ]}
    monkeypatch.setattr(relationships, "document", lambda _: payload)
    with pytest.raises(ValueError, match="duplicates"):
        relationships.load_relationship_edges(account_ids={"a", "b"}, program_ids=set())


def test_bounded_paths_cover_typed_commercial_and_capability_links() -> None:
    service = RelationshipIntelligenceService(build_sample_environment())
    result = service.account_relationships("lockheed-martin", depth=4)
    types = {hop.relationship_type for path in result["paths"] for hop in path["hops"]}
    assert {"QUOTED_WITH", "ORDERED_WITH", "PARTICIPATES_IN", "REQUIRES_COMPONENT_CLASS", "CAPABILITY_MATCH"} <= types
    assert any(path["target_entity"].kind == "business_unit" for path in result["paths"])
    assert len({path["path_id"] for path in result["paths"]}) == len(result["paths"])


def test_warm_path_requires_an_explicit_evidenced_edge() -> None:
    result = RelationshipIntelligenceService(build_sample_environment()).account_relationships("spirit-aerosystems", depth=2)
    paths = [path for path in result["paths"] if path["target_entity"].id == "boeing" and path["hops"][0].relationship_type == "PARENT_CHILD"]
    assert paths and paths[0]["overall_evidence_state"] is EvidenceState.CONFIRMED
    assert paths[0]["presentation_state"] == "validated"
    assert any(path["target_entity"].kind in {"contact", "business_unit"} and path["presentation_state"] == "validated" for path in result["paths"])


def test_evidence_presentation_mapping_is_deterministic() -> None:
    assert presentation_state(EvidenceState.CONFIRMED) == "validated"
    assert presentation_state(EvidenceState.INFERRED) == "needs_validation"
    assert presentation_state(EvidenceState.MISSING) == presentation_state(EvidenceState.CONFLICTING) == "unusable"


@pytest.mark.asyncio
async def test_account_relationship_api_is_typed_and_bounded() -> None:
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as client:
        response = await client.get("/api/accounts/spirit-aerosystems/relationships", params={"depth": 2})
        missing = await client.get("/api/accounts/not-real/relationships")
    assert response.status_code == 200 and missing.status_code == 404
    payload = response.json()
    assert payload["account"]["kind"] == "account" and payload["max_depth"] == 2
    assert any(path["presentation_state"] == "validated" for path in payload["paths"])
