import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from btx_omni.ai.config import AiConfig
from btx_omni.ai.contracts import EntityCandidateProposal
from btx_omni.ai.gemini import GeminiProvider
from btx_omni.ai.registry import get_ai_provider
from btx_omni.api.intelligence_projection import intelligence_signals
from btx_omni.api.monitor import operational_collect
from btx_omni.api.runtime import PocRuntime
from btx_omni.app import create_app
from btx_omni.core.config import Settings, get_settings
from btx_omni.modules.scoring.account_attractiveness import (
    AccountAttractivenessInputs,
    calculate_account_attractiveness,
)
from btx_omni.monitor.catalog import MonitorCatalog
from btx_omni.monitor.entity_candidates import (
    EntityCandidateResolver,
    generate_candidate_account_ids,
)
from btx_omni.monitor.packs import PACKS
from btx_omni.monitor.repository import MonitorRepository
from btx_omni.monitor.resolution import AccountWatchProfile, resolve_entity
from btx_omni.monitor.service import MonitorService
from btx_omni.monitor.sources import (
    CommerceAdapter,
    CompanyNewsAdapter,
    DodAdapter,
    FdaAdapter,
    SamAdapter,
    SecEdgarAdapter,
    StateEconomicAdapter,
    UsaSpendingAdapter,
)
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


def test_sam_naics_are_applied_only_after_explicit_verification() -> None:
    adapter = SamAdapter(fake_get({"opportunitiesData": []}))
    pending = Settings(
        _env_file=None,
        sam_api_key="key",
        monitor_sam_naics="336411,334413",
        monitor_sam_naics_verification_state="PENDING_VERIFICATION",
    )
    verified = pending.model_copy(
        update={"monitor_sam_naics_verification_state": "VERIFIED"}
    )

    adapter.collect(run_id="pending", settings=pending)
    assert "ncode=" not in adapter.request_url(1)
    adapter.collect(run_id="verified", settings=verified)
    assert "ncode=336411%2C334413" in adapter.request_url(1)


def test_sam_uses_documented_query_key_and_paginates() -> None:
    urls: list[str] = []
    def get(url: str, _headers: dict[str, str]):
        urls.append(url)
        offset = 0 if "offset=0" in url else 1
        return 200, json.dumps({"totalRecords": 2, "opportunitiesData": [{"noticeId": f"N-{offset}", "title": "award"}]}).encode(), {}
    observations = SamAdapter(get).collect(run_id="r", settings=Settings(_env_file=None, sam_api_key="key"), limit=2)
    assert len(observations) == 2
    assert all("api_key=key" in url and "postedFrom=" in url and "postedTo=" in url for url in urls)


def test_new_official_adapters_are_bounded_and_shadow_only() -> None:
    rss = b"<rss><channel><item><guid>one</guid><title>Contract award</title><link>https://official.example/one</link><pubDate>Tue, 01 Sep 2026 10:00:00 +0000</pubDate></item></channel></rss>"
    dod = DodAdapter(lambda _url, _headers: (200, rss, {}))
    assert dod.definition.seller_promotion_permitted is False
    assert dod.collect(run_id="dod", settings=Settings(_env_file=None))[0].source_identity.source_record_id == "one"
    commerce = CommerceAdapter(fake_get({"data": [{"id": "chips-1", "title": "CHIPS manufacturing investment", "url": "https://commerce.gov/n/1"}]}))
    assert commerce.collect(run_id="commerce", settings=Settings(_env_file=None, commerce_api_key="key"))[0].source_identity.source_record_id == "chips-1"


