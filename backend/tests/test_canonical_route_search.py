"""Independent small-graph oracle and authorization/temporal search gates."""
from dataclasses import replace
from datetime import date
from itertools import pairwise, permutations

import pytest

from btx_omni.modules.relationships.routes import (
    CanonicalRouteGraph,
    RouteEdge,
    RouteNode,
    RouteQuery,
)

AS_OF = date(2026, 9, 7)


def access_graph():
    nodes = tuple(RouteNode("SAMPLE", "person", key, key, "account") for key in "abcd")
    by_key = {n.canonical_id: n.id for n in nodes}
    pairs = (("a", "b"), ("a", "c"), ("b", "c"), ("c", "b"), ("b", "d"), ("c", "d"), ("a", "b"))
    edges = tuple(RouteEdge(str(i), by_key[a], by_key[b], "EXPLICIT_INTRODUCTION", (f"e{i}",), (f"l{i}",), (f"s{i}",), "POC_SCENARIO_RECORD", AS_OF, account_id="account", valid_until=date(2026, 10, 1)) for i, (a, b) in enumerate(pairs))
    query = RouteQuery("SAMPLE", by_key["a"], frozenset((by_key["d"],)), "documented_access", AS_OF, frozenset(("account",)))
    return nodes, edges, query


def test_explicit_empty_targets_return_full_revision_scope_without_enumeration():
    nodes, edges, query = access_graph()
    graph = CanonicalRouteGraph(nodes, edges, 'empty-target-revision')
    query = replace(query, target_ids=frozenset())
    result = graph.search(query)
    assert result['search_complete'] and result['examined_count'] == result['candidate_count'] == 0
    assert result['eligible_graph_revision'] == 'empty-target-revision'
    assert result['rubric_version'] == 'BTX_RELATIONSHIP_POC_1'
    assert result['scope']['target_ids'] == []
    assert result['scope']['source_id'] == query.source_id
    with pytest.raises(PermissionError):
        graph.search(replace(query, authorized_account_ids=frozenset()))


def exhaustive_oracle(edges, source, targets, depth):
    # Deliberately independent permutation enumeration, not the service DFS.
    found = set()
    for length in range(1, depth + 1):
        for path in permutations(edges, length):
            if path[0].source != source or path[-1].target not in targets:
                continue
            if any(a.target != b.source for a, b in pairwise(path)):
                continue
            nodes = [source, *(e.target for e in path)]
            if len(nodes) == len(set(nodes)):
                found.add(tuple(e.id for e in path))
    return found


def test_actual_search_matches_exhaustive_oracle_parallel_edges_cycles_and_shared_nodes():
    nodes, edges, query = access_graph()
    result = CanonicalRouteGraph(nodes, edges, "revision").search(query)
    expected = exhaustive_oracle(edges, query.source_id, query.target_ids, query.max_depth)
    assert {tuple(p["edge_ids"]) for p in result["evaluated_routes"]} == expected
    assert result["search_complete"] and len(expected) == 6
    reverse = CanonicalRouteGraph(tuple(reversed(nodes)), tuple(reversed(edges)), "revision").search(query)
    assert result == reverse


@pytest.mark.parametrize("change", [{"max_expansions": 1}, {"max_candidates": 1}])
def test_budget_never_claims_complete(change):
    nodes, edges, query = access_graph()
    result = CanonicalRouteGraph(nodes, edges, "revision").search(replace(query, **change))
    assert not result["search_complete"] and result["stop_reason"] in {"EXPANSION_LIMIT", "CANDIDATE_LIMIT"}


def test_cancellation_and_denied_scope():
    nodes, edges, query = access_graph()
    graph = CanonicalRouteGraph(nodes, edges, "revision")
    assert graph.search(query, cancelled=lambda: True)["stop_reason"] == "CANCELLED"
    with pytest.raises(PermissionError):
        graph.search(replace(query, authorized_account_ids=frozenset()))
    with pytest.raises(PermissionError):
        graph.search(replace(query, scope_id="OTHER"))


@pytest.mark.parametrize("change", [{"valid_until": date(2026, 9, 6)}, {"valid_until": None}, {"observed_on": None}, {"evidence_ids": ()}, {"conflicting": True}])
def test_invalid_access_evidence_cannot_become_a_route(change):
    nodes, edges, query = access_graph()
    invalid = tuple(replace(e, **change) for e in edges)
    assert CanonicalRouteGraph(nodes, invalid, "revision").search(query)["candidate_count"] == 0


def test_inverse_not_implicitly_authorized_and_generic_hubs_excluded():
    nodes, edges, query = access_graph()
    graph = CanonicalRouteGraph(nodes, edges, "revision")
    assert graph.search(replace(query, source_id=next(iter(query.target_ids)), target_ids=frozenset((query.source_id,))))["candidate_count"] == 0
    replacement = {n.id: replace(n, kind="industry") if n.canonical_id in "bc" else n for n in nodes}
    remapped = tuple(replace(e, source=replacement[e.source].id, target=replacement[e.target].id) for e in edges)
    assert CanonicalRouteGraph(tuple(replacement.values()), remapped, "revision").search(query)["candidate_count"] == 0


def test_five_hop_path_requires_explicit_deeper_search():
    nodes = tuple(RouteNode("SAMPLE", "person", str(i), str(i), "account") for i in range(6))
    _, original, query = access_graph()
    edges = tuple(replace(original[0], id=str(i), source=nodes[i].id, target=nodes[i + 1].id) for i in range(5))
    query = replace(query, source_id=nodes[0].id, target_ids=frozenset((nodes[-1].id,)))
    graph = CanonicalRouteGraph(nodes, edges, "revision")
    assert graph.search(query)["candidate_count"] == 0
    deeper = graph.search(replace(query, max_depth=6))
    assert deeper["candidate_count"] == 1 and deeper["evaluated_routes"][0]["hop_count"] == 5
    assert deeper["searched_depth"] == 6
