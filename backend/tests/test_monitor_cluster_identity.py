from dataclasses import replace

import pytest
from test_monitor import make_event, make_observation

from btx_omni.monitor.clustering import cluster_event, cluster_key


def test_distinct_records_with_same_subject_type_and_unknown_date_do_not_corroborate():
    first = replace(make_event(), event_date=None)
    second = replace(first, id='different-event', provenance=replace(first.provenance, source_record_id='different-notice'))
    assert cluster_key(first) != cluster_key(second)
    cluster = cluster_event(first, make_observation()).cluster
    with pytest.raises(ValueError, match='different source record'):
        cluster_event(second, make_observation(), cluster)


def test_amended_source_record_keeps_cluster_and_prior_version_lineage_without_new_event_count():
    first = make_event()
    amended = replace(first, id='amended-event', event_date=None)
    original = cluster_event(first, make_observation())
    changed = cluster_event(amended, replace(make_observation('changed'), id='obs-changed'), original.cluster)
    assert not changed.created and changed.source_record_changed
    assert changed.cluster.event_id == 'amended-event'
    assert changed.cluster.related_event_ids == (first.id,)
    assert changed.cluster.observation_ids == ('obs-1', 'obs-changed')
    replay = cluster_event(amended, replace(make_observation('changed'), id='obs-changed'), changed.cluster)
    assert replay.cluster == changed.cluster


def test_different_publishers_native_ids_are_namespaced_not_implicit_independence():
    first = make_event()
    copy = replace(first, provenance=replace(first.provenance, source_system='another-publisher'))
    assert cluster_key(first) != cluster_key(copy)
