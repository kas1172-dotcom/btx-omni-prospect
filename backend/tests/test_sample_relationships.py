from btx_omni.core.clock import as_of_date
from btx_omni.modules.relationships.routes import RouteQuery
from btx_omni.modules.relationships.service import RelationshipIntelligenceService
from btx_omni.providers.sample.enhancement import enhance_environment
from btx_omni.providers.sample.environment import build_sample_environment


def test_j8_j9_longer_evidenced_route_beats_shorter_older_route():
    sample = enhance_environment(build_sample_environment())
    aid = 'demo-regional-defense'
    query = RouteQuery('SAMPLE', f'SAMPLE:account:{aid}', frozenset({'SAMPLE:btx_facility:apm-rochester'}),
        'commercial_fit', as_of_date(), frozenset(a.id for a in sample.accounts), max_depth=4, deadline_seconds=2)
    result = RelationshipIntelligenceService(sample).ranked_routes(query)
    routes = result['evaluated_routes']
    assert {r['hop_count'] for r in routes} >= {2, 3, 4}
    assert routes[0]['hop_count'] == 4
    assert routes[0]['utility'] > max(r['utility'] for r in routes if r['hop_count'] == 2)
    assert result['rubric_version'].startswith('BTX_RELATIONSHIP_')
    assert all(r['weakest_link'] and len(r['node_ids']) == len(set(r['node_ids'])) for r in routes)
    assert len({r['path_id'] for r in routes}) == len(routes)
    assert sample.commercial_ledgers[aid]['unsupported_route_links'][0]['state'] == 'HYPOTHESIZED_UNSUPPORTED'
    assert all(a['source_record_id'] and a['observed_on'] for r in routes for a in r['assertions'])
