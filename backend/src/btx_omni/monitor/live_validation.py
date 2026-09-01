"""Manual bounded proof of the governed public-source Monitor pipeline.

This module is deliberately not a scheduler and is never used by application
startup or tests.  It creates a temporary SQLite MonitorRepository solely to
exercise the normal collection, normalization, resolution, persistence, and
Signal Brief projection boundaries against selected public sources.
"""

from __future__ import annotations

import argparse
import json
from tempfile import TemporaryDirectory
from time import monotonic

from sqlalchemy import create_engine

from btx_omni.core.config import Settings
from btx_omni.monitor.briefs import signal_briefs_for_monitor
from btx_omni.monitor.catalog import MonitorCatalog
from btx_omni.monitor.repository import MonitorRepository
from btx_omni.monitor.service import MonitorService
from btx_omni.monitor.sources import REGISTRY, SecEdgarAdapter, UsaSpendingAdapter
from btx_omni.monitor.targeting import StrategicWatchUniverse
from btx_omni.monitor.usaspending import recipient_query_names
from btx_omni.persistence.models import metadata
from btx_omni.providers.sample.environment import build_sample_environment


def _service(*, database_url: str, target_limit: int) -> MonitorService:
    sample = build_sample_environment()
    settings = Settings(
        _env_file=None,
        monitor_mode="live",
        monitor_durable_state_enabled=True,
        monitor_source_target_limit=target_limit,
        database_url=database_url,
    )
    universe = StrategicWatchUniverse(
        accounts=sample.accounts,
        profiles=sample.watch_profiles,
        facilities=sample.facilities,
        scenario_account_ids=frozenset(sample.rich_scenarios),
    )
    targets = universe.targets_for(REGISTRY["usaspending"].definition, cap=target_limit)
    registry = dict(REGISTRY)
    registry["usaspending"] = UsaSpendingAdapter(
        recipient_names=recipient_query_names(tuple(item.profile for item in targets))
    )
    sec_targets = tuple(
        target
        for target in universe.targets_for(REGISTRY["sec_edgar"].definition, cap=10_000)
        if target.profile.sec_cik
    )[:target_limit]
    registry["sec_edgar"] = SecEdgarAdapter(
        targets=tuple((target.profile.sec_cik, target.legal_name) for target in sec_targets if target.profile.sec_cik)
    )
    # The temporary database URL is supplied by the caller after its directory
    # exists.  The repository itself remains the normal durable boundary.
    engine = create_engine(settings.database_url)
    metadata.create_all(engine)
    service = MonitorService(
        settings,
        registry=registry,
        repository=MonitorRepository(engine),
        watch_profiles=tuple(item.profile for item in targets),
        catalog=MonitorCatalog(sample.watch_profiles, sample.programs, sample.facilities),
    )
    service.watch_targets = {"usaspending": targets, "sec_edgar": sec_targets}
    return service


def _source_report(service: MonitorService, source_id: str, *, limit: int) -> dict[str, object]:
    started = monotonic()
    before_observations = len(service.observations)
    before_events = len(service.events)
    before_versions = {
        record_id: observation.source_version.content_hash
        for (source_system, record_id), observation in service.source_versions.items()
        if source_system == source_id
    }
    run = service.collect(source_id, limit=limit)
    events = tuple(
        event
        for event in service.events.values()
        if event.provenance.source_system == source_id
    )
    briefs = tuple(
        brief
        for brief in signal_briefs_for_monitor(service)
        if brief.source_system == source_id
    )
    organizations, programs = service.repository.candidates() if service.repository else ((), ())
    after_versions = {
        record_id: observation.source_version.content_hash
        for (source_system, record_id), observation in service.source_versions.items()
        if source_system == source_id
    }
    overlap = set(before_versions) & set(after_versions)
    return {
        "source_id": source_id,
        "endpoint": service.registry[source_id].definition.api_base,
        "source_state": service.health[source_id].state.value,
        "request_attempted": True,
        "records_seen": run.records_seen,
        "observations_created": len(service.observations) - before_observations,
        "events_created": len(service.events) - before_events,
        "events_for_source": len(events),
        "resolved": sum(event.resolution_state.value == "RESOLVED" for event in events),
        "unresolved": sum(event.resolution_state.value == "UNRESOLVED" for event in events),
        "ambiguous": sum(event.resolution_state.value == "AMBIGUOUS" for event in events),
        "rejected": sum(event.resolution_state.value == "REJECTED" for event in events),
        "organization_candidates": sum(
            item.provenance.source_system == source_id for item in organizations
        ),
        "program_candidates": sum(
            item.provenance.source_system == source_id for item in programs
        ),
        "seller_eligible_briefs": sum(
            brief.seller_promotion_state == "RESOLVED_ELIGIBLE" for brief in briefs
        ),
        "current_briefs": sum(brief.freshness == "CURRENT" for brief in briefs),
        "upcoming_briefs": sum(brief.event_timing == "UPCOMING" for brief in briefs),
        "data_modes": tuple(sorted({event.provenance.data_mode.value for event in events})),
        "overlapping_source_identities": len(overlap),
        "unchanged_overlapping_hashes": sum(
            before_versions[record_id] == after_versions[record_id]
            for record_id in overlap
        ),
        "failures": run.failures,
        "elapsed_ms": round((monotonic() - started) * 1000),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run bounded governed Monitor live validation.")
    parser.add_argument("--source", action="append", dest="sources", required=True)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--target-limit", type=int, default=1)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args(argv)
    source_ids = tuple(args.sources)
    unknown = set(source_ids) - set(REGISTRY)
    if unknown or args.limit < 1 or args.target_limit < 1 or args.repeat < 1:
        parser.error("sources must be registered and limits must be positive")

    with TemporaryDirectory(prefix="btx-monitor-live-validation-") as directory:
        database_url = f"sqlite:///{directory}/monitor.db"
        service = _service(
            database_url=database_url, target_limit=args.target_limit
        )
        try:
            report = tuple(
                _source_report(service, source_id, limit=args.limit)
                for _ in range(args.repeat)
                for source_id in source_ids
            )
        finally:
            if service.repository:
                service.repository.engine.dispose()
    print(json.dumps(report, sort_keys=True, default=str))
    return 1 if any(item["failures"] for item in report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
