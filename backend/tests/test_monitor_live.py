import json

import pytest
from fastapi.testclient import TestClient

from btx_omni.ai.anthropic import AnthropicProvider
from btx_omni.ai.config import AiConfig
from btx_omni.ai.contracts import AiRequest
from btx_omni.ai.registry import get_ai_provider
from btx_omni.app import create_app
from btx_omni.core.config import Settings
from btx_omni.monitor.packs import PACKS
from btx_omni.monitor.resolution import AccountWatchProfile, resolve_entity
from btx_omni.monitor.service import MonitorService
from btx_omni.monitor.sources import FdaAdapter, SamAdapter, UsaSpendingAdapter


def fake_get(payload: object, status: int = 200):
    def get(_url: str, _headers: dict[str, str]) -> tuple[int, bytes, dict[str, str]]:
        return status, json.dumps(payload).encode(), {}
    return get


def test_structured_adapters_emit_canonical_observations() -> None:
    sam = SamAdapter(fake_get({"opportunitiesData": [{"noticeId": "N-1", "title": "Award notice", "postedDate": "2026-01-02T00:00:00Z", "uiLink": "https://sam.example/N-1"}]}))
    usa = UsaSpendingAdapter(fake_get({"results": [{"Award ID": "A-1", "description": "Contract award"}]}))
    fda = FdaAdapter(fake_get({"results": [{"k_number": "K123", "device_name": "Device approval"}]}))
    settings = Settings(sam_api_key="test-key", monitor_mode="live")
    assert sam.collect(run_id="r1", settings=settings)[0].source_identity.source_record_id == "N-1"
    assert usa.parse(json.dumps({"results": [{"Award ID": "A-1", "description": "Contract award"}]}).encode(), run_id="r1")[0].source_tier.startswith("TIER_1")
    assert fda.collect(run_id="r1", settings=settings)[0].raw_evidence.media_type == "application/json"


def test_unavailable_auth_malformed_rate_limit_and_empty_are_health_states() -> None:
    service = MonitorService(Settings(monitor_mode="live"), {"sam_gov": SamAdapter(fake_get({}))})
    assert service.collect("sam_gov").failures == ("SAM_API_KEY is not configured",)
    rate_limited = MonitorService(Settings(monitor_mode="live", sam_api_key="x"), {"sam_gov": SamAdapter(fake_get({}, 429))})
    assert rate_limited.collect("sam_gov").failures == ("RATE_LIMITED",)
    malformed = MonitorService(Settings(monitor_mode="live"), {"fda": FdaAdapter(lambda _u, _h: (200, b"no-json", {}))})
    assert malformed.collect("fda").failures == ("MALFORMED_SOURCE_RESPONSE",)
    empty = MonitorService(Settings(monitor_mode="live"), {"fda": FdaAdapter(fake_get({"results": []}))})
    assert empty.collect("fda").records_seen == 0


def test_all_six_industry_packs_reference_registry_sources_and_no_live_fallback() -> None:
    source_ids = {"sam_gov", "usaspending", "federal_register", "sec_edgar", "nasa", "dod", "commerce", "fda_openfda", "company_newsroom", "state_economic_development"}
    assert set(PACKS) == {"commercial_aerospace", "defense", "space", "semiconductor", "medical_device", "robotics"}
    assert all(set(pack.source_ids) <= source_ids for pack in PACKS.values())
    with pytest.raises(RuntimeError, match="disabled"):
        MonitorService(Settings(monitor_mode="disabled")).collect("fda_openfda")


def test_entity_collision_is_ambiguous_and_ai_registry_is_provider_neutral() -> None:
    profiles = (AccountWatchProfile("one", "Acme", aliases=("Acme Systems",)), AccountWatchProfile("two", "Acme Two", aliases=("Acme Systems",)))
    assert resolve_entity("Acme Systems", profiles).state.value == "AMBIGUOUS"
    provider = get_ai_provider(AiConfig("anthropic", None, "test-model"))
    assert isinstance(provider, AnthropicProvider)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        provider.summarize_evidence(AiRequest("text", ("ev-1",), "summarize"))


def test_monitor_observations_cluster_with_multiple_evidence_and_source_update() -> None:
    settings = Settings(monitor_mode="live")
    first = FdaAdapter(fake_get({"results": [{"id": "same", "title": "Device approval"}]}))
    second = FdaAdapter(fake_get({"results": [{"id": "same", "title": "Device approval amended"}]}))
    service = MonitorService(settings, {"fda": first})
    service.collect("fda")
    service.registry["fda"] = second
    service.collect("fda")
    assert len(service.runs) == 2 and service.health["fda"].last_success_at is not None


def test_monitor_registry_endpoint_is_internal_observability() -> None:
    client = TestClient(create_app())
    response = client.get("/api/monitor/sources")
    assert response.status_code == 200
    assert {item["source_id"] for item in response.json()} >= {"sam_gov", "fda_openfda", "sec_edgar"}
