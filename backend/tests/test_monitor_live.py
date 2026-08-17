import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from btx_omni.ai.anthropic import AnthropicProvider
from btx_omni.ai.config import AiConfig
from btx_omni.ai.contracts import AiRequest
from btx_omni.ai.registry import get_ai_provider
from btx_omni.api.intelligence_projection import intelligence_signals
from btx_omni.api.monitor import operational_collect
from btx_omni.api.runtime import PocRuntime
from btx_omni.app import create_app
from btx_omni.core.config import Settings
from btx_omni.monitor.packs import PACKS
from btx_omni.monitor.repository import MonitorRepository
from btx_omni.monitor.resolution import AccountWatchProfile, resolve_entity
from btx_omni.monitor.service import MonitorService
from btx_omni.monitor.sources import FdaAdapter, SamAdapter, UsaSpendingAdapter
from btx_omni.persistence.models import metadata


def fake_get(payload: object, status: int = 200):
    def get(_url: str, _headers: dict[str, str]) -> tuple[int, bytes, dict[str, str]]:
        return status, json.dumps(payload).encode(), {}
    return get


def test_structured_adapters_emit_canonical_observations() -> None:
    sam = SamAdapter(fake_get({"opportunitiesData": [{"noticeId": "N-1", "title": "Award notice", "postedDate": "2026-01-02T00:00:00Z", "uiLink": "https://sam.example/N-1"}]}))
    usa = UsaSpendingAdapter(fake_get({"results": [{"Award ID": "A-1", "description": "Contract award"}]}))
    fda = FdaAdapter(fake_get({"results": [{"k_number": "K123", "device_name": "Device approval"}]}))
    settings = Settings(_env_file=None, sam_api_key="test-key", monitor_mode="live")
    assert sam.collect(run_id="r1", settings=settings)[0].source_identity.source_record_id == "N-1"
    usa_observation = usa.parse(json.dumps({"results": [{"Award ID": "A-1", "description": "Contract award"}]}).encode(), run_id="r1")[0]
    fda_observation = fda.collect(run_id="r1", settings=settings)[0]
    assert usa_observation.source_tier.startswith("TIER_1") and usa_observation.source_identity.source_record_id == "A-1"
    assert fda_observation.raw_evidence.media_type == "application/json" and fda_observation.source_identity.source_record_id == "K123"


def test_live_adapter_caps_generic_results_before_normalization() -> None:
    adapter = FdaAdapter(fake_get({"results": [{"k_number": "K1"}, {"k_number": "K2"}]}))

    observations = adapter.collect(run_id="r1", settings=Settings(_env_file=None, monitor_mode="live"), limit=1)

    assert len(observations) == 1 and observations[0].source_identity.source_record_id == "K1"


def test_unavailable_auth_malformed_rate_limit_and_empty_are_health_states() -> None:
    service = MonitorService(
        Settings(_env_file=None, monitor_mode="live", sam_api_key=None),
        {"sam_gov": SamAdapter(fake_get({}))},
    )
    assert service.collect("sam_gov").failures == ("SAM_API_KEY is not configured",)
    rate_limited = MonitorService(
        Settings(_env_file=None, monitor_mode="live", sam_api_key="x"),
        {"sam_gov": SamAdapter(fake_get({}, 429))},
    )
    assert rate_limited.collect("sam_gov").failures == ("RATE_LIMITED",)
    malformed = MonitorService(
        Settings(_env_file=None, monitor_mode="live"),
        {"fda": FdaAdapter(lambda _u, _h: (200, b"no-json", {}))},
    )
    assert malformed.collect("fda").failures == ("MALFORMED_SOURCE_RESPONSE",)
    empty = MonitorService(
        Settings(_env_file=None, monitor_mode="live"),
        {"fda": FdaAdapter(fake_get({"results": []}))},
    )
    assert empty.collect("fda").records_seen == 0


def test_all_six_industry_packs_reference_registry_sources_and_no_live_fallback() -> None:
    source_ids = {"sam_gov", "usaspending", "federal_register", "sec_edgar", "nasa", "dod", "commerce", "fda_openfda", "company_newsroom", "state_economic_development"}
    assert set(PACKS) == {"commercial_aerospace", "defense", "space", "semiconductor", "medical_device", "robotics"}
    assert all(set(pack.source_ids) <= source_ids for pack in PACKS.values())
    with pytest.raises(RuntimeError, match="disabled"):
        MonitorService(Settings(_env_file=None, monitor_mode="disabled")).collect("fda_openfda")


