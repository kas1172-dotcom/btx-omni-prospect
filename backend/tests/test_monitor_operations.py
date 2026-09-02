from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine

from btx_omni.ai.contracts import (
    LanguageProviderError,
    LanguageResult,
    ProviderStatus,
)
from btx_omni.api.monitor import monitor_health, sources
from btx_omni.api.runtime import PocRuntime
from btx_omni.core.config import Settings
from btx_omni.monitor.briefs import (
    BriefRetryPolicy,
    apply_cached_synthesis,
    governed_content_hash,
    process_signal_brief_synthesis,
    publication_freshness,
    signal_brief,
    signal_briefs_for_monitor,
    synthesize_signal_brief,
)
from btx_omni.monitor.catalog import MonitorCatalog
from btx_omni.monitor.contracts import CollectionRun
from btx_omni.monitor.ontology import (
    ResolutionState,
    SellerRelevanceState,
    SourceHealthState,
)
from btx_omni.monitor.repository import MonitorRepository
from btx_omni.monitor.service import MonitorService
from btx_omni.monitor.sources import REGISTRY, FdaAdapter
from btx_omni.monitor.targeting import StrategicWatchUniverse, TargetReason
from btx_omni.monitor.worker import run_worker
from btx_omni.persistence.models import metadata
from btx_omni.providers.sample.environment import build_sample_environment

NOW = datetime(2026, 8, 28, 12, tzinfo=UTC)


def _get(payload: object, status: int = 200):
    def get(_url: str, _headers: dict[str, str]):
        return status, json.dumps(payload).encode(), {}

    return get


def _service(tmp_path, adapter: FdaAdapter) -> MonitorService:
    engine = create_engine(f"sqlite:///{tmp_path / 'monitor.db'}")
    metadata.create_all(engine)
    sample = build_sample_environment()
    return MonitorService(
        Settings(
            _env_file=None, monitor_mode="live", monitor_durable_state_enabled=True
        ),
        {"fda_openfda": adapter},
        repository=MonitorRepository(engine),
        watch_profiles=sample.watch_profiles,
        catalog=MonitorCatalog(
            sample.watch_profiles, sample.programs, sample.facilities
        ),
        clock=lambda: NOW,
    )


def test_source_registry_truthfully_describes_collectability_and_requirements() -> None:
    settings = Settings(_env_file=None, monitor_mode="live", sam_api_key=None)
    states = {
        source_id: adapter.available(settings)
        for source_id, adapter in REGISTRY.items()
    }

    assert states["sam_gov"] == (False, "SAM_API_KEY is not configured")
    assert states["usaspending"][0] is False
    assert states["federal_register"][0] is True
    assert states["nasa"][0] is True
    assert states["fda_openfda"][0] is True
    assert states["sec_edgar"][0] is False
    assert states["dod"][0] is True
    assert states["commerce"] == (False, "BTX_COMMERCE_API_KEY is not configured")
    assert states["company_newsroom"][0] is False
    assert states["state_economic_development"][0] is False
    assert (
        REGISTRY["nasa"].definition.content_structure
        == "OFFICIAL_RSS_WITH_UNSTRUCTURED_TEXT"
    )
    assert not REGISTRY["dod"].definition.seller_promotion_permitted
    assert REGISTRY["usaspending"].definition.consumes_strategic_targets
    assert REGISTRY["usaspending"].definition.targeting_mode == "ACCOUNT_TARGETED"
    assert all(
        not adapter.definition.consumes_strategic_targets
        for source_id, adapter in REGISTRY.items()
        if source_id != "usaspending"
    )


def test_watch_universe_is_stable_bounded_and_provenance_preserving() -> None:
    sample = build_sample_environment()
    policy = StrategicWatchUniverse(
        accounts=sample.accounts,
        profiles=sample.watch_profiles,
        facilities=sample.facilities,
        scenario_account_ids=frozenset(sample.rich_scenarios),
    )

    targets = policy.targets_for(REGISTRY["usaspending"].definition, cap=7)

    assert len(targets) == 7
    assert targets == policy.targets_for(REGISTRY["usaspending"].definition, cap=7)
    assert targets[0].canonical_account_id == "boeing"
    assert "EXISTING_GOVERNED_WATCH_PROFILE" in {
        reason.code for reason in targets[0].reasons
    }
    assert all(reason.source_system for target in targets for reason in target.reasons)
    assert not any(
        hasattr(target, field)
        for target in targets
        for field in ("rank", "score", "relationship_strength", "commercial_history")
    )


