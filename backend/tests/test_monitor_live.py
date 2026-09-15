import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

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
from btx_omni.monitor.ontology import ResolutionState, SourceHealthState
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
from btx_omni.providers.sample.environment import build_sample_environment


def fake_get(payload: object, status: int = 200):
    def get(_url: str, _headers: dict[str, str]) -> tuple[int, bytes, dict[str, str]]:
        return status, json.dumps(payload).encode(), {}

    return get


def test_structured_adapters_emit_canonical_observations() -> None:
    sam = SamAdapter(
        fake_get(
            {
                "opportunitiesData": [
                    {
                        "noticeId": "N-1",
                        "title": "Award notice",
                        "postedDate": "2026-01-02T00:00:00Z",
                        "uiLink": "https://sam.example/N-1",
                    }
                ]
            }
        )
    )
    usa = UsaSpendingAdapter(
        fake_get({"results": [{"Award ID": "A-1", "description": "Contract award"}]})
    )
    fda = FdaAdapter(
        fake_get({"results": [{"k_number": "K123", "device_name": "Device approval"}]})
    )
    settings = Settings(_env_file=None, sam_api_key="test-key", monitor_mode="live")
    assert (
        sam.collect(run_id="r1", settings=settings)[0].source_identity.source_record_id
        == "N-1"
    )
    usa_observation = usa.parse(
        json.dumps(
            {"results": [{"Award ID": "A-1", "description": "Contract award"}]}
        ).encode(),
        run_id="r1",
    )[0]
    fda_observation = fda.collect(run_id="r1", settings=settings)[0]
    assert (
        usa_observation.source_tier.startswith("TIER_1")
        and usa_observation.source_identity.source_record_id == "A-1"
    )
    assert (
        fda_observation.raw_evidence.media_type == "application/json"
        and fda_observation.source_identity.source_record_id == "K123"
    )


def test_live_adapter_caps_generic_results_before_normalization() -> None:
    adapter = FdaAdapter(
        fake_get({"results": [{"k_number": "K1"}, {"k_number": "K2"}]})
    )

    observations = adapter.collect(
        run_id="r1", settings=Settings(_env_file=None, monitor_mode="live"), limit=1
    )

    assert (
        len(observations) == 1
        and observations[0].source_identity.source_record_id == "K1"
    )


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
    assert "ncode=336411" in adapter.request_url(1)


def test_sam_queries_each_verified_naics_as_a_separate_bounded_request() -> None:
    urls: list[str] = []

    def get(url: str, _headers: dict[str, str]):
        urls.append(url)
        code = "336411" if "ncode=336411" in url else "334413"
        return (
            200,
            json.dumps(
                {
                    "totalRecords": 1,
                    "opportunitiesData": [{"noticeId": f"N-{code}", "title": code}],
                }
            ).encode(),
            {},
        )

    settings = Settings(
        _env_file=None,
        sam_api_key="key",
        monitor_sam_naics="336411,334413",
        monitor_sam_naics_verification_state="VERIFIED",
    )
    observations = SamAdapter(get).collect(run_id="r", settings=settings, limit=4)
    assert len(urls) == 2
    assert all("%2C" not in url for url in urls)
    assert {item.source_identity.source_record_id for item in observations} == {
        "N-336411",
        "N-334413",
    }


def test_sam_honors_bounded_public_retrieval_window() -> None:
    urls: list[str] = []

    def get(url: str, _headers: dict[str, str]):
        urls.append(url)
        return (
            200,
            json.dumps({"totalRecords": 0, "opportunitiesData": []}).encode(),
            {},
        )

    settings = Settings(
        _env_file=None,
        sam_api_key="key",
        monitor_public_lookback_days=60,
    )
    SamAdapter(get).collect(
        run_id="r",
        settings=settings,
        collected_at=datetime(2026, 9, 9, tzinfo=UTC),
    )
    assert "postedFrom=07%2F11%2F2026" in urls[0]
    assert "postedTo=09%2F09%2F2026" in urls[0]