def test_governed_company_and_state_feed_registries_preserve_ownership() -> None:
    rss = b"<rss><channel><item><guid>release-1</guid><title>Skunk Works program update</title><link>https://news.example/release-1</link></item></channel></rss>"
    company = CompanyNewsAdapter(lambda _url, _headers: (200, rss, {}))
    company_settings = Settings(_env_file=None, monitor_company_feed_registry='[{"id":"lockheed-news","canonical_account_id":"lockheed-martin","url":"https://news.example/feed"}]')
    company_observation = company.collect(run_id="company", settings=company_settings)[0]
    assert ("governed_source_owner", "lockheed-martin") in company_observation.source_identity.source_native_ids
    state = StateEconomicAdapter(lambda _url, _headers: (200, rss, {}))
    state_settings = Settings(_env_file=None, monitor_state_source_registry='[{"id":"pa-ed","url":"https://pa.gov/feed"}]')
    assert state.collect(run_id="state", settings=state_settings)[0].source_identity.source_record_id == "release-1"


def test_default_company_registry_is_bounded_and_one_broken_feed_is_isolated() -> None:
    rss = b"<rss><channel><item><guid>release-2</guid><title>Boeing production update</title><link>https://official.example/release-2</link></item></channel></rss>"
    calls = 0
    def get(_url: str, _headers: dict[str, str]):
        nonlocal calls
        calls += 1
        return (500, b"{}", {}) if calls == 1 else (200, rss, {})
    adapter = CompanyNewsAdapter(get)
    observations = adapter.collect(
        run_id="company",
        settings=Settings(_env_file=None, monitor_company_feed_registry="DEFAULT"),
    )
    assert len(observations) == 2
    assert {item.source_identity.source_native_ids[0][1] for item in observations} == {"lockheed-martin", "emerson"}


def test_company_registry_apportions_bounded_results_across_all_publishers() -> None:
    rss = b"<rss><channel><item><guid>release-3</guid><title>Official update</title><link>http://official.example/release-3</link></item></channel></rss>"
    observations = CompanyNewsAdapter(lambda _url, _headers: (200, rss, {})).collect(
        run_id="company",
        settings=Settings(_env_file=None, monitor_company_feed_registry="DEFAULT"),
        limit=3,
    )
    assert len(observations) == 3
    assert {item.source_identity.source_native_ids[0][1] for item in observations} == {"boeing", "lockheed-martin", "emerson"}
    assert all(item.raw_evidence.locator.startswith("https://") for item in observations)


def test_company_source_owner_does_not_convert_article_third_party_to_customer() -> None:
    from btx_omni.monitor.contracts import (
        RawEvidenceReference,
        SourceIdentity,
        SourceObservation,
        SourceVersion,
    )
    from btx_omni.monitor.normalization import normalize_structured_observation

    now = datetime(2026, 9, 1, tzinfo=UTC)
    identity = SourceIdentity("company_newsroom", "release", (("governed_source_owner", "boeing"),))
    version = SourceVersion("release", None, "a" * 64, now, now)
    observation = SourceObservation("observation-release", identity, version, now, "Third Party Logistics announces a partnership", RawEvidenceReference("evidence-release", identity, version, "https://publisher.example/release", now))
    event = normalize_structured_observation(observation, catalog=MonitorCatalog((AccountWatchProfile("boeing", "Boeing"),))).event
    assert event.subject_entities[0].canonical_account_id == "boeing"
    assert event.subject_entities[0].method == "governed_source_ownership"


def test_sec_requires_explicit_identifying_agent_and_preserves_filing_identity() -> None:
    payload = {
        "filings": {
            "recent": {
                "accessionNumber": ["0000000001-26-000001", "0000000001-26-000002"],
                "filingDate": ["2026-08-01", "2026-07-01"],
                "form": ["10-Q", "8-K"],
                "primaryDocument": ["q2.htm", "event.htm"],
            }
        }
    }
    calls: list[dict[str, str]] = []

    def get(_url: str, headers: dict[str, str]) -> tuple[int, bytes, dict[str, str]]:
        calls.append(headers)
        return 200, json.dumps(payload).encode(), {}

    adapter = SecEdgarAdapter(get, targets=(("0000000001", "Verified Co"),))
    assert adapter.available(Settings(_env_file=None))[0] is False
    settings = Settings(_env_file=None, sec_user_agent="BTX Omni Prospect ops@example.com")
    observation = adapter.collect(run_id="sec", settings=settings)[0]
    assert calls[0]["User-Agent"] == settings.sec_user_agent
    assert observation.source_identity.source_record_id == "0000000001-26-000001"
    assert observation.source_identity.source_native_ids == (("sec_cik", "0000000001"),)
    assert observation.raw_evidence.locator.endswith("/q2.htm")