def test_durable_collection_preserves_cursor_and_success_across_partial_failure(
    tmp_path,
) -> None:
    service = _service(
        tmp_path,
        FdaAdapter(
            _get(
                {
                    "results": [
                        {
                            "k_number": "K-OPS",
                            "device_name": "Medtronic device approval",
                            "decision_date": "2026-08-20",
                        }
                    ]
                }
            )
        ),
    )
    successful = service.collect("fda_openfda")
    service.registry["fda_openfda"] = FdaAdapter(_get({}, 500))
    failed = service.collect("fda_openfda")
    snapshot = service.repository.snapshot() if service.repository else None

    assert successful.cursor and successful.cursor.source_id == "fda_openfda"
    assert failed.failures == ("HTTP_500",)
    assert service.health["fda_openfda"].last_success_at == successful.completed_at
    assert snapshot and len(snapshot["runs"]) == 2
    assert snapshot["events"] and snapshot["health"][0]["state"] == "FAILED"
    assert snapshot["health"][0]["last_success_at"] is not None


def test_operational_states_cover_disabled_not_configured_never_failed_and_stale(
    tmp_path,
) -> None:
    service = _service(tmp_path, FdaAdapter(_get({"results": []})))
    assert (
        service.operational_status("fda_openfda", now=NOW).state
        is SourceHealthState.NEVER_ATTEMPTED
    )
    disabled = Settings(
        _env_file=None,
        monitor_mode="disabled",
        monitor_durable_state_enabled=True,
        database_url=service.settings.database_url,
    )
    service.settings = disabled
    assert (
        service.operational_status("fda_openfda", now=NOW).state
        is SourceHealthState.DISABLED
    )
    service.settings = Settings(
        _env_file=None,
        monitor_mode="live",
        monitor_durable_state_enabled=True,
        database_url=service.settings.database_url,
    )
    service.registry["sam_gov"] = REGISTRY["sam_gov"]
    assert (
        service.operational_status("sam_gov", now=NOW).state
        is SourceHealthState.NOT_CONFIGURED
    )
    assert (
        service.operational_status(
            "fda_openfda",
            now=NOW,
            durable_health={
                "last_attempt_at": NOW - timedelta(hours=2),
                "last_success_at": None,
                "detail": "HTTP_500",
                "state": "FAILED",
            },
        ).state
        is SourceHealthState.FAILED
    )
    assert (
        service.operational_status(
            "fda_openfda",
            now=NOW,
            durable_health={
                "last_attempt_at": NOW - timedelta(hours=60),
                "last_success_at": NOW - timedelta(hours=60),
                "detail": None,
                "state": "HEALTHY",
            },
        ).state
        is SourceHealthState.STALE
    )


def test_signal_brief_uses_publication_freshness_and_blocks_unresolved_promotion(
    tmp_path,
) -> None:
    service = _service(
        tmp_path,
        FdaAdapter(
            _get(
                {
                    "results": [
                        {
                            "k_number": "K-BRIEF",
                            "device_name": "Unknown device approval",
                            "decision_date": "2026-01-01",
                        }
                    ]
                }
            )
        ),
    )
    service.collect("fda_openfda")
    event = next(iter(service.events.values()))
    observation = next(iter(service.observations.values()))
    brief = signal_brief(event, observation, freshness_hours=48, now=NOW)

    assert brief.freshness == "STALE"
    assert brief.recommended_action is None
    assert brief.canonical_account_ids == ()
    assert "canonical Customer resolution" in brief.missing_fields
    assert brief.evidence_ids and brief.source_url
    assert brief.event_timing == "OBSERVED"
    assert "REGULATORY_APPROVAL" not in brief.headline
    assert (
        publication_freshness(None, collected_at=NOW, threshold_hours=48, now=NOW)
        == "PUBLICATION_DATE_UNAVAILABLE"
    )