def test_sam_uses_documented_query_key_and_paginates() -> None:
    urls: list[str] = []

    def get(url: str, _headers: dict[str, str]):
        urls.append(url)
        offset = 0 if "offset=0" in url else 1
        return (
            200,
            json.dumps(
                {
                    "totalRecords": 2,
                    "opportunitiesData": [
                        {"noticeId": f"N-{offset}", "title": "award"}
                    ],
                }
            ).encode(),
            {},
        )

    observations = SamAdapter(get).collect(
        run_id="r", settings=Settings(_env_file=None, sam_api_key="key"), limit=2
    )
    assert len(observations) == 2
    assert all(
        "api_key=key" in url and "postedFrom=" in url and "postedTo=" in url
        for url in urls
    )


def test_new_official_adapters_are_bounded_and_shadow_only() -> None:
    rss = b"<rss><channel><item><guid>one</guid><title>Contract award</title><link>https://official.example/one</link><pubDate>Tue, 01 Sep 2026 10:00:00 +0000</pubDate></item></channel></rss>"
    dod = DodAdapter(lambda _url, _headers: (200, rss, {}))
    assert dod.definition.seller_promotion_permitted is False
    assert (
        dod.collect(run_id="dod", settings=Settings(_env_file=None))[
            0
        ].source_identity.source_record_id
        == "one"
    )
    commerce = CommerceAdapter(
        fake_get(
            {
                "data": [
                    {
                        "id": "chips-1",
                        "title": "CHIPS manufacturing investment",
                        "url": "https://commerce.gov/n/1",
                    }
                ]
            }
        )
    )
    assert (
        commerce.collect(
            run_id="commerce", settings=Settings(_env_file=None, commerce_api_key="key")
        )[0].source_identity.source_record_id
        == "chips-1"
    )


def test_governed_company_and_state_feed_registries_preserve_ownership() -> None:
    rss = b"<rss><channel><item><guid>release-1</guid><title>Skunk Works program update</title><link>https://news.example/release-1</link></item></channel></rss>"
    company = CompanyNewsAdapter(lambda _url, _headers: (200, rss, {}))
    company_settings = Settings(
        _env_file=None,
        monitor_company_feed_registry='[{"id":"lockheed-news","canonical_account_id":"lockheed-martin","url":"https://news.example/feed"}]',
    )
    company_observation = company.collect(run_id="company", settings=company_settings)[
        0
    ]
    assert (
        "governed_source_owner",
        "lockheed-martin",
    ) in company_observation.source_identity.source_native_ids
    state = StateEconomicAdapter(lambda _url, _headers: (200, rss, {}))
    state_settings = Settings(
        _env_file=None,
        monitor_state_source_registry='[{"id":"pa-ed","url":"https://pa.gov/feed"}]',
    )
    assert (
        state.collect(run_id="state", settings=state_settings)[
            0
        ].source_identity.source_record_id
        == "release-1"
    )


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
    assert {item.source_identity.source_native_ids[0][1] for item in observations} == {
        "lockheed-martin",
        "emerson",
    }
    assert adapter.collection_warnings() == ("boeing-investor-press:HTTP_500",)


def test_company_partial_failure_is_durable_and_does_not_discard_success(
    tmp_path,
) -> None:
    rss = b"<rss><channel><item><guid>release-partial</guid><title>Lockheed Martin capacity update</title><link>https://official.example/release-partial</link></item></channel></rss>"
    calls = 0

    def get(_url: str, _headers: dict[str, str]):
        nonlocal calls
        calls += 1
        return (503, b"", {}) if calls == 1 else (200, rss, {})

    engine = create_engine(f"sqlite:///{tmp_path / 'company-partial.db'}")
    metadata.create_all(engine)
    sample = build_sample_environment()
    service = MonitorService(
        Settings(
            _env_file=None,
            monitor_mode="live",
            monitor_durable_state_enabled=True,
            monitor_company_feed_registry="DEFAULT",
        ),
        {"company_newsroom": CompanyNewsAdapter(get)},
        repository=MonitorRepository(engine),
        watch_profiles=sample.watch_profiles,
        catalog=MonitorCatalog(
            sample.watch_profiles, sample.programs, sample.facilities
        ),
    )

    run = service.collect("company_newsroom", limit=3)

    assert run.records_seen == 2
    assert run.failures == ("boeing-investor-press:HTTP_503",)
    assert service.health["company_newsroom"].state is SourceHealthState.PARTIAL
    durable = service.repository.snapshot()
    assert durable["runs"][0]["failures"] == ["boeing-investor-press:HTTP_503"]
    assert len(durable["events"]) == 2