def test_sec_filing_accession_is_idempotent_in_the_monitor_pipeline() -> None:
    payload = {
        "filings": {
            "recent": {
                "accessionNumber": ["0000000001-26-000001"],
                "filingDate": ["2026-08-01"],
                "form": ["10-K"],
                "primaryDocument": ["annual.htm"],
            }
        }
    }
    adapter = SecEdgarAdapter(
        fake_get(payload), targets=(("0000000001", "Verified Co"),)
    )
    service = MonitorService(
        Settings(
            _env_file=None,
            monitor_mode="live",
            sec_user_agent="BTX Omni Prospect ops@example.com",
        ),
        {"sec_edgar": adapter},
        catalog=MonitorCatalog(
            (AccountWatchProfile("verified", "Verified Co", sec_cik="0000000001"),)
        ),
    )

    first = service.collect("sec_edgar")
    second = service.collect("sec_edgar")

    assert first.records_new == 1
    assert second.records_new == 0
    assert second.records_changed == 0


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
    assert set(PACKS) == {"commercial_aerospace", "defense", "energy", "medical", "robotics", "semiconductor", "space"}
    assert all(set(pack.source_ids) <= source_ids for pack in PACKS.values())
    with pytest.raises(RuntimeError, match="disabled"):
        MonitorService(Settings(_env_file=None, monitor_mode="disabled")).collect("fda_openfda")


def test_entity_collision_is_ambiguous_and_ai_registry_is_provider_neutral() -> None:
    profiles = (AccountWatchProfile("one", "Acme", aliases=("Acme Systems",)), AccountWatchProfile("two", "Acme Two", aliases=("Acme Systems",)))
    assert resolve_entity("Acme Systems", profiles).state.value == "AMBIGUOUS"
    provider = get_ai_provider(AiConfig("gemini", None, "test-model", "developer", None, "global", 1))
    assert isinstance(provider, GeminiProvider)
    assert not provider.configured


def test_entity_candidate_is_cached_and_never_promotes_canonical_identity() -> None:
    class CandidateProvider:
        name = "fake-gemini"
        config = type("Config", (), {"model": "test"})()
        calls = 0
        def propose_entity_candidate(self, request):
            self.calls += 1
            assert request.candidate_account_ids == ("one", "two")
            return EntityCandidateProposal("one", ("one",), "linguistic candidate", ("legal proof absent",))

    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    profiles = (AccountWatchProfile("one", "Acme One", aliases=("Acme Systems",)), AccountWatchProfile("two", "Acme Two", aliases=("Acme Systems",)))
    provider = CandidateProvider()
    service = MonitorService(
        Settings(_env_file=None, monitor_mode="live"),
        {"fda": FdaAdapter(fake_get({"results": [{"id": "candidate-1", "title": "Acme Systems approval"}]}))},
        repository=MonitorRepository(engine), watch_profiles=profiles,
        catalog=MonitorCatalog(profiles),
        entity_candidate_resolver=EntityCandidateResolver(provider, MonitorRepository(engine), profiles),
    )
    service.collect("fda")
    service.collect("fda")
    event = next(iter(service.events.values()))
    assert provider.calls == 1
    assert event.subject_entities[0].canonical_account_id is None
    assert event.subject_entities[0].state.value == "UNRESOLVED"
    assert event.subject_entities[0].candidate_account_ids == ("one",)