def test_injected_collection_clock_controls_generated_monitor_timestamps(tmp_path) -> None:
    service = _service(
        tmp_path,
        FdaAdapter(
            _get(
                {
                    "results": [
                        {
                            "k_number": "K-CLOCK",
                            "device_name": "Medtronic device approval",
                            "decision_date": "2026-08-28",
                        }
                    ]
                }
            )
        ),
    )

    run = service.collect("fda_openfda")
    observation = next(iter(service.observations.values()))

    assert run.started_at == run.completed_at == NOW
    assert observation.observed_at == NOW
    assert observation.source_version.first_seen_at == NOW
    assert observation.raw_evidence.captured_at == NOW
    assert observation.source_published_at == datetime(2026, 8, 28, tzinfo=UTC)
    assert publication_freshness(
        observation.source_published_at,
        collected_at=observation.observed_at,
        threshold_hours=48,
        now=NOW,
    ) == "CURRENT"


def test_future_collection_timestamp_remains_withheld(tmp_path) -> None:
    service = _service(tmp_path, FdaAdapter(_get({"results": []})))

    assert publication_freshness(
        NOW,
        collected_at=NOW + timedelta(seconds=1),
        threshold_hours=48,
        now=NOW,
    ) == "STALE"
    assert service.clock().tzinfo is UTC


class _BriefProvider:
    name = "gemini"
    configured = True

    def __init__(self) -> None:
        self.calls = 0

    def synthesize(self, request):
        self.calls += 1
        return LanguageResult(
            "Seller-readable governed summary.", "gemini", "fake", request.evidence_ids
        )


class _FailingProvider(_BriefProvider):
    def synthesize(self, request):
        self.calls += 1
        raise RuntimeError("provider unavailable")


class _StatusProvider(_BriefProvider):
    def __init__(self, status: ProviderStatus) -> None:
        super().__init__()
        self.status = status

    def synthesize(self, request):
        self.calls += 1
        raise LanguageProviderError(self.status)


class _UnconfiguredProvider(_BriefProvider):
    configured = False


class _CountingProvider(_BriefProvider):
    def __init__(self) -> None:
        super().__init__()


def test_gemini_brief_synthesis_cannot_change_governed_metadata(tmp_path) -> None:
    service = _service(
        tmp_path,
        FdaAdapter(
            _get(
                {
                    "results": [
                        {
                            "k_number": "K-GEMINI",
                            "device_name": "Medtronic device approval",
                            "decision_date": "2026-08-28",
                        }
                    ]
                }
            )
        ),
    )
    service.collect("fda_openfda")
    event = next(iter(service.events.values()))
    event = replace(
        event,
        resolution_state=ResolutionState.RESOLVED,
        seller_relevance_state=SellerRelevanceState.RESOLVED_ELIGIBLE,
    )
    observation = next(iter(service.observations.values()))
    brief = signal_brief(event, observation, freshness_hours=48, now=NOW)
    assert (brief.resolution_state, brief.seller_promotion_state, brief.freshness) == (
        "RESOLVED",
        "RESOLVED_ELIGIBLE",
        "CURRENT",
    )
    synthesized = synthesize_signal_brief(brief, _BriefProvider())

    assert synthesized.seller_summary == "Seller-readable governed summary."
    assert (
        replace(
            synthesized,
            seller_summary=brief.seller_summary,
            language_provider=None,
            summary_mode="DETERMINISTIC",
        )
        == brief
    )
    assert synthesize_signal_brief(brief, _FailingProvider()) == brief