def test_owned_publisher_preserves_other_explicit_company_subjects() -> None:
    sample = build_sample_environment()
    catalog = MonitorCatalog(sample.watch_profiles, sample.programs, sample.facilities)
    subjects = catalog.resolve_subjects(
        "Boeing and Lockheed Martin announce a documented partnership.",
        source_identifiers=(("governed_source_owner", "boeing"),),
    )

    assert [item.canonical_account_id for item in subjects] == [
        "boeing",
        "lockheed-martin",
    ]
    assert all(item.state is ResolutionState.RESOLVED for item in subjects)

    from btx_omni.monitor.normalization import normalize_structured_observation

    observation = CompanyNewsAdapter(
        lambda _url, _headers: (
            200,
            b"<rss><channel><item><guid>joint</guid><title>Boeing and Lockheed Martin announce a defense partnership</title><link>https://official.example/joint</link><pubDate>Tue, 15 Sep 2026 10:00:00 GMT</pubDate></item></channel></rss>",
            {},
        )
    ).collect(
        run_id="joint",
        settings=Settings(_env_file=None, monitor_company_feed_registry="DEFAULT"),
        limit=3,
        collected_at=datetime(2026, 9, 15, tzinfo=UTC),
    )[0]
    event = normalize_structured_observation(
        observation,
        catalog=catalog,
        source_markets=CompanyNewsAdapter.definition.industries_supported,
        now=datetime(2026, 9, 15, 12, tzinfo=UTC),
    ).event
    assert event.resolution_state is ResolutionState.RESOLVED
    assert event.seller_relevance_state.value == "RESOLVED_ELIGIBLE"


def test_company_registry_apportions_bounded_results_across_all_publishers() -> None:
    rss = b"<rss><channel><item><guid>release-3</guid><title>Official update</title><link>http://official.example/release-3</link></item></channel></rss>"
    observations = CompanyNewsAdapter(lambda _url, _headers: (200, rss, {})).collect(
        run_id="company",
        settings=Settings(_env_file=None, monitor_company_feed_registry="DEFAULT"),
        limit=3,
    )
    assert len(observations) == 3
    assert {item.source_identity.source_native_ids[0][1] for item in observations} == {
        "boeing",
        "lockheed-martin",
        "emerson",
    }
    assert all(
        item.raw_evidence.locator.startswith("https://") for item in observations
    )


def test_company_source_owner_does_not_convert_article_third_party_to_customer() -> (
    None
):
    from btx_omni.monitor.contracts import (
        RawEvidenceReference,
        SourceIdentity,
        SourceObservation,
        SourceVersion,
    )
    from btx_omni.monitor.normalization import normalize_structured_observation

    now = datetime(2026, 9, 1, tzinfo=UTC)
    identity = SourceIdentity(
        "company_newsroom", "release", (("governed_source_owner", "boeing"),)
    )
    version = SourceVersion("release", None, "a" * 64, now, now)
    observation = SourceObservation(
        "observation-release",
        identity,
        version,
        now,
        "Third Party Logistics announces a partnership",
        RawEvidenceReference(
            "evidence-release",
            identity,
            version,
            "https://publisher.example/release",
            now,
        ),
    )
    event = normalize_structured_observation(
        observation, catalog=MonitorCatalog((AccountWatchProfile("boeing", "Boeing"),))
    ).event
    assert event.subject_entities[0].canonical_account_id == "boeing"
    assert event.subject_entities[0].method == "governed_source_ownership"


def test_sec_requires_explicit_identifying_agent_and_preserves_filing_identity() -> (
    None
):
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
    settings = Settings(
        _env_file=None, sec_user_agent="BTX Omni Prospect ops@example.com"
    )
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


def test_all_six_industry_packs_reference_registry_sources_and_no_live_fallback() -> (
    None
):
    source_ids = {
        "sam_gov",
        "usaspending",
        "federal_register",
        "sec_edgar",
        "nasa",
        "dod",
        "commerce",
        "fda_openfda",
        "company_newsroom",
        "state_economic_development",
    }
    assert set(PACKS) == {
        "commercial_aerospace",
        "defense",
        "energy",
        "medical",
        "robotics",
        "semiconductor",
        "space",
    }
    assert all(set(pack.source_ids) <= source_ids for pack in PACKS.values())
    with pytest.raises(RuntimeError, match="disabled"):
        MonitorService(Settings(_env_file=None, monitor_mode="disabled")).collect(
            "fda_openfda"
        )


