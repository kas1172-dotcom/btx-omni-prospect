"""Bounded operational Monitor worker for an external scheduler."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import nullcontext
from dataclasses import asdict
from time import monotonic

from btx_omni.ai.config import AiConfig
from btx_omni.ai.contracts import PublicEvidenceRecord, TechnicalDecompositionRequest
from btx_omni.ai.registry import get_ai_provider
from btx_omni.api.runtime import PocRuntime
from btx_omni.core.config import Settings
from btx_omni.modules.federal_procurement import procurement_projection
from btx_omni.modules.intelligence.governed_explanation_adapters import (
    process_customer_attractiveness_explanation,
    process_federal_opportunity_explanation,
    process_relationship_path_explanation,
    process_technical_opportunity_explanation,
)
from btx_omni.modules.intelligence.technical_fit import seller_projection
from btx_omni.modules.relationships.presentation import (
    SellerRelationshipPresentationService,
)
from btx_omni.modules.relationships.service import RelationshipIntelligenceService
from btx_omni.modules.scoring.account_attractiveness import (
    AccountAttractivenessInputs,
    seller_attractiveness_projection,
)
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
        for index, source_id in enumerate(configured):
            remaining = deadline - monotonic()
            if remaining < settings.monitor_source_min_start_seconds:
                deadline_exhausted = True
                break
            # Reserve a fair minimum start window for each remaining provider.
            # A slow upstream must be observable, but cannot starve every
            # subsequent source by consuming the entire global deadline.
            remaining_sources = len(configured) - index
            source_deadline = min(
                deadline,
                monotonic() + max(
                    settings.monitor_source_min_start_seconds,
                    remaining / remaining_sources,
                ),
            )
            run = runtime.monitor.collect(
                source_id,
                limit=limit or settings.monitor_source_record_limit,
                deadline_monotonic=source_deadline,
            )
            runs.append(run)
            if monotonic() >= deadline:
                deadline_exhausted = True
                break
        synthesis = None
        technical: list[dict] = []
        explanations: list[dict] = []
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
            # Technical calls are bounded worker work. Seller reads only consume cached/projection data.
            provider = get_ai_provider(AiConfig.from_settings(settings))
            for brief in signal_briefs_for_monitor(runtime.monitor)[
                : settings.monitor_technical_decomposition_cap
            ]:
                account = next(
                    (
                        item
                        for item in runtime.sample.accounts
                        if item.id in brief.canonical_account_ids
                    ),
                    None,
                )
                program = next(
                    (
                        item
                        for item in runtime.sample.programs
                        if item.id == brief.canonical_program_id
                    ),
                    None,
                )
                request = TechnicalDecompositionRequest(
                    event_id=brief.id,
                    event_type=brief.headline,
                    canonical_customer_name=account.legal_name if account else None,
                    canonical_program_name=program.name if program else None,
                    market=brief.markets[0] if brief.markets else None,
                    evidence=(
                        PublicEvidenceRecord(
                            brief.evidence_ids[0] if brief.evidence_ids else brief.id,
                            brief.what_happened,
                            brief.what_happened,
                            brief.source_url,
                            brief.source_system,
                        ),
                    ),
                )
                cache_key = runtime.technical_decomposition.cache_key(
                    request,
                    model=runtime.technical_decomposition.provider_model(provider),
                )
                outcome = runtime.technical_decomposition.process(
                    request,
                    provider,
                    cached=repository.technical_decomposition(brief.id, cache_key),
                    now=runtime.observed_at(),
                )
                projection = outcome.projection
                if outcome.should_persist:
                    repository.save_technical_decomposition(
                        event_id=brief.id,
                        governed_content_hash=projection.governed_content_hash,
                        projection=seller_projection(projection),
                        provider=projection.language_provider,
                        model=projection.language_model,
                        status=projection.provider_status.value,
                        processed_at=runtime.observed_at(),
                        attempt_count=outcome.attempt_count,
                        next_retry_at=outcome.next_retry_at,
                    )
                if projection.decomposition:
                    technical_explanation = process_technical_opportunity_explanation(
                        projection=seller_projection(projection),
                        event_id=brief.id,
                        provider=provider,
                        repository=repository,
                        now=runtime.observed_at(),
                    )
                    explanations.append(
                        {
                            "type": "TECHNICAL_OPPORTUNITY_FIT",
                            "subject": brief.id,
                            "provider_status": technical_explanation.provider_status.value,
                        }
                    )
                technical.append(
                    {
                        "event_id": brief.id,
                        "provider_status": projection.provider_status.value,
                        "matches": len(projection.matches),
                    }
                )
            # Customer/Federal explanation calls share the bounded worker and durable cache.
            explanation_provider = get_ai_provider(AiConfig.from_settings(settings))
            cap = settings.monitor_technical_decomposition_cap
            for account in runtime.sample.accounts[:cap]:
                scenario = runtime.sample.priority_scenarios.get(
                    account.id
                ) or runtime.sample.rich_scenarios.get(account.id)
                attractiveness = seller_attractiveness_projection(
                    AccountAttractivenessInputs(
                        runtime.sample.scoring_inputs.get(account.id, {})
                    ),
                    calculated_at=runtime.observed_at(),
                    excluded=bool(scenario and scenario.exclusion_reason),
                    exclusion_reason=scenario.exclusion_reason if scenario else None,
                )
                outcome = process_customer_attractiveness_explanation(
                    account_id=account.id,
                    account_name=account.legal_name,
                    projection=attractiveness,
                    provider=explanation_provider,
                    repository=repository,
                    now=runtime.observed_at(),
                )
                explanations.append(
                    {
                        "type": "CUSTOMER_ATTRACTIVENESS",
                        "subject": account.id,
                        "provider_status": outcome.provider_status.value,
                    }
                )
            relationship_service = SellerRelationshipPresentationService()
            for account in runtime.sample.accounts[:cap]:
                relationships = RelationshipIntelligenceService(
                    runtime.sample
                ).account_relationships(account.id)
                paths = relationship_service.present(relationships)[
                    "seller_projection"
                ]["validated"][:1]
                for path in paths:
                    outcome = process_relationship_path_explanation(
                        path=path,
                        customer_id=account.id,
                        provider=explanation_provider,
                        repository=repository,
                        now=runtime.observed_at(),
                    )
                    explanations.append(
                        {
                            "type": "RELATIONSHIP_PATH",
                            "subject": path["path_id"],
                            "provider_status": outcome.provider_status.value,
                        }
                    )
            for opportunity in procurement_projection(runtime)["active"][
                "opportunities"
            ][:cap]:
                outcome = process_federal_opportunity_explanation(
                    opportunity=opportunity,
                    provider=explanation_provider,
                    repository=repository,
                    now=runtime.observed_at(),
                )
                explanations.append(
                    {
                        "type": "FEDERAL_OPPORTUNITY_RELEVANCE",
                        "subject": opportunity["opportunity_id"],
                        "provider_status": outcome.provider_status.value,
                    }
                )
    failed = tuple(run.source_id for run in runs if run.failures)
    report = {
        "status": "DEADLINE_EXHAUSTED"
        if deadline_exhausted
        else "FAILED"
        if failed
        else "SUCCESS",
        "configured_sources": configured,
        "skipped_sources": skipped,
        "failed_sources": failed,
        "runs": tuple(asdict(run) for run in runs),
        "brief_synthesis": asdict(synthesis) if synthesis else None,
        "technical_decomposition": technical,
        "governed_explanations": explanations,
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