def test_brief_synthesis_never_invokes_provider_for_ineligible_truth_states(tmp_path) -> None:
    service = _service(
        tmp_path,
        FdaAdapter(
            _get(
                {
                    "results": [
                        {
                            "k_number": "K-GATED",
                            "device_name": "Medtronic device approval",
                            "decision_date": "2026-08-28",
                        }
                    ]
                }
            )
        ),
    )
    service.collect("fda_openfda")
    event = next(iter(service.events.values()))
    observation = next(iter(service.observations.values()))
    eligible = signal_brief(
        replace(event, seller_relevance_state=SellerRelevanceState.RESOLVED_ELIGIBLE),
        observation,
        freshness_hours=48,
        now=NOW,
    )
    provider = _CountingProvider()

    guarded = (
        replace(eligible, seller_promotion_state="REVIEW_REQUIRED"),
        replace(eligible, freshness="STALE"),
        replace(eligible, resolution_state="UNRESOLVED"),
        replace(
            eligible,
            publication_timestamp=None,
            relevant_event_timestamp=None,
            event_timing="UNKNOWN",
            freshness="PUBLICATION_DATE_UNAVAILABLE",
        ),
    )
    assert all(synthesize_signal_brief(item, provider) == item for item in guarded)
    process_signal_brief_synthesis(
        guarded,
        provider=provider,
        repository=service.repository,
        cap=4,
        now=NOW,
    )
    assert provider.calls == 0


def test_worker_runs_only_configured_sources_and_reports_partial_failure(
    monkeypatch,
) -> None:
    class Adapter:
        def __init__(self, available: bool):
            self._available = available

        def available(self, settings):
            return self._available, None if self._available else "not configured"

    class Monitor:
        def __init__(self):
            self.registry = {
                "good": Adapter(True),
                "bad": Adapter(True),
                "off": Adapter(False),
            }

        def collect(self, source_id, limit, **_kwargs):
            return CollectionRun(
                source_id,
                source_id,
                NOW,
                NOW,
                None,
                records_seen=1,
                failures=("HTTP_500",) if source_id == "bad" else (),
            )

    class Runtime:
        def __init__(self, settings):
            self.monitor = Monitor()

    monkeypatch.setattr("btx_omni.monitor.worker.PocRuntime", Runtime)
    settings = Settings(
        _env_file=None,
        monitor_mode="live",
        monitor_durable_state_enabled=True,
        monitor_worker_sources="good,bad,off",
    )
    report, code = run_worker(settings)

    assert code == 1 and report["configured_sources"] == ("good", "bad")
    assert report["skipped_sources"] == ("off",)
    assert report["failed_sources"] == ("bad",)
    assert {run["source_id"] for run in report["runs"]} == {"good", "bad"}


def test_worker_fails_closed_when_another_worker_holds_the_lock(monkeypatch) -> None:
    class Lock:
        def __enter__(self):
            return False

        def __exit__(self, *_args):
            return None

    class Repository:
        def operational_lock(self):
            return Lock()

    class Runtime:
        def __init__(self, settings):
            self.monitor = type(
                "Monitor", (), {"repository": Repository(), "registry": {}}
            )()

    monkeypatch.setattr("btx_omni.monitor.worker.PocRuntime", Runtime)
    report, code = run_worker(
        Settings(
            _env_file=None, monitor_mode="live", monitor_durable_state_enabled=True
        )
    )

    assert code == 3 and report["status"] == "OVERLAP_SKIPPED"


def test_worker_enforces_collection_deadline_preserves_completed_runs_and_releases_lock(monkeypatch) -> None:
    released = False
    persisted: list[str] = []

    class Lock:
        def __enter__(self):
            return True

        def __exit__(self, *_args):
            nonlocal released
            released = True

    class Repository:
        def operational_lock(self):
            return Lock()

        def snapshot(self):
            return {"health": (), "runs": (), "events": (), "rejected": ()}

        def persist_snapshot(self, **values):
            persisted.append(values["run"].source_id)

    class Adapter:
        definition = REGISTRY["fda_openfda"].definition

        def __init__(self, delay: float):
            self.delay = delay

        def available(self, settings):
            return True, None

        def collect(self, **_kwargs):
            time.sleep(self.delay)
            return []

    settings = Settings(
        _env_file=None,
        monitor_mode="live",
        monitor_durable_state_enabled=True,
        monitor_worker_sources="fast,slow",
        monitor_worker_max_seconds=0.15,
        monitor_source_min_start_seconds=0.01,
    )
    monitor = MonitorService(
        settings,
        {"fast": Adapter(0), "slow": Adapter(1)},
        repository=Repository(),  # type: ignore[arg-type]
    )

    class Runtime:
        def __init__(self, _settings):
            self.monitor = monitor

    monkeypatch.setattr("btx_omni.monitor.worker.PocRuntime", Runtime)
    monkeypatch.delattr("btx_omni.monitor.service.signal.setitimer", raising=False)
    started = time.monotonic()
    report, code = run_worker(settings)
    elapsed = time.monotonic() - started

    assert code == 1 and report["status"] == "DEADLINE_EXHAUSTED"
    assert elapsed < 0.5
    assert persisted == ["fast", "slow"]
    assert report["runs"][0]["failures"] == ()
    assert report["runs"][1]["failures"] == ("DEADLINE_EXCEEDED",)
    assert released


