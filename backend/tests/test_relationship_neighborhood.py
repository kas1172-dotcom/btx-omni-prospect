from dataclasses import replace
from datetime import date

import pytest

from btx_omni.modules.relationships.neighborhood import project_neighborhood
from btx_omni.modules.relationships.routes import (
    CanonicalRouteGraph,
    RouteEdge,
    RouteNode,
    RouteQuery,
)

NOW = date(2026, 9, 8)


def fixture(pairs):
    nodes = {key: RouteNode('SAMPLE', 'role_target', key, 'Fixture ' + key, 'a') for pair in pairs for key in pair}
    edges = tuple(RouteEdge(f'{a}-{b}', nodes[a].id, nodes[b].id, 'EXPLICIT_INTRODUCTION', (f'record-{a}-{b}',),
                            (f'lineage-{a}-{b}',), ('authored-fixture',), 'POC_SCENARIO_RECORD', NOW,
                            account_id='a', valid_until=date(2027, 1, 1)) for a, b in pairs)
    graph = CanonicalRouteGraph(tuple(nodes.values()), edges, 'fixture-revision')
    query = RouteQuery('SAMPLE', nodes['a'].id, frozenset(), 'documented_access', NOW, frozenset({'a'}))
    return graph, query, nodes


def test_two_hops_and_collapse_preserve_shared_expansion_connection_and_path_membership():
    graph, query, nodes = fixture([('a', 'b'), ('b', 'c'), ('c', 'd'), ('d', 'e'), ('c', 'x'), ('x', 'e')])
    base = project_neighborhood(graph, query, [], None)
    assert {item['id'] for item in base['edges']} == {'a-b', 'b-c'}
    selected = {'path_id': 'selected', 'node_ids': (nodes['a'].id, nodes['b'].id), 'edge_ids': ('a-b',)}
    other = {**selected, 'path_id': 'other'}
    both = project_neighborhood(graph, query, [selected, other], selected, expanded_node_ids=(nodes['c'].id, nodes['d'].id))
    collapsed = project_neighborhood(graph, query, [selected, other], selected, expanded_node_ids=(nodes['d'].id,))
    ids = {item['id'] for item in collapsed['edges']}
    assert {'a-b', 'b-c', 'c-d', 'd-e'} <= ids and 'c-x' not in ids
    shared = next(item for item in both['edges'] if item['id'] == 'a-b')
    assert shared['path_ids'] == ['other', 'selected']
    assert 'expansion:' + nodes['d'].id in shared['expansion_owners']
    assert len(both['nodes']) == len({item['id'] for item in both['nodes']})
    assert collapsed['selected_path_id'] == 'selected'


def test_view_pages_keep_complete_selected_path_and_are_insertion_order_stable():
    pairs = [('a', f'n{i:02}') for i in range(20)]
    graph, query, nodes = fixture(pairs)
    selected = {'path_id': 'selected', 'node_ids': (nodes['a'].id, nodes['n00'].id), 'edge_ids': ('a-n00',)}
    base = project_neighborhood(graph, query, [selected], selected, node_budget=7, edge_budget=6)
    all_edges = set()
    for page in range(base['page_count']):
        current = project_neighborhood(graph, query, [selected], selected, node_budget=7, edge_budget=6, page=page)
        assert len(current['nodes']) <= 7 and len(current['edges']) <= 6
        ids = {item['id'] for item in current['edges']}
        assert 'a-n00' in ids
        all_edges.update(ids)
    assert all_edges == set(graph.edges)
    reversed_graph = CanonicalRouteGraph(tuple(reversed(tuple(graph.nodes.values()))), tuple(reversed(tuple(graph.edges.values()))), graph.revision)
    reverse = project_neighborhood(reversed_graph, query, [selected], selected, node_budget=7, edge_budget=6)
    assert reverse['edges'] == base['edges'] and reverse['nodes'] == base['nodes']
    with pytest.raises(ValueError, match='page changed'):
        project_neighborhood(graph, query, [selected], selected, page=base['page_count'], node_budget=7, edge_budget=6)


def test_context_budgets_authorization_expiry_and_disconnected_anchors_are_not_hidden():
    graph, query, nodes = fixture([('a', 'b'), ('b', 'c'), ('foreign', 'other')])
    partial = project_neighborhood(graph, query, [], None, max_examined=1)
    assert partial['context_complete'] is False and partial['context_stop_reason'] == 'EXPANSION_LIMIT'
    assert partial['context_examined_count'] == 1
    with pytest.raises(ValueError, match='no permitted connection'):
        project_neighborhood(graph, query, [], None, expanded_node_ids=(nodes['foreign'].id,))
    with pytest.raises(PermissionError):
        project_neighborhood(graph, replace(query, authorized_account_ids=frozenset()), [], None)
    expired = CanonicalRouteGraph(tuple(graph.nodes.values()), tuple(replace(e, valid_until=date(2026, 1, 1)) for e in graph.edges.values()), graph.revision)
    assert project_neighborhood(expired, query, [], None)['edges'] == []


def test_parallel_semantic_predicates_remain_separate_context_assertions():
    account = RouteNode('SAMPLE', 'account', 'a', 'Account', 'a')
    component = RouteNode('SAMPLE', 'component_class', 'c', 'Component', 'a')
    facility = RouteNode('SAMPLE', 'btx_facility', 'f', 'Facility')
    structure = RouteEdge('structure', account.id, component.id, 'ACCOUNT_COMPONENT', ('c',), ('c',), (), 'POC_ASSUMPTION', NOW)
    fit = RouteEdge('fit', facility.id, component.id, 'PLAUSIBLE_CAPABILITY_FIT', ('fit-record',), ('fit',), (), 'ANALYST_INFERENCE', NOW, inverse_modes=('commercial_fit',))
    experience = replace(fit, id='experience', predicate='PRODUCED_ACCEPTED_COMPONENT', evidence_ids=('work',), lineage_groups=('work',), truth_class='POC_SCENARIO_RECORD')
    graph = CanonicalRouteGraph((account, component, facility), (structure, fit, experience), 'revision')
    query = RouteQuery('SAMPLE', account.id, frozenset({facility.id}), 'commercial_fit', NOW, frozenset({'a'}))
    view = project_neighborhood(graph, query, [], None)
    assert {e['id'] for e in view['edges']} == {'structure', 'fit', 'experience'}
    assert len(view['nodes']) == 3
