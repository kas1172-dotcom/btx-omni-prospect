"""Explicit isolated D2 scenario uses the normal importer and canonical service."""
from copy import deepcopy
from datetime import date

import pytest
from sqlalchemy import create_engine
from test_commercial_persistence import importer_package

from btx_omni.modules.assistant.relationship_context import (
    selected_relationship_context,
)
from btx_omni.modules.commercial.projection import project_commercial_records
from btx_omni.modules.relationships import canonical_projection
from btx_omni.modules.relationships.routes import RouteQuery
from btx_omni.modules.relationships.service import RelationshipIntelligenceService
from btx_omni.persistence import models
from btx_omni.persistence.commercial_import import CommercialImportRepository
from btx_omni.providers.sample.environment import build_sample_environment


def test_d2_longer_supported_route_beats_short_inference_after_real_import(tmp_path, monkeypatch):
    package = importer_package()
    account = package["accounts"][0]
    account["programs"][0]["source_ids"] = []
    account["components"][0].update(btx_facility_id="BTX-FAC-BU-ERA", source_ids=[])
    account["order_lines"][0]["btx_facility_id"] = "BTX-FAC-BU-ERA"
    catalog = deepcopy(canonical_projection.relationship_catalog())
    catalog["edges"] = [{"edge_id": "fixture:d2:fit", "from_id": "BTX-FAC-BU-ERA", "to_id": "c", "component_id": "c", "predicate": "PLAUSIBLE_CAPABILITY_FIT", "evidence_ids": ["c"], "truth_class": "ANALYST_INFERENCE", "observed_on": "2026-08-20"}]
    monkeypatch.setattr(canonical_projection, "relationship_catalog", lambda: catalog)
    engine = create_engine(f"sqlite:///{tmp_path / 'd2.sqlite'}")
    models.metadata.create_all(engine)
    repo = CommercialImportRepository(engine)
    original = build_sample_environment()
    repo.import_package(package, {"test-account": "honeywell"}, original, apply=True)
    replay = repo.import_package(package, {"test-account": "honeywell"}, original, apply=True)
    assert replay["created"] == replay["updated"] == 0
    revision, records = repo.snapshot()
    sample = project_commercial_records(original, records, revision=revision)
    query = RouteQuery("SAMPLE", "SAMPLE:account:honeywell", frozenset(("SAMPLE:btx_facility:era-elk-grove",)), "commercial_fit", date(2026, 8, 31), frozenset(("honeywell",)), "c")
    result = RelationshipIntelligenceService(sample).ranked_routes(query)
    routes = result["evaluated_routes"]
    longer = next(r for r in routes if r["hop_count"] == 3 and r["factors"].bottleneck == 2)
    shorter = next(r for r in routes if r["hop_count"] == 2 and r["factors"].bottleneck == 1)
    assert longer["utility"] > shorter["utility"]
    assert "v" in longer["evidence_ids"]  # persisted accepted revenue record
    assert all(r["factors"].bottleneck >= 2 for g in result["groups"].values() for r in g["routes"])
    assert records["honeywell"]["ttm_summary"]["revenue_minor"] == 400
    assert len({n["id"] for n in result["graph"]["nodes"]}) == len(result["graph"]["nodes"])
    expanded = RelationshipIntelligenceService(sample).ranked_routes(query, selected_path_id=longer['path_id'],
        expanded_node_ids=('SAMPLE:component_class:c',), expected_graph_revision=result['eligible_graph_revision'])
    assert expanded['graph']['selected_path_id'] == longer['path_id']
    assert expanded['graph']['expanded_node_ids'] == ['SAMPLE:component_class:c']
    assert expanded['evaluated_routes'][0]['utility'] == routes[0]['utility']
    record_context = RelationshipIntelligenceService(sample).ranked_routes(query, selected_path_id=longer['path_id'],
        include_record_context=True, node_budget=80, edge_budget=160)
    assert record_context['graph']['selected_path_id'] == longer['path_id']
    assert record_context['groups'] == result['groups']
    references = [edge for edge in record_context['graph']['edges'] if edge['predicate'].startswith('RECORD_')]
    assert references and all(not edge['path_ids'] for edge in references)
    assert record_context['projection_counts']['record_projection']['version'] == 'BTX_GRAPH_RECORD_REFERENCES_1'
    with pytest.raises(ValueError, match='evidence changed'):
        RelationshipIntelligenceService(sample).ranked_routes(query, expected_graph_revision='retired-revision')
    historical_graph, historical_metadata = canonical_projection.project_route_graph(sample, as_of=date(2026, 8, 5))
    current_graph, _ = canonical_projection.project_route_graph(sample, as_of=date(2026, 8, 31))
    assert historical_graph.revision != current_graph.revision
    assert historical_metadata['constraints'] == {}
    assert set(result['temporal_limits']) == {'honeywell'}
    selection = {"source_account_id": "honeywell", "target_ids": list(query.target_ids), "mode": query.mode, "as_of": query.as_of,
                 "depth": 4, "path_id": longer["path_id"], "graph_revision": result["eligible_graph_revision"], "source_component_id": "c"}
    explanation = selected_relationship_context(sample, selection, account_id="honeywell")
    assert explanation["route"]["utility"] == longer["utility"]
    assert "USD 4.00" in explanation["content"]
    assert "USD 4.00" in explanation["expanded_content"] and "2026-08-12" in explanation["expanded_content"]
    assert any(record['record'].get('revenue_minor') == 400 for record in explanation['evidence_records'])
    with pytest.raises(ValueError, match="stale"):
        selected_relationship_context(sample, {**selection, "graph_revision": "old"}, account_id="honeywell")
    with pytest.raises(ValueError, match="scope"):
        selected_relationship_context(sample, selection, account_id="boeing")
    engine.dispose()