def test_signal_brief_timing_and_watch_reasons_are_governed(tmp_path) -> None:
    service = _service(
        tmp_path,
        FdaAdapter(
            _get(
                {
                    "results": [
                        {
                            "k_number": "K-TIMING",
                            "device_name": "Medtronic device approval",
                            "decision_date": "2026-09-01",
                        }
                    ]
                }
            )
        ),
    )
    service.collect("fda_openfda")
    event = next(iter(service.events.values()))
    observation = next(iter(service.observations.values()))
    reason = TargetReason("BTX_TOP_100_REFERENCE", "Governed watch membership.", "SANITIZED_REFERENCE", "row-1")
    upcoming = signal_brief(event, observation, freshness_hours=48, now=NOW, target_reasons=(reason,))
    unknown = signal_brief(replace(event, event_date=None), replace(observation, source_published_at=None), freshness_hours=48, now=NOW)

    assert upcoming.event_timing == "UPCOMING"
    assert upcoming.relevant_event_timestamp == datetime(2026, 9, 1, tzinfo=UTC)
    assert upcoming.watchlist_eligible and upcoming.priority_reasons == (reason,)
    assert unknown.event_timing == "UNKNOWN" and unknown.relevant_event_timestamp is None
    assert not unknown.watchlist_eligible and unknown.priority_reasons == ()
    assert not any(hasattr(upcoming, name) for name in ("rank", "relationship_strength", "customer_status", "score"))


def test_monitor_health_reuses_durable_synthesis_without_model_calls(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        monitor_mode="live",
        monitor_durable_state_enabled=True,
        database_url=f"sqlite:///{tmp_path / 'projection.db'}",
        gemini_api_key="configured-for-fake-only",
    )
    engine = create_engine(settings.database_url)
    metadata.create_all(engine)
    runtime = PocRuntime(settings)
    runtime.monitor.clock = lambda: NOW
    runtime.monitor.registry["fda_openfda"] = FdaAdapter(
        _get({"results": [{"k_number": "K-PROJECTION", "device_name": "Medtronic device approval", "decision_date": "2026-08-28"}]})
    )
    runtime.monitor.collect("fda_openfda")
    event_id = next(iter(runtime.monitor.events))
    runtime.monitor.events[event_id] = replace(
        runtime.monitor.events[event_id],
        resolution_state=ResolutionState.RESOLVED,
        seller_relevance_state=SellerRelevanceState.RESOLVED_ELIGIBLE,
    )
    provider = _BriefProvider()
    deterministic = signal_briefs_for_monitor(runtime.monitor, now=NOW)
    batch = process_signal_brief_synthesis(
        deterministic,
        provider=provider,
        repository=runtime.monitor.repository,
        cap=3,
        now=NOW,
    )
    assert batch.attempted == batch.assisted == provider.calls == 1

    first = monitor_health(runtime)
    second = monitor_health(runtime)
    assisted = next(item for item in first["signal_briefs"] if item.id == event_id)

    # The synthesis was written for the August 28 governed state.  Health
    # recomputes freshness at read time, so its later governed hash must not
    # reuse the cached prose.
    assert assisted.summary_mode == "DETERMINISTIC"
    assert assisted.seller_summary != "Seller-readable governed summary."
    assert first["brief_synthesis_status"] == "UNAVAILABLE"
    assert next(item for item in second["signal_briefs"] if item.id == event_id) == assisted
    assert provider.calls == 1