def test_entity_collision_is_ambiguous_and_ai_registry_is_provider_neutral() -> None:
    profiles = (
        AccountWatchProfile("one", "Acme", aliases=("Acme Systems",)),
        AccountWatchProfile("two", "Acme Two", aliases=("Acme Systems",)),
    )
    assert resolve_entity("Acme Systems", profiles).state.value == "AMBIGUOUS"
    provider = get_ai_provider(
        AiConfig("gemini", None, "test-model", "developer", None, "global", 1)
    )
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
            return EntityCandidateProposal(
                "one", ("one",), "linguistic candidate", ("legal proof absent",)
            )

    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    profiles = (
        AccountWatchProfile("one", "Acme One", aliases=("Acme Systems",)),
        AccountWatchProfile("two", "Acme Two", aliases=("Acme Systems",)),
    )
    provider = CandidateProvider()
    service = MonitorService(
        Settings(_env_file=None, monitor_mode="live"),
        {
            "fda": FdaAdapter(
                fake_get(
                    {
                        "results": [
                            {"id": "candidate-1", "title": "Acme Systems approval"}
                        ]
                    }
                )
            )
        },
        repository=MonitorRepository(engine),
        watch_profiles=profiles,
        catalog=MonitorCatalog(profiles),
        entity_candidate_resolver=EntityCandidateResolver(
            provider, MonitorRepository(engine), profiles
        ),
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
        mention="Boeing",
        source_text="Boeing announces a Phoenix Plant expansion",
        profiles=profiles,
        markets=("Commercial Aerospace",),
        cap=2,
    )
    assert candidates == ("other", "target")
    assert "first" not in candidates
    assert (
        generate_candidate_account_ids(
            mention="Entirely Unknown",
            source_text="Unrelated association notice",
            profiles=profiles,
        )
        == ()
    )


def test_governed_source_owner_resolves_without_native_identifier_but_identifier_wins() -> (
    None
):
    profiles = (
        AccountWatchProfile("boeing", "Boeing", domain="boeing.example"),
        AccountWatchProfile("lockheed", "Lockheed Martin", sec_cik="0000936468"),
    )
    catalog = MonitorCatalog(profiles)
    owned = catalog.resolve_subjects(
        "Skunk Works announces an update", source_url="https://boeing.example/feed"
    )
    assert owned[0].canonical_account_id == "boeing"
    conflicted = catalog.resolve_subjects(
        "Skunk Works announces an update",
        source_url="https://boeing.example/feed",
        source_identifiers=(("sec_cik", "0000936468"),),
    )
    assert conflicted[0].canonical_account_id == "lockheed"


def test_monitor_observations_cluster_with_multiple_evidence_and_source_update() -> (
    None
):
    settings = Settings(_env_file=None, monitor_mode="live")
    first = FdaAdapter(
        fake_get({"results": [{"id": "same", "title": "Device approval"}]})
    )
    second = FdaAdapter(
        fake_get({"results": [{"id": "same", "title": "Device approval amended"}]})
    )
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
    service = MonitorService(
        settings,
        {
            "fda": FdaAdapter(
                fake_get({"results": [{"id": "same", "title": "Device approval"}]})
            )
        },
        repository=repository,
    )
    service.collect("fda")
    service.registry["fda"] = FdaAdapter(
        fake_get({"results": [{"id": "same", "title": "Device approval amended"}]})
    )
    service.collect("fda")
    service.registry["fda"] = FdaAdapter(lambda _url, _headers: (500, b"{}", {}))
    service.collect("fda")
    snapshot = repository.snapshot()
    assert len(snapshot["runs"]) == 3 and snapshot["runs"][0]["failures"]
    assert snapshot["events"][0]["data_mode"] == "LIVE_PUBLIC"
    assert (
        snapshot["events"][0]["publication_date"] is None
        or snapshot["events"][0]["collected_at"]
    )
    assert snapshot["health"][0]["state"] == "FAILED"
    assert (
        service.source_state(
            source_id="fda", last_success_at=None, now=service.runs[-1].started_at
        )
        == "UNAVAILABLE"
    )
    assert (
        service.source_state(
            source_id="fda",
            last_success_at=datetime.now(UTC) - timedelta(hours=49),
            now=datetime.now(UTC),
        )
        == "STALE"
    )