def test_entity_collision_is_ambiguous_and_ai_registry_is_provider_neutral() -> None:
    profiles = (AccountWatchProfile("one", "Acme", aliases=("Acme Systems",)), AccountWatchProfile("two", "Acme Two", aliases=("Acme Systems",)))
    assert resolve_entity("Acme Systems", profiles).state.value == "AMBIGUOUS"
    provider = get_ai_provider(AiConfig("anthropic", None, "test-model"))
    assert isinstance(provider, AnthropicProvider)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        provider.summarize_evidence(AiRequest("text", ("ev-1",), "summarize"))


def test_monitor_observations_cluster_with_multiple_evidence_and_source_update() -> None:
    settings = Settings(_env_file=None, monitor_mode="live")
    first = FdaAdapter(fake_get({"results": [{"id": "same", "title": "Device approval"}]}))
    second = FdaAdapter(fake_get({"results": [{"id": "same", "title": "Device approval amended"}]}))
    service = MonitorService(settings, {"fda": first})
    service.collect("fda")
    service.registry["fda"] = second
    service.collect("fda")
    assert len(service.runs) == 2 and service.health["fda"].last_success_at is not None
    assert service.runs[0].records_new == 1 and service.runs[1].records_changed == 1


def test_durable_monitor_persists_runs_versions_events_and_failures() -> None:
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    repository = MonitorRepository(engine)
    settings = Settings(_env_file=None, monitor_mode="live")
    service = MonitorService(settings, {"fda": FdaAdapter(fake_get({"results": [{"id": "same", "title": "Device approval"}]}))}, repository=repository)
    service.collect("fda")
    service.registry["fda"] = FdaAdapter(fake_get({"results": [{"id": "same", "title": "Device approval amended"}]}))
    service.collect("fda")
    service.registry["fda"] = FdaAdapter(lambda _url, _headers: (500, b"{}", {}))
    service.collect("fda")
    snapshot = repository.snapshot()
    assert len(snapshot["runs"]) == 3 and snapshot["runs"][0]["failures"]
    assert snapshot["events"][0]["data_mode"] == "LIVE_PUBLIC"
    assert snapshot["events"][0]["publication_date"] is None or snapshot["events"][0]["collected_at"]
    assert snapshot["health"][0]["state"] == "FAILED"
    assert service.source_state(source_id="fda", last_success_at=None, now=service.runs[-1].started_at) == "UNAVAILABLE"
    assert service.source_state(source_id="fda", last_success_at=datetime.now(UTC) - timedelta(hours=49), now=datetime.now(UTC)) == "STALE"


def test_monitor_registry_endpoint_is_internal_observability() -> None:
    client = TestClient(create_app())
    response = client.get("/api/monitor/sources")
    assert response.status_code == 200
    assert {item["source_id"] for item in response.json()} >= {"sam_gov", "fda_openfda", "sec_edgar"}
    health = client.get("/api/monitor/health")
    assert health.status_code == 200 and {"sources", "last_runs", "clusters", "rejected_observations"} <= set(health.json())
    assert client.post("/api/monitor/collect/fda_openfda").status_code == 403
    assert client.post("/api/monitor/internal/collect/fda_openfda").status_code == 403
    assert all(item["data_mode"] == "CURATED_PUBLIC" for item in health.json()["curated_preview"])


def test_operational_collection_rejects_an_invalid_operator_token() -> None:
    runtime = PocRuntime(Settings(_env_file=None, monitor_operator_token="configured-but-private"))
    with pytest.raises(HTTPException, match="authorization failed"):
        operational_collect("fda_openfda", runtime, "wrong-token")


def test_live_monitor_event_projects_through_canonical_intelligence_contract() -> None:
    runtime = PocRuntime(Settings(_env_file=None, monitor_mode="live"))
    runtime.monitor = MonitorService(runtime.settings, {"fda": FdaAdapter(fake_get({"results": [{"id": "live-1", "title": "Device approval"}]}))})
    runtime.monitor.collect("fda", limit=1)

    live = [item for item in intelligence_signals(runtime) if item.get("data_mode") == "CONNECTED"]

    assert not live