def test_monitor_health_multiple_eligible_briefs_never_constructs_provider(
    monkeypatch, tmp_path
) -> None:
    settings = Settings(
        _env_file=None,
        monitor_mode="live",
        monitor_durable_state_enabled=True,
        database_url=f"sqlite:///{tmp_path / 'health-many.db'}",
        gemini_api_key="configured-but-must-not-be-used",
    )
    engine = create_engine(settings.database_url)
    metadata.create_all(engine)
    runtime = PocRuntime(settings)
    runtime.monitor.registry["fda_openfda"] = FdaAdapter(
        _get(
            {
                "results": [
                    {
                        "k_number": f"K-HEALTH-{index}",
                        "device_name": "Medtronic device approval",
                        "decision_date": "2026-08-28",
                    }
                    for index in range(8)
                ]
            }
        )
    )
    runtime.monitor.collect("fda_openfda")
    runtime.monitor.events = {
        event_id: replace(
            event,
            resolution_state=ResolutionState.RESOLVED,
            seller_relevance_state=SellerRelevanceState.RESOLVED_ELIGIBLE,
        )
        for event_id, event in runtime.monitor.events.items()
    }
    provider_constructions = 0

    def forbidden_provider(_config):
        nonlocal provider_constructions
        provider_constructions += 1
        raise AssertionError("Monitor health must not construct an AI provider")

    monkeypatch.setattr("btx_omni.ai.registry.get_ai_provider", forbidden_provider)
    assert len(monitor_health(runtime)["signal_briefs"]) == 8
    assert len(monitor_health(runtime)["signal_briefs"]) == 8
    assert provider_constructions == 0


def test_synthesis_cache_hash_invalidation_eligibility_and_cap(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'cache.db'}")
    metadata.create_all(engine)
    repository = MonitorRepository(engine)
    service = _service(
        tmp_path,
        FdaAdapter(
            _get(
                {
                    "results": [
                        {
                            "k_number": "K-CACHE",
                            "device_name": "Medtronic device approval",
                            "decision_date": "2026-08-28",
                        }
                    ]
                }
            )
        ),
    )
    service.collect("fda_openfda")
    event_id = next(iter(service.events))
    service.events[event_id] = replace(
        service.events[event_id],
        resolution_state=ResolutionState.RESOLVED,
        seller_relevance_state=SellerRelevanceState.RESOLVED_ELIGIBLE,
    )
    original = signal_briefs_for_monitor(service, now=NOW)[0]
    provider = _BriefProvider()

    first = process_signal_brief_synthesis(
        (original,), provider=provider, repository=repository, cap=1, now=NOW
    )
    repeated = process_signal_brief_synthesis(
        (original,), provider=provider, repository=repository, cap=1, now=NOW
    )
    cached = repository.brief_synthesis(
        original.id, governed_content_hash(original)
    )
    assert first.attempted == 1 and repeated.reused == 1 and provider.calls == 1
    assert apply_cached_synthesis(original, cached).summary_mode == "GEMINI_ASSISTED"

    changed = replace(original, what_happened="Governed source content changed.")
    assert governed_content_hash(changed) != governed_content_hash(original)
    assert apply_cached_synthesis(changed, cached) == changed
    process_signal_brief_synthesis(
        (changed,), provider=provider, repository=repository, cap=1, now=NOW
    )
    assert provider.calls == 2
    assert repository.brief_synthesis_count() == 1
    stale = replace(changed, freshness="STALE", seller_promotion_state="WITHHELD_STALE")
    assert apply_cached_synthesis(
        stale, repository.brief_synthesis(changed.id, governed_content_hash(changed))
    ) == stale

    candidates = tuple(replace(original, id=f"brief-{index}") for index in range(4))
    capped_provider = _BriefProvider()
    capped = process_signal_brief_synthesis(
        candidates,
        provider=capped_provider,
        repository=repository,
        cap=2,
        now=NOW,
    )
    assert capped.attempted == capped_provider.calls == 2 and capped.capped


