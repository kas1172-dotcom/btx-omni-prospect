from datetime import UTC, datetime

from btx_omni.core.classification import Classification
from btx_omni.core.provenance import Provenance
from btx_omni.domain.alerts import CommercialAlert
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.monitor.clustering import cluster_event, observation_changed
from btx_omni.monitor.contracts import (
    EntityResolution,
    EventEvidence,
    IntelligenceEvent,
    NormalizedClaim,
    ProgramResolution,
    RawEvidenceReference,
    SourceHealth,
    SourceIdentity,
    SourceObservation,
    SourceVersion,
)
from btx_omni.monitor.health import is_source_health_warning
from btx_omni.monitor.ontology import EventType, ResolutionState, SourceHealthState
from btx_omni.monitor.packs import PACKS
from btx_omni.monitor.pipeline import MonitorPipeline

NOW = datetime(2026, 1, 2, tzinfo=UTC)


def make_observation(content_hash: str = "a") -> SourceObservation:
    identity = SourceIdentity("sam_gov", "notice-1", (("notice_id", "notice-1"),))
    version = SourceVersion("notice-1", "v1", content_hash, NOW, NOW)
    evidence = RawEvidenceReference("ev-1", identity, version, "https://example.test/notice-1", NOW, "Award notice")
    return SourceObservation("obs-1", identity, version, NOW, "Award", evidence, NOW)


def make_event() -> IntelligenceEvent:
    provenance = Provenance("sam_gov", "notice-1", "https://example.test/notice-1", NOW, NOW, Classification.PUBLIC, EvidenceState.CONFIRMED, DataMode.SAMPLE, True)
    subject = EntityResolution("Example Defense", "acct-1", ResolutionState.RESOLVED, "uei_exact", "exact UEI")
    program = ProgramResolution("Platform X", "program-1", ResolutionState.RESOLVED, "alias_exact", "governed program alias")
    claim = NormalizedClaim("awardee", "Example Defense", ("ev-1",), "field_map", "structured source field")
    return IntelligenceEvent("event-1", EventType.CONTRACT_AWARD, (subject,), (), program, "US", NOW, None, None, (claim,), (EventEvidence("ev-1", ("awardee",), "PRIMARY"),), provenance, "authoritative government record", "deterministic field mapping", "exact UEI", "one authoritative source", ResolutionState.RESOLVED)


def test_event_creation_retains_evidence_lineage_and_matching_boundary() -> None:
    event = make_event()
    assert event.evidence[0].evidence_id == "ev-1"
    assert MonitorPipeline(PACKS["defense"]).output_for_matching(event) is event


def test_duplicate_observations_cluster_and_changed_records_are_visible() -> None:
    event, first = make_event(), make_observation()
    initial = cluster_event(event, first)
    duplicate = cluster_event(event, make_observation(), initial.cluster)
    changed = make_observation("b")
    assert not duplicate.created and duplicate.cluster.observation_ids == ("obs-1",)
    assert observation_changed(first, changed)


def test_source_health_is_not_a_commercial_alert() -> None:
    health = SourceHealth("sam_gov", SourceHealthState.WARNING, NOW, None, "SOURCE_HEALTH_WARNING", "cursor stalled")
    assert is_source_health_warning(health)
    assert not isinstance(health, CommercialAlert)


def test_industry_packs_keep_generic_core_free_of_btx_strings() -> None:
    assert "sam_gov" in PACKS["defense"].source_ids
    assert MonitorPipeline(PACKS["robotics"]).pack.id == "robotics"