def test_monitor_registry_endpoint_is_internal_observability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An explicit empty process value overrides any developer-local .env token.
    monkeypatch.setenv("BTX_MONITOR_OPERATOR_TOKEN", "")
    get_settings.cache_clear()
    client = TestClient(create_app())
    response = client.get("/api/monitor/sources")
    assert response.status_code == 200
    assert {item["source_id"] for item in response.json()} >= {
        "sam_gov",
        "fda_openfda",
        "sec_edgar",
    }
    health = client.get("/api/monitor/health")
    assert health.status_code == 200 and {
        "sources",
        "last_runs",
        "clusters",
        "rejected_observations",
    } <= set(health.json())
    assert client.post("/api/monitor/collect/fda_openfda").status_code == 403
    assert client.post("/api/monitor/internal/collect/fda_openfda").status_code == 503

    monkeypatch.setenv("BTX_MONITOR_OPERATOR_TOKEN", "configured-but-private")
    get_settings.cache_clear()
    configured_client = TestClient(create_app())
    assert (
        configured_client.post("/api/monitor/internal/collect/fda_openfda").status_code
        == 403
    )
    assert (
        configured_client.post(
            "/api/monitor/internal/collect/fda_openfda",
            headers={"X-BTX-Monitor-Operator-Token": "wrong-token"},
        ).status_code
        == 403
    )
    get_settings.cache_clear()
    assert all(
        item["data_mode"] == "CURATED_PUBLIC"
        for item in health.json()["curated_preview"]
    )


def test_operational_collection_rejects_an_invalid_operator_token() -> None:
    runtime = PocRuntime(
        Settings(_env_file=None, monitor_operator_token="configured-but-private")
    )
    with pytest.raises(HTTPException, match="authorization failed"):
        operational_collect("fda_openfda", runtime, "wrong-token")


def test_live_monitor_event_projects_through_canonical_intelligence_contract() -> None:
    runtime = PocRuntime(Settings(_env_file=None, monitor_mode="live"))
    runtime.monitor = MonitorService(
        runtime.settings,
        {
            "fda": FdaAdapter(
                fake_get({"results": [{"id": "live-1", "title": "Device approval"}]})
            )
        },
    )
    runtime.monitor.collect("fda", limit=1)

    live = [
        item
        for item in intelligence_signals(runtime)
        if item.get("data_mode") == "CONNECTED"
    ]

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


def test_separate_worker_commit_reaches_running_api_with_identical_confidence(tmp_path):
    from btx_omni.monitor.briefs import signal_brief, signal_briefs_for_monitor

    worker = _durable_runtime(tmp_path)
    reader = PocRuntime(worker.settings)  # API exists before this scheduled write.
    assert not [
        item
        for item in intelligence_signals(reader)
        if item.get("data_mode") == "CONNECTED"
    ]
    worker.monitor.registry["fda_openfda"] = _fda(
        {
            "k_number": "K-CROSS-PROCESS",
            "device_name": "Medtronic device approval",
            "decision_date": "2026-09-08",
        }
    )
    run = worker.monitor.collect("fda_openfda", limit=1)
    assert not run.failures
    now = datetime(2026, 9, 8, 23, tzinfo=UTC)
    expected = signal_brief(
        next(iter(worker.monitor.events.values())),
        next(iter(worker.monitor.observations.values())),
        freshness_hours=worker.monitor.freshness_threshold_hours("fda_openfda"),
        now=now,
    )
    visible = [
        item
        for item in intelligence_signals(reader)
        if item.get("data_mode") == "CONNECTED"
    ]
    assert len(visible) == 1
    assert visible[0]["business_briefing"]["context_id"].endswith(
        ":medtronic"
    )
    assert "governed public update" not in visible[0]["relevance_explanation"].casefold()
    actual = signal_briefs_for_monitor(reader.monitor, now=now)[0]
    assert actual.signal_confidence == expected.signal_confidence
    assert actual.publication_timestamp == expected.publication_timestamp
    assert actual.signal_confidence["factors"][0]["points"] is not None
    worker.monitor.registry["fda_openfda"] = _fda(
        {
            "k_number": "K-CROSS-PROCESS",
            "device_name": "Medtronic charity award",
            "decision_date": "2026-09-08",
        }
    )
    correction = worker.monitor.collect("fda_openfda", limit=1)
    assert not correction.failures and correction.records_changed == 1
    assert not [
        item
        for item in intelligence_signals(reader)
        if item.get("data_mode") == "CONNECTED"
    ]
    assert len(signal_briefs_for_monitor(reader.monitor, now=now)) == 1