def test_not_configured_does_not_consume_attempt_and_recovers_immediately(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'not-configured.db'}")
    metadata.create_all(engine)
    repository = MonitorRepository(engine)
    service = _service(
        tmp_path,
        FdaAdapter(
            _get(
                {
                    "results": [
                        {
                            "k_number": "K-NOT-CONFIGURED",
                            "device_name": "Medtronic device approval",
                            "decision_date": "2026-08-28",
                        }
                    ]
                }
            )
        ),
    )
    service.collect("fda_openfda")
    event_id = next(iter(service.events))
    service.events[event_id] = replace(
        service.events[event_id],
        resolution_state=ResolutionState.RESOLVED,
        seller_relevance_state=SellerRelevanceState.RESOLVED_ELIGIBLE,
    )
    brief = signal_briefs_for_monitor(service, now=NOW)[0]
    unconfigured = _UnconfiguredProvider()

    first = process_signal_brief_synthesis(
        (brief,), provider=unconfigured, repository=repository, cap=1, now=NOW
    )
    second = process_signal_brief_synthesis(
        (brief,),
        provider=unconfigured,
        repository=repository,
        cap=1,
        now=NOW + timedelta(days=1),
    )
    cached = repository.brief_synthesis(brief.id, governed_content_hash(brief))
    assert first.attempted == second.attempted == unconfigured.calls == 0
    assert first.deferred == second.deferred == 1
    assert cached["status"] == "NOT_CONFIGURED"
    assert cached["attempt_count"] == 0 and cached["next_retry_at"] is None

    configured = _BriefProvider()
    recovered = process_signal_brief_synthesis(
        (brief,), provider=configured, repository=repository, cap=1, now=NOW
    )
    assert recovered.attempted == recovered.assisted == configured.calls == 1
    assert repository.brief_synthesis_count() == 1


def test_provider_failures_retry_after_status_cooldown_and_then_reuse(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'failures.db'}")
    metadata.create_all(engine)
    repository = MonitorRepository(engine)
    service = _service(
        tmp_path,
        FdaAdapter(
            _get(
                {
                    "results": [
                        {
                            "k_number": "K-FAILURE",
                            "device_name": "Medtronic device approval",
                            "decision_date": "2026-08-28",
                        }
                    ]
                }
            )
        ),
    )
    service.collect("fda_openfda")
    event_id = next(iter(service.events))
    service.events[event_id] = replace(
        service.events[event_id],
        resolution_state=ResolutionState.RESOLVED,
        seller_relevance_state=SellerRelevanceState.RESOLVED_ELIGIBLE,
    )
    brief = signal_briefs_for_monitor(service, now=NOW)[0]
    policy = BriefRetryPolicy(
        auth_failed_seconds=10,
        timeout_seconds=20,
        quota_seconds=40,
        unavailable_seconds=30,
    )
    delays = {
        ProviderStatus.AUTH_FAILED: 10,
        ProviderStatus.TIMEOUT: 20,
        ProviderStatus.QUOTA: 40,
        ProviderStatus.UNAVAILABLE: 30,
    }

    for index, status in enumerate(delays):
        candidate = replace(brief, id=f"failure-{index}")
        provider = _StatusProvider(status)
        result = process_signal_brief_synthesis(
            (candidate,),
            provider=provider,
            repository=repository,
            cap=1,
            retry_policy=policy,
            now=NOW,
        )
        cached = repository.brief_synthesis(
            candidate.id, governed_content_hash(candidate)
        )
        assert result.statuses == (status,) and provider.calls == 1
        assert cached["status"] == status.value and cached["summary"] is None
        assert cached["attempt_count"] == 1
        assert cached["next_retry_at"] == NOW + timedelta(seconds=delays[status])
        assert apply_cached_synthesis(candidate, cached) == candidate

        deferred = process_signal_brief_synthesis(
            (candidate,),
            provider=provider,
            repository=repository,
            cap=1,
            retry_policy=policy,
            now=NOW + timedelta(seconds=delays[status] - 1),
        )
        assert deferred.attempted == 0 and deferred.deferred == 1
        assert provider.calls == 1

        recovered_provider = _BriefProvider()
        recovered = process_signal_brief_synthesis(
            (candidate,),
            provider=recovered_provider,
            repository=repository,
            cap=1,
            retry_policy=policy,
            now=NOW + timedelta(seconds=delays[status]),
        )
        successful = repository.brief_synthesis(
            candidate.id, governed_content_hash(candidate)
        )
        assert recovered.attempted == recovered.assisted == 1
        assert successful["status"] == "AVAILABLE"
        assert successful["attempt_count"] == 2
        never_again = _BriefProvider()
        reused = process_signal_brief_synthesis(
            (candidate,),
            provider=never_again,
            repository=repository,
            cap=1,
            retry_policy=policy,
            now=NOW + timedelta(days=365),
        )
        assert reused.reused == 1 and never_again.calls == 0

    assert repository.brief_synthesis_count() == len(delays)


