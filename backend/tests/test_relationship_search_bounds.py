"""Small independent graph oracles for the actual canonical traversal method."""
from collections import defaultdict

from btx_omni.domain.common import EvidenceState
from btx_omni.modules.relationships.service import (
    RelationshipEntity,
    RelationshipIntelligenceService,
)


def graph(edges):
    service = RelationshipIntelligenceService.__new__(RelationshipIntelligenceService)
    ids = {value for a, b, _ in edges for value in (a, b)}
    service.entities = {("account", key): RelationshipEntity("account", key, key) for key in ids}
    hops = []
    for a, b, key in edges:
        service._add(hops, service.entities[("account", a)], key, service.entities[("account", b)], EvidenceState.CONFIRMED, None, source_ids=(key,))
    service.adjacency = defaultdict(list)
    for hop in hops:
        service.adjacency[hop.from_entity].append(hop)
    for values in service.adjacency.values():
        values.sort(key=lambda hop: (hop.relationship_type, hop.to_entity.kind, hop.to_entity.id, hop.assertion_id, hop.inverse))
    return service


def test_path_local_visitation_preserves_parallel_alternatives_and_excludes_cycles():
    service = graph([("a", "b", "ab1"), ("a", "b", "ab2"), ("a", "c", "ac"), ("b", "d", "bd"), ("c", "d", "cd"), ("b", "a", "cycle")])
    result = service.account_relationships("a", depth=3)
    routes = [p for p in result["paths"] if p["target_entity"].id == "d"]
    assert {tuple(h.relationship_type for h in p["hops"]) for p in routes} == {("ab1", "bd"), ("ab2", "bd"), ("ac", "cd")}
    for path in result["paths"]:
        nodes = [path["source_entity"].id, *(h.to_entity.id for h in path["hops"])]
        assert len(nodes) == len(set(nodes))
    assert result["search_complete"]


def test_five_assertion_route_is_found_at_six_not_four():
    service = graph([(str(i), str(i + 1), f"e{i}") for i in range(5)])
    assert not any(p["target_entity"].id == "5" for p in service.account_relationships("0", depth=4)["paths"])
    result = service.account_relationships("0", depth=6)
    assert len(next(p for p in result["paths"] if p["target_entity"].id == "5")["hops"]) == 5
    assert result["searched_depth"] == 6


def test_caps_are_explicit_and_insertion_order_does_not_change_assertion_ids():
    edges = [("a", "b", "ab"), ("a", "c", "ac"), ("b", "d", "bd")]
    first, second = graph(edges), graph(list(reversed(edges)))
    assert [p["path_id"] for p in first.account_relationships("a")["paths"]] == [p["path_id"] for p in second.account_relationships("a")["paths"]]
    result = first.account_relationships("a", max_paths=1)
    assert not result["search_complete"] and result["stop_reason"] == "CANDIDATE_LIMIT"
    result = first.account_relationships("a", max_expansions=1)
    assert not result["search_complete"] and result["stop_reason"] == "EXPANSION_LIMIT"
    assert result["examined_count"] == 1
