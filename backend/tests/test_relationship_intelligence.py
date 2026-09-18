import pytest
from httpx import ASGITransport, AsyncClient

from btx_omni.api.accounts import RELATIONSHIP_REFERENCE_PATH_LIMIT
from btx_omni.app import create_app
from btx_omni.domain.common import EvidenceState
from btx_omni.modules.relationships.presentation import (
    SellerRelationshipPresentationService,
    seller_relationship_semantics,
    seller_route_evidence_label,
    seller_route_predicate_label,
)
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


def test_source_less_explicit_edges_need_validation_even_if_the_legacy_state_is_confirmed() -> None:
    result = RelationshipIntelligenceService(build_sample_environment()).account_relationships("spirit-aerosystems", depth=1)
    geographic = next(path for path in result["direct_relationships"] if path["hops"][0].relationship_type == "GEOGRAPHIC_CLUSTER_REVERSE")
    assert geographic["overall_evidence_state"] is EvidenceState.CONFIRMED
    assert geographic["presentation_state"] == "needs_validation"
    assert geographic["hops"][0].presentation_state == "needs_validation"


def test_evidence_presentation_mapping_is_deterministic() -> None:
    assert presentation_state(EvidenceState.CONFIRMED) == "validated"
    assert presentation_state(EvidenceState.INFERRED) == "needs_validation"
    assert presentation_state(EvidenceState.MISSING) == presentation_state(EvidenceState.CONFLICTING) == "unusable"


def test_seller_relationship_policy_is_deterministic_and_bounded() -> None:
    label, why, move = seller_relationship_semantics("SHARED_PROGRAM")
    assert label == "Shared program"
    assert "canonically associated" in why
    assert move == "Inspect the shared program evidence before using it to shape outreach."
    assert not any(term in f"{label} {why} {move}".lower() for term in ("warm", "introduction", "strong", "confidence"))

    reverse = seller_relationship_semantics("PARENT_CHILD_REVERSE")
    assert reverse == seller_relationship_semantics("PARENT_CHILD")
    fallback = seller_relationship_semantics("UNRECOGNIZED_CANONICAL_TYPE")
    assert fallback[0] == "Recorded relationship"
    assert "Inspect the evidence" in fallback[2]
    assert seller_route_predicate_label("CAPABILITY_MATCH") == "BTX capability alignment"
    assert seller_route_evidence_label("INFERRED") == "Possible route to investigate"
    assert seller_route_evidence_label("MISSING") == "Not currently actionable"


def test_seller_projection_preserves_raw_paths_and_evidence_without_strength() -> None:
    raw = RelationshipIntelligenceService(build_sample_environment()).account_relationships("lockheed-martin", depth=2)
    raw_path_ids = [path["path_id"] for path in raw["paths"]]
    projected = SellerRelationshipPresentationService().present(raw)
    assert [path["path_id"] for path in raw["paths"]] == raw_path_ids
    assert len(projected["seller_direct_relationships"]) == len(raw["direct_relationships"])
    assert len(projected["seller_paths"]) == len(raw["paths"])
    direct = projected["seller_direct_relationships"][0]
    multi_hop = next(path for path in projected["seller_paths"] if not path["direct"])
    for path in (direct, multi_hop):
        assert path["summary"] and path["connection_label"] and path["why_it_matters"]
        assert path["suggested_move"]
        assert path["evidence"]
        assert all("evidence_state" in item and "source_record_id" in item for item in path["evidence"])
        assert "strength" not in path and "confidence" not in path
        assert "warm" not in path["suggested_move"].lower()
        assert "introduction" not in path["suggested_move"].lower()
    assert direct["direct"] is True and direct["step_count"] == 1
    assert multi_hop["direct"] is False and multi_hop["step_count"] == 2
    assert all(step["display_name"] not in {"quote", "order"} for path in projected["seller_paths"] for step in path["steps"])
    seller = projected["seller_projection"]
    assert seller["returned_count"] <= 12
    assert seller["unusable_count"] >= 0
    assert not any(path["presentation_state"] == "unusable" for path in seller["validated"] + seller["needs_validation"])
    assert all("seller_rationale" in path for path in seller["validated"] + seller["needs_validation"])
    assert all("validation_requirements" in path for path in seller["validated"] + seller["needs_validation"])


def test_needs_validation_paths_expose_governed_requirements() -> None:
    raw = RelationshipIntelligenceService(build_sample_environment()).account_relationships(
        "spirit-aerosystems", depth=1
    )
    raw_path = next(
        item
        for item in raw["direct_relationships"]
        if item["hops"][0].relationship_type == "GEOGRAPHIC_CLUSTER_REVERSE"
    )
    path = SellerRelationshipPresentationService().present_path(raw_path)
    assert path["validation_requirements"] == [
        "Attach or confirm the source record for the recorded relationship."
    ]


def test_seller_projection_prioritizes_governed_state_directness_sources_and_stability() -> None:
    service = RelationshipIntelligenceService(build_sample_environment())
    raw = service.account_relationships("spirit-aerosystems", depth=2)
    first = SellerRelationshipPresentationService().present(raw)["seller_projection"]
    second = SellerRelationshipPresentationService().present(raw)["seller_projection"]
    first_paths = first["validated"] + first["needs_validation"]
    second_paths = second["validated"] + second["needs_validation"]
    assert [path["path_id"] for path in first_paths] == [path["path_id"] for path in second_paths]
    assert not first["needs_validation"] or not first["validated"] or first_paths.index(first["needs_validation"][0]) >= len(first["validated"])
    for paths in (first["validated"], first["needs_validation"]):
        assert [path["direct"] for path in paths] == sorted((path["direct"] for path in paths), reverse=True)


@pytest.mark.asyncio
async def test_account_relationship_api_is_typed_and_bounded() -> None:
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as client:
        response = await client.get("/api/accounts/spirit-aerosystems/relationships", params={"depth": 2})
        missing = await client.get("/api/accounts/not-real/relationships")
    assert response.status_code == 200 and missing.status_code == 404
    payload = response.json()
    assert len(payload["paths"]) <= RELATIONSHIP_REFERENCE_PATH_LIMIT
    assert payload["account"]["kind"] == "account" and payload["max_depth"] == 2
    assert any(path["presentation_state"] == "validated" for path in payload["paths"])
    multi_hop = next(path for path in payload["paths"] if len(path["hops"]) == 2)
    assert multi_hop["path_id"] and all(hop["presentation_state"] for hop in multi_hop["hops"])
    assert len(payload["seller_direct_relationships"]) == len(payload["direct_relationships"])
    assert len(payload["seller_paths"]) == len(payload["paths"])
    assert payload["seller_projection"]["returned_count"] <= 12
    assert not any(path["presentation_state"] == "unusable" for path in payload["seller_projection"]["validated"] + payload["seller_projection"]["needs_validation"])
    assert "relationship_type" in payload["paths"][0]["hops"][0]
    assert "connection_label" in payload["seller_paths"][0]
    assert "strength" not in payload["seller_paths"][0]
