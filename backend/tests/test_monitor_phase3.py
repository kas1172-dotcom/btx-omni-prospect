import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine

from btx_omni.core.classification import Classification
from btx_omni.core.config import Settings
from btx_omni.core.provenance import Provenance
from btx_omni.domain.accounts import AccountFacility
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.domain.markets import PRIMARY_MARKETS
from btx_omni.domain.programs import Program
from btx_omni.monitor.catalog import MonitorCatalog
from btx_omni.monitor.normalization import normalize_structured_observation
from btx_omni.monitor.ontology import ResolutionState, SellerRelevanceState
from btx_omni.monitor.policy import classify_markets, recency_state
from btx_omni.monitor.repository import MonitorRepository
from btx_omni.monitor.resolution import AccountWatchProfile
from btx_omni.monitor.service import MonitorService
from btx_omni.monitor.sources import REGISTRY, FdaAdapter
from btx_omni.persistence.models import metadata

NOW = datetime(2026, 8, 19, tzinfo=UTC)


def fake_get(payload: object, status: int = 200):
    def get(_url: str, _headers: dict[str, str]) -> tuple[int, bytes, dict[str, str]]:
        return status, json.dumps(payload).encode(), {}

    return get


def catalog() -> MonitorCatalog:
    public = Provenance("research", "catalog", "https://example.test/catalog", NOW, NOW, Classification.PUBLIC, EvidenceState.CONFIRMED, DataMode.CONNECTED, False)
    program = Program("artemis", None, "NASA Artemis", "space", EvidenceState.CONFIRMED, public)
    facility = AccountFacility("starbase", "spacex", "SpaceX Starbase", "Boca Chica", "TX", Decimal(0), Decimal(0))
    return MonitorCatalog((AccountWatchProfile("spacex", "SpaceX", aliases=("Space Exploration Technologies",)),), (program,), (facility,))


def test_market_taxonomy_recency_and_noise_are_deterministic() -> None:
    assert set(classify_markets("NASA Artemis launch and spacecraft contract")) == {"Space Exploration"}
    assert "Robotics" not in classify_markets("robotics only")
    assert all(set(adapter.definition.industries_supported) <= PRIMARY_MARKETS for adapter in REGISTRY.values())
    assert recency_state(NOW - timedelta(days=31), now=NOW) == "HISTORICAL"


def test_normalization_resolves_exact_catalog_links_and_rejects_noise() -> None:
    adapter = FdaAdapter(
        fake_get(
            {
                "results": [
                    {
                        "k_number": "K-1",
                        "device_name": "SpaceX NASA Artemis SpaceX Starbase approval",
                        "decision_date": "2026-08-15",
                    },
                    {
                        "k_number": "K-2",
                        "device_name": "SpaceX charity award",
                        "decision_date": "2026-08-15",
                    },
                ]
            }
        )
    )
    settings = Settings(_env_file=None, monitor_mode="live")
    resolved = normalize_structured_observation(adapter.collect(run_id="run", settings=settings)[0], catalog=catalog(), source_markets=("Space Exploration",), now=NOW).event
    noisy = normalize_structured_observation(adapter.collect(run_id="run", settings=settings)[1], catalog=catalog(), source_markets=("Space Exploration",), now=NOW).event
    assert resolved.subject_entities[0].canonical_account_id == "spacex"
    assert resolved.program.canonical_program_id == "artemis"
    assert resolved.canonical_facility_id == "starbase"
    assert resolved.event_type.value == "REGULATORY_APPROVAL"
    assert resolved.recency_state == "RECENT"
    assert noisy.seller_relevance_state is SellerRelevanceState.REJECTED


def test_unresolved_observation_is_retained_without_forced_account_match() -> None:
    adapter = FdaAdapter(fake_get({"results": [{"k_number": "K-1", "device_name": "Unknown medical device approval", "decision_date": "2026-08-15"}]}))
    event = normalize_structured_observation(adapter.collect(run_id="run", settings=Settings(_env_file=None, monitor_mode="live"))[0], catalog=catalog(), source_markets=("Medical",), now=NOW).event
    assert event.subject_entities[0].state is ResolutionState.UNRESOLVED
    assert event.seller_relevance_state is SellerRelevanceState.UNRESOLVED


def test_collect_all_persists_success_and_provider_failure_without_second_runner() -> None:
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    repository = MonitorRepository(engine)
    successful = FdaAdapter(fake_get({"results": [{"k_number": "K-1", "device_name": "Medical device approval", "decision_date": "2026-08-15"}]}))
    failed = FdaAdapter(fake_get({}, 500))
    service = MonitorService(Settings(_env_file=None, monitor_mode="live"), {"medical": successful, "failed": failed}, repository=repository, catalog=catalog())
    runs = service.collect_all(limit=1)
    snapshot = MonitorRepository(engine).snapshot()
    assert [run.source_id for run in runs] == ["medical", "failed"]
    assert runs[0].records_seen == 1 and runs[1].failures == ("HTTP_500",)
    assert len(snapshot["runs"]) == 2 and snapshot["events"]