def test_candidate_generator_uses_governed_evidence_not_catalog_order() -> None:
    profiles = (
        AccountWatchProfile("first", "Unrelated Industrial Holdings"),
        AccountWatchProfile("target", "Boeing Company", aliases=("Boeing",)),
        AccountWatchProfile("other", "Boeing Precision", facilities=("Phoenix Plant",)),
    )
    candidates = generate_candidate_account_ids(
        mention="Boeing", source_text="Boeing announces a Phoenix Plant expansion",
        profiles=profiles, markets=("Commercial Aerospace",), cap=2,
    )
    assert candidates == ("other", "target")
    assert "first" not in candidates
    assert generate_candidate_account_ids(mention="Entirely Unknown", source_text="Unrelated association notice", profiles=profiles) == ()


def test_governed_source_owner_resolves_without_native_identifier_but_identifier_wins() -> None:
    profiles = (
        AccountWatchProfile("boeing", "Boeing", domain="boeing.example"),
        AccountWatchProfile("lockheed", "Lockheed Martin", sec_cik="0000936468"),
    )
    catalog = MonitorCatalog(profiles)
    owned = catalog.resolve_subjects("Skunk Works announces an update", source_url="https://boeing.example/feed")
    assert owned[0].canonical_account_id == "boeing"
    conflicted = catalog.resolve_subjects("Skunk Works announces an update", source_url="https://boeing.example/feed", source_identifiers=(("sec_cik", "0000936468"),))
    assert conflicted[0].canonical_account_id == "lockheed"


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


def test_monitor_registry_endpoint_is_internal_observability(monkeypatch: pytest.MonkeyPatch) -> None:
    # An explicit empty process value overrides any developer-local .env token.
    monkeypatch.setenv("BTX_MONITOR_OPERATOR_TOKEN", "")
    get_settings.cache_clear()
    client = TestClient(create_app())
    response = client.get("/api/monitor/sources")
    assert response.status_code == 200
    assert {item["source_id"] for item in response.json()} >= {"sam_gov", "fda_openfda", "sec_edgar"}
    health = client.get("/api/monitor/health")
    assert health.status_code == 200 and {"sources", "last_runs", "clusters", "rejected_observations"} <= set(health.json())
    assert client.post("/api/monitor/collect/fda_openfda").status_code == 403
    assert client.post("/api/monitor/internal/collect/fda_openfda").status_code == 503

    monkeypatch.setenv("BTX_MONITOR_OPERATOR_TOKEN", "configured-but-private")
    get_settings.cache_clear()
    configured_client = TestClient(create_app())
    assert configured_client.post("/api/monitor/internal/collect/fda_openfda").status_code == 403
    assert configured_client.post(
        "/api/monitor/internal/collect/fda_openfda",
        headers={"X-BTX-Monitor-Operator-Token": "wrong-token"},
    ).status_code == 403
    get_settings.cache_clear()
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


def _durable_runtime(tmp_path) -> PocRuntime:
    settings = Settings(
        _env_file=None,
        monitor_mode="live",
        monitor_durable_state_enabled=True,
        database_url=f"sqlite:///{tmp_path / 'monitor-restart.db'}",
    )
    engine = create_engine(settings.database_url)
    metadata.create_all(engine)
    return PocRuntime(settings)


def _fda(payload: dict) -> FdaAdapter:
    return FdaAdapter(fake_get({"results": [payload]}))