def test_seller_window_prioritizes_persisted_relevance_before_recency(monkeypatch):
    from btx_omni.monitor.briefs import SignalBrief, signal_briefs_for_monitor

    now = datetime(2026, 9, 15, tzinfo=UTC)

    def brief(event_id: str, published_at: datetime) -> SignalBrief:
        return SignalBrief(
            id=event_id,
            headline=event_id,
            what_happened=event_id,
            why_it_may_matter=event_id,
            canonical_account_ids=("honeywell",),
            canonical_program_id=None,
            markets=(),
            publication_timestamp=published_at,
            collection_timestamp=now,
            freshness="CURRENT",
            evidence_ids=(f"evidence:{event_id}",),
            source_url="https://example.com/source",
            source_system="test",
            data_mode="CONNECTED",
            resolution_state="RESOLVED",
            seller_promotion_state="RESOLVED_ELIGIBLE",
            what_to_watch="Review",
            recommended_action="Review",
            missing_fields=(),
            seller_summary=event_id,
        )

    briefs = {
        "older-relevant": brief("older-relevant", now - timedelta(days=10)),
        "newer-informational": brief(
            "newer-informational", now - timedelta(hours=1)
        ),
    }
    events = tuple(
        (
            SimpleNamespace(
                id=event_id,
                provenance=SimpleNamespace(source_system="test"),
                subject_entities=(
                    SimpleNamespace(canonical_account_id="honeywell"),
                ),
            ),
            None,
        )
        for event_id in briefs
    )

    class Repository:
        def current_intelligence_assessments(self, *, limit):
            assert limit >= 1000
            return (
                {
                    "event_id": "older-relevant",
                    "account_id": "honeywell",
                    "created_at": now - timedelta(days=1),
                    "projection": {
                        "priority_eligible": True,
                        "commercial_relevance_state": (
                            "ESTABLISHED_COMMERCIAL_RELEVANCE"
                        ),
                    },
                },
                {
                    "event_id": "newer-informational",
                    "account_id": "honeywell",
                    "created_at": now,
                    "projection": {
                        "priority_eligible": False,
                        "commercial_relevance_state": "INFORMATIONAL",
                    },
                },
            )

        def technical_decomposition_for_event(self, _event_id):
            return None

    monitor = SimpleNamespace(
        repository=Repository(),
        watch_targets={},
        freshness_threshold_hours=lambda _source_id: 24,
    )
    monkeypatch.setattr(
        "btx_omni.monitor.service.current_event_contexts", lambda _monitor: events
    )
    monkeypatch.setattr(
        "btx_omni.monitor.briefs.signal_brief",
        lambda event, _observation, **_kwargs: replace(briefs[event.id]),
    )

    projected = signal_briefs_for_monitor(
        monitor, now=now, projection_limit=1
    )

    assert [item.id for item in projected] == ["older-relevant"]


def test_governed_publisher_identity_does_not_copy_article_payload_into_entity_name():
    profile = AccountWatchProfile("lockheed-martin", "Lockheed Martin Corporation")
    source = "Public program update\n" + json.dumps(
        {"passages": ["Evidence body."] * 1000}
    )
    subject = MonitorCatalog((profile,)).resolve_subjects(
        source, source_identifiers=(("governed_source_owner", "lockheed-martin"),)
    )[0]
    assert subject.mention == "Lockheed Martin Corporation"
    assert subject.method == "governed_source_ownership"
    assert subject.canonical_account_id == "lockheed-martin"


