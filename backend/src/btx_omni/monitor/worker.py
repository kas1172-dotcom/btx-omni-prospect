"""Bounded operational Monitor worker for an external scheduler."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import nullcontext
from dataclasses import asdict
from time import monotonic

from btx_omni.ai.config import AiConfig
from btx_omni.ai.registry import get_ai_provider
from btx_omni.api.runtime import PocRuntime
from btx_omni.core.config import Settings
from btx_omni.monitor.briefs import (
    BriefRetryPolicy,
    process_signal_brief_synthesis,
    signal_briefs_for_monitor,
)


def run_worker(
    settings: Settings,
    *,
    source_ids: tuple[str, ...] | None = None,
    limit: int | None = None,
) -> tuple[dict, int]:
    if (
        settings.monitor_mode.lower() != "live"
        or not settings.monitor_durable_state_enabled
    ):
        return {
            "status": "NOT_CONFIGURED",
            "detail": "Live mode and durable Monitor state are required.",
        }, 2
    runtime = PocRuntime(settings)
    repository = getattr(runtime.monitor, "repository", None)
    lock = repository.operational_lock() if repository else nullcontext(True)
    with lock as acquired:
        if not acquired:
            return {
                "status": "OVERLAP_SKIPPED",
                "detail": "Another Monitor worker owns the operational lock.",
            }, 3
        requested = (
            source_ids
            or tuple(
                item.strip()
                for item in settings.monitor_worker_sources.split(",")
                if item.strip()
            )
            or tuple(runtime.monitor.registry)
        )
        unknown = set(requested) - set(runtime.monitor.registry)
        if unknown:
            return {"status": "INVALID_SOURCE", "sources": sorted(unknown)}, 2
        configured = tuple(
            source_id
            for source_id in requested
            if runtime.monitor.registry[source_id].available(settings)[0]
        )
        skipped = tuple(
            source_id for source_id in requested if source_id not in configured
        )
        deadline = monotonic() + settings.monitor_worker_max_seconds
        runs = []
        deadline_exhausted = False
        for source_id in configured:
            remaining = deadline - monotonic()
            if remaining < settings.monitor_source_min_start_seconds:
                deadline_exhausted = True
                break
            run = runtime.monitor.collect(
                source_id,
                limit=limit or settings.monitor_source_record_limit,
                deadline_monotonic=deadline,
            )
            runs.append(run)
            if "DEADLINE_EXCEEDED" in run.failures:
                deadline_exhausted = True
                break
            if monotonic() >= deadline:
                deadline_exhausted = True
                break
        synthesis = None
        if runs and not deadline_exhausted and repository:
            synthesis = process_signal_brief_synthesis(
                signal_briefs_for_monitor(runtime.monitor),
                provider=get_ai_provider(AiConfig.from_settings(settings)),
                repository=repository,
                cap=settings.monitor_brief_synthesis_cap,
                retry_policy=BriefRetryPolicy(
                    auth_failed_seconds=settings.monitor_brief_auth_retry_seconds,
                    timeout_seconds=settings.monitor_brief_timeout_retry_seconds,
                    quota_seconds=settings.monitor_brief_quota_retry_seconds,
                    unavailable_seconds=settings.monitor_brief_unavailable_retry_seconds,
                ),
                deadline_monotonic=deadline,
                minimum_attempt_seconds=settings.ai_timeout_seconds,
            )
    failed = tuple(run.source_id for run in runs if run.failures)
    report = {
        "status": "DEADLINE_EXHAUSTED" if deadline_exhausted else "FAILED" if failed else "SUCCESS",
        "configured_sources": configured,
        "skipped_sources": skipped,
        "failed_sources": failed,
        "runs": tuple(asdict(run) for run in runs),
        "brief_synthesis": asdict(synthesis) if synthesis else None,
        "bounded": {
            "record_limit_per_source": limit or settings.monitor_source_record_limit,
            "collection_deadline_seconds": settings.monitor_worker_max_seconds,
            "minimum_start_budget_seconds": settings.monitor_source_min_start_seconds,
            "deadline_scope": "source collection is interruptible; transactional persistence completes before exit",
        },
    }
    return report, 1 if failed or not runs or deadline_exhausted else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run bounded durable BTX Monitor collection."
    )
    parser.add_argument("--source", action="append", dest="sources")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    report, code = run_worker(
        Settings(),
        source_ids=tuple(args.sources) if args.sources else None,
        limit=args.limit,
    )
    print(json.dumps(report, default=str, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
