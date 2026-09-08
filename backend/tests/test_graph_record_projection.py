from dataclasses import replace
from datetime import date

from btx_omni.modules.commercial.projection import project_commercial_records
from btx_omni.modules.relationships.canonical_projection import project_route_graph
from btx_omni.modules.relationships.record_projection import PREDICATES
from btx_omni.modules.relationships.routes import CanonicalRouteGraph, RouteQuery
from btx_omni.persistence.import_commercial_sample import (
    ACCOUNT_CROSSWALK,
    load_release_sample,
)
from btx_omni.providers.sample.environment import build_sample_environment


def sample():
    package = load_release_sample()
    accounts = {ACCOUNT_CROSSWALK[item['account_id']]: item for item in package['accounts']}
    return project_commercial_records(build_sample_environment(), accounts, revision='fixture-record-projection')


def test_full_source_records_have_typed_context_without_changing_route_strength():
    source = sample()
    graph, metadata = project_route_graph(source, as_of=date(2026, 8, 31))
    refs = {key: edge for key, edge in graph.edges.items() if edge.predicate in PREDICATES}
    assert refs and len(refs) == metadata['record_projection']['edge_count']
    connected = {node for edge in refs.values() for node in (edge.source, edge.target)}
    for node in graph.nodes.values():
        if node.kind in {'rfqs', 'quotes', 'quote_revisions', 'quote_lines', 'agreements', 'orders', 'order_lines',
                         'shipments', 'acceptances', 'revenue_events', 'invoices', 'payments', 'interactions', 'role_target'}:
            assert node.id in connected
    assert all(graph.nodes[edge.target].kind != 'contact_candidate' for edge in refs.values())
    assert all(edge.account_id == graph.nodes[edge.source].account_id for edge in refs.values())
    query = RouteQuery('SAMPLE', 'SAMPLE:account:kla', frozenset({'SAMPLE:account:spacex'}),
                       'cross_account_experience', date(2026, 8, 31), frozenset({'kla', 'spacex'}), max_depth=6)
    baseline = CanonicalRouteGraph(tuple(graph.nodes.values()), tuple(edge for key, edge in graph.edges.items() if key not in refs), graph.revision)
    ranked = graph.search(query)
    assert ranked['search_complete'] and baseline.search(query)['groups'] == ranked['groups']
    assert all(not set(route['edge_ids']) & refs.keys() for route in ranked['evaluated_routes'])


def test_context_ids_replay_stably_and_historical_cancellation_date_is_real():
    source = sample()
    graph, _ = project_route_graph(source, as_of=date(2026, 8, 31))
    replay, _ = project_route_graph(replace(source, commercial_ledgers=dict(reversed(list(source.commercial_ledgers.items())))), as_of=date(2026, 8, 31))
    assert graph.edges == replay.edges
    cancellations = [edge for edge in graph.edges.values() if edge.source.startswith('SAMPLE:cancellations:')]
    assert cancellations and all(edge.observed_on == date(2025, 12, 15) for edge in cancellations)
    query = RouteQuery('SAMPLE', 'SAMPLE:account:emerson', frozenset(), 'commercial_fit', date(2025, 11, 30), frozenset({'emerson'}))
    assert all(not graph._edge_allowed(edge, False, query) for edge in cancellations)
    denied = replace(query, as_of=date(2026, 8, 31), authorized_account_ids=frozenset({'kla'}))
    assert all(not graph._edge_allowed(edge, False, denied) for edge in cancellations)