def test_durable_monitor_events_rehydrate_after_runtime_restart_without_scoring_change(
    tmp_path,
) -> None:
    initial = _durable_runtime(tmp_path)
    initial.monitor.clock = lambda: datetime(2026, 8, 31, tzinfo=UTC)
    initial.monitor.registry["fda_openfda"] = _fda(
        {
            "k_number": "K-RESTART-MEDTRONIC",
            "device_name": "Medtronic device approval",
            "decision_date": "2026-08-15",
        }
    )
    score_before = calculate_account_attractiveness(
        AccountAttractivenessInputs(initial.sample.scoring_inputs["medtronic"]),
        evidence_ids=("medtronic-public-identity",),
        calculated_at=initial.observed_at(),
    )
    sample_commercial = tuple(
        (
            item.account_id,
            item.business_unit,
            item.ttm_revenue_minor,
            item.ttm_bookings_minor,
        )
        for item in initial.sample.commercial_contexts
    )
    initial.monitor.collect("fda_openfda")
    before_restart = [
        item
        for item in intelligence_signals(initial)
        if item.get("data_mode") == "CONNECTED"
    ]

    restarted = PocRuntime(initial.settings)
    after_restart = [
        item
        for item in intelligence_signals(restarted)
        if item.get("data_mode") == "CONNECTED"
    ]
    score_after = calculate_account_attractiveness(
        AccountAttractivenessInputs(restarted.sample.scoring_inputs["medtronic"]),
        evidence_ids=("medtronic-public-identity",),
        calculated_at=restarted.observed_at(),
    )

    assert len(before_restart) == len(after_restart) == 1
    assert before_restart[0]["id"] == after_restart[0]["id"]
    assert after_restart[0]["account_id"] == "medtronic"
    assert (
        after_restart[0]["source_url"]
        and after_restart[0]["provenance"].source_record_id == "K-RESTART-MEDTRONIC"
    )
    assert len(restarted.monitor.events) == 1
    restarted.monitor.hydrate_events()
    assert len(restarted.monitor.events) == 1
    assert score_before.score == score_after.score
    assert (
        tuple(
            (
                item.account_id,
                item.business_unit,
                item.ttm_revenue_minor,
                item.ttm_bookings_minor,
            )
            for item in restarted.sample.commercial_contexts
        )
        == sample_commercial
    )


def test_durable_restart_rehydrates_but_excludes_noneligible_events(tmp_path) -> None:
    initial = _durable_runtime(tmp_path)
    initial.monitor.clock = lambda: datetime(2026, 8, 31, tzinfo=UTC)
    repository = initial.monitor.repository
    assert repository is not None
    sample = initial.sample
    services = (
        MonitorService(
            initial.settings,
            {
                "resolved": _fda(
                    {
                        "k_number": "K-RESOLVED",
                        "device_name": "Medtronic device approval",
                        "decision_date": "2026-08-15",
                    }
                )
            },
            repository=repository,
            watch_profiles=sample.watch_profiles,
            catalog=initial.monitor.catalog,
        ),
        MonitorService(
            initial.settings,
            {
                "unresolved": _fda(
                    {
                        "k_number": "K-UNRESOLVED",
                        "device_name": "Unknown device approval",
                        "decision_date": "2026-08-15",
                    }
                )
            },
            repository=repository,
            watch_profiles=sample.watch_profiles,
            catalog=initial.monitor.catalog,
        ),
        MonitorService(
            initial.settings,
            {
                "rejected": _fda(
                    {
                        "k_number": "K-REJECTED",
                        "device_name": "Medtronic charity award",
                        "decision_date": "2026-08-15",
                    }
                )
            },
            repository=repository,
            watch_profiles=sample.watch_profiles,
            catalog=initial.monitor.catalog,
        ),
        MonitorService(
            initial.settings,
            {
                "ambiguous": _fda(
                    {
                        "k_number": "K-AMBIGUOUS",
                        "device_name": "Acme Systems device approval",
                        "decision_date": "2026-08-15",
                    }
                )
            },
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
    for service, source_id in zip(
        services, ("resolved", "unresolved", "rejected", "ambiguous"), strict=True
    ):
        service.clock = lambda: datetime(2026, 8, 31, tzinfo=UTC)
        service.collect(source_id)

    restarted = PocRuntime(initial.settings)
    projected = [
        item
        for item in intelligence_signals(restarted)
        if item.get("data_mode") == "CONNECTED"
    ]
    states = {
        event.id: event.seller_relevance_state.value
        for event in restarted.monitor.events.values()
    }

    assert len(restarted.monitor.events) == 4
    assert len(projected) == 1 and projected[0]["account_id"] == "medtronic"
    assert set(states.values()) == {
        "RESOLVED_ELIGIBLE",
        "UNRESOLVED",
        "REJECTED",
        "AMBIGUOUS",
    }