def test_durable_monitor_events_rehydrate_after_runtime_restart_without_scoring_change(tmp_path) -> None:
    initial = _durable_runtime(tmp_path)
    initial.monitor.registry["fda_openfda"] = _fda(
        {"k_number": "K-RESTART-MEDTRONIC", "device_name": "Medtronic device approval", "decision_date": "2026-08-15"}
    )
    score_before = calculate_account_attractiveness(
        AccountAttractivenessInputs(initial.sample.scoring_inputs["medtronic"]),
        evidence_ids=("medtronic-public-identity",),
        calculated_at=initial.observed_at(),
    )
    sample_commercial = tuple(
        (item.account_id, item.business_unit, item.ttm_revenue_minor, item.ttm_bookings_minor)
        for item in initial.sample.commercial_contexts
    )
    initial.monitor.collect("fda_openfda")
    before_restart = [item for item in intelligence_signals(initial) if item.get("data_mode") == "CONNECTED"]

    restarted = PocRuntime(initial.settings)
    after_restart = [item for item in intelligence_signals(restarted) if item.get("data_mode") == "CONNECTED"]
    score_after = calculate_account_attractiveness(
        AccountAttractivenessInputs(restarted.sample.scoring_inputs["medtronic"]),
        evidence_ids=("medtronic-public-identity",),
        calculated_at=restarted.observed_at(),
    )

    assert len(before_restart) == len(after_restart) == 1
    assert before_restart[0]["id"] == after_restart[0]["id"]
    assert after_restart[0]["account_id"] == "medtronic"
    assert after_restart[0]["source_url"] and after_restart[0]["provenance"].source_record_id == "K-RESTART-MEDTRONIC"
    assert len(restarted.monitor.events) == 1
    restarted.monitor.hydrate_events()
    assert len(restarted.monitor.events) == 1
    assert score_before.score == score_after.score
    assert tuple(
        (item.account_id, item.business_unit, item.ttm_revenue_minor, item.ttm_bookings_minor)
        for item in restarted.sample.commercial_contexts
    ) == sample_commercial


def test_durable_restart_rehydrates_but_excludes_noneligible_events(tmp_path) -> None:
    initial = _durable_runtime(tmp_path)
    repository = initial.monitor.repository
    assert repository is not None
    sample = initial.sample
    services = (
        MonitorService(
            initial.settings,
            {"resolved": _fda({"k_number": "K-RESOLVED", "device_name": "Medtronic device approval", "decision_date": "2026-08-15"})},
            repository=repository,
            watch_profiles=sample.watch_profiles,
            catalog=initial.monitor.catalog,
        ),
        MonitorService(
            initial.settings,
            {"unresolved": _fda({"k_number": "K-UNRESOLVED", "device_name": "Unknown device approval", "decision_date": "2026-08-15"})},
            repository=repository,
            watch_profiles=sample.watch_profiles,
            catalog=initial.monitor.catalog,
        ),
        MonitorService(
            initial.settings,
            {"rejected": _fda({"k_number": "K-REJECTED", "device_name": "Medtronic charity award", "decision_date": "2026-08-15"})},
            repository=repository,
            watch_profiles=sample.watch_profiles,
            catalog=initial.monitor.catalog,
        ),
        MonitorService(
            initial.settings,
            {"ambiguous": _fda({"k_number": "K-AMBIGUOUS", "device_name": "Acme Systems device approval", "decision_date": "2026-08-15"})},
            repository=repository,
            watch_profiles=(
                AccountWatchProfile("one", "Acme One", aliases=("Acme Systems",)),
                AccountWatchProfile("two", "Acme Two", aliases=("Acme Systems",)),
            ),
            catalog=MonitorCatalog(
                (
                    AccountWatchProfile("one", "Acme One", aliases=("Acme Systems",)),
                    AccountWatchProfile("two", "Acme Two", aliases=("Acme Systems",)),
                ),
                sample.programs,
                sample.facilities,
            ),
        ),
    )
    for service, source_id in zip(services, ("resolved", "unresolved", "rejected", "ambiguous"), strict=True):
        service.collect(source_id)

    restarted = PocRuntime(initial.settings)
    projected = [item for item in intelligence_signals(restarted) if item.get("data_mode") == "CONNECTED"]
    states = {event.id: event.seller_relevance_state.value for event in restarted.monitor.events.values()}

    assert len(restarted.monitor.events) == 4
    assert len(projected) == 1 and projected[0]["account_id"] == "medtronic"
    assert set(states.values()) == {"RESOLVED_ELIGIBLE", "UNRESOLVED", "REJECTED", "AMBIGUOUS"}