def test_changed_failure_hash_retries_immediately_and_retry_cap_is_enforced(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'retry-cap.db'}")
    metadata.create_all(engine)
    repository = MonitorRepository(engine)
    service = _service(
        tmp_path,
        FdaAdapter(
            _get(
                {
                    "results": [
                        {
                            "k_number": "K-RETRY-CAP",
                            "device_name": "Medtronic device approval",
                            "decision_date": "2026-08-28",
                        }
                    ]
                }
            )
        ),
    )
    service.collect("fda_openfda")
    event_id = next(iter(service.events))
    service.events[event_id] = replace(
        service.events[event_id],
        resolution_state=ResolutionState.RESOLVED,
        seller_relevance_state=SellerRelevanceState.RESOLVED_ELIGIBLE,
    )
    brief = signal_briefs_for_monitor(service, now=NOW)[0]
    failed = _StatusProvider(ProviderStatus.TIMEOUT)
    process_signal_brief_synthesis(
        (brief,), provider=failed, repository=repository, cap=1, now=NOW
    )
    changed = replace(brief, what_happened="New governed content")
    changed_provider = _BriefProvider()
    process_signal_brief_synthesis(
        (changed,), provider=changed_provider, repository=repository, cap=1, now=NOW
    )
    assert changed_provider.calls == 1 and repository.brief_synthesis_count() == 1

    retry_candidates = tuple(replace(brief, id=f"retry-{index}") for index in range(2))
    failure_provider = _StatusProvider(ProviderStatus.TIMEOUT)
    process_signal_brief_synthesis(
        retry_candidates,
        provider=failure_provider,
        repository=repository,
        cap=2,
        retry_policy=BriefRetryPolicy(timeout_seconds=1),
        now=NOW,
    )
    retry_provider = _BriefProvider()
    retry_batch = process_signal_brief_synthesis(
        retry_candidates,
        provider=retry_provider,
        repository=repository,
        cap=1,
        retry_policy=BriefRetryPolicy(timeout_seconds=1),
        now=NOW + timedelta(seconds=1),
    )
    assert retry_batch.attempted == retry_provider.calls == 1
    assert retry_batch.capped
    assert repository.brief_synthesis_count() == 3


def test_worker_readiness_does_not_claim_scheduler_truth(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        monitor_mode="live",
        monitor_durable_state_enabled=True,
        monitor_schedule_configured=False,
        database_url=f"sqlite:///{tmp_path / 'readiness.db'}",
    )
    engine = create_engine(settings.database_url)
    metadata.create_all(engine)
    runtime = PocRuntime(settings)
    response = monitor_health(runtime)

    assert response["worker_runtime_state"] == "WORKER_READY_FOR_INVOCATION"
    assert response["scheduler_state"] == "SCHEDULE_NOT_CONFIRMED"
    assert not response["collection_enabled"]
    assert "does not confirm an active schedule" in response["seller_message"]


def test_source_projection_reports_only_usaspending_as_target_consumer(tmp_path) -> None:
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'sources.db'}")
    engine = create_engine(settings.database_url)
    metadata.create_all(engine)
    projected = sources(PocRuntime(settings))

    consumers = {item["source_id"] for item in projected if item["consumes_strategic_targets"]}
    assert consumers == {"usaspending"}
    assert next(item for item in projected if item["source_id"] == "usaspending")["targeting_mode"] == "ACCOUNT_TARGETED"
    assert all(
        item["targeting_mode"] in {"BROAD_PUBLIC_FEED", "NOT_CONFIGURED"}
        for item in projected
        if item["source_id"] != "usaspending"
    )
