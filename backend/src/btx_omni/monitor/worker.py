"""Bounded operational Monitor worker for an external scheduler."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import nullcontext
from dataclasses import asdict, replace
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
    seller_attractiveness_projection,
)
from btx_omni.monitor.briefs import (
    BriefRetryPolicy,
    apply_cached_synthesis,
    brief_cache_id,
    governed_content_hash,
    process_signal_brief_synthesis,
    signal_briefs_for_monitor,
)
from btx_omni.monitor.business_briefings import (
    persist_assessment,
    requires_technical_investigation,
)
from btx_omni.monitor.documents import document_evidence
from btx_omni.monitor.research import MonitorResearchCoordinator


def run_worker(
    settings: Settings,
    *,
    source_ids: tuple[str, ...] | None = None,
    limit: int | None = None,
) -> tuple[dict, int]:
    if limit is not None and (type(limit) is not int or not 1 <= limit <= 100):
        return {
            "status": "INVALID_LIMIT",
            "detail": "Choose 1–100 records per source.",
        }, 2
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
        # Public macro observations use their own canonical owner, not fabricated
        # Monitor customer events. Reuse this worker and its operational lock.
        market_refresh = (
            runtime.markets.worker_refresh(deadline_monotonic=deadline)
            if settings.market_refresh_enabled
            else {"status": "DISABLED"}
        )
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
                monotonic()
                + max(
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
        # Source deadlines are isolated. Successful sources retain their worker
        # budget and can proceed to bounded research and briefing generation.
        synthesis = None
        investigations = []
        technical: list[dict] = []
        explanations: list[dict] = []
        optional_budget_stops: list[str] = []

        def can_start_optional(stage: str) -> bool:
            nonlocal deadline_exhausted
            if deadline - monotonic() < settings.ai_timeout_seconds:
                deadline_exhausted = True
                if stage not in optional_budget_stops:
                    optional_budget_stops.append(stage)
                return False
            return True

        if runs and not deadline_exhausted and repository:
            environment = (
                runtime.environment()
                if callable(getattr(runtime, "environment", None))
                else runtime.sample
            )

            def projected_briefs():
                if callable(getattr(runtime, "environment", None)):
                    return signal_briefs_for_monitor(
                        runtime.monitor, environment=environment
                    )
                return signal_briefs_for_monitor(runtime.monitor)

            research_provider = get_ai_provider(
                AiConfig.from_settings(settings, purpose="monitor_public_research")
            )
            coordinator = MonitorResearchCoordinator(repository, research_provider)
            # Investigate only this collection cycle, not arbitrary private or
            # historical account rows. Public relevance still controls publication.
            candidates = (
                repository.research_documents(
                    tuple(run.id for run in runs),
                    limit=settings.monitor_research_cap,
                    now=runtime.observed_at(),
                    retained_days=60,
                )
                if getattr(research_provider, "configured", False)
                and settings.monitor_research_cap
                else ()
            )
            for document in candidates:
                if not can_start_optional("RESEARCH_COORDINATOR"):
                    break
                investigation = coordinator.investigate(
                    document,
                    source_revision=document["content_hash"],
                    deadline_monotonic=min(deadline, monotonic() + 90),
                )
                # A bounded coordinator may stop before it acquires a durable
                # research run (for example when its deadline is exhausted).
                # Preserve the public event identity, but do not invent a run ID
                # or attempt to read/write a journal entry that does not exist.
                investigation.setdefault("event_id", document["event_id"])
                investigations.append(investigation)
            # Technical calls are bounded worker work. Seller reads only consume cached/projection data.
            provider = get_ai_provider(AiConfig.from_settings(settings))
            technical_briefs = tuple(
                {
                    brief.id: brief
                    for brief in projected_briefs()
                    if requires_technical_investigation(brief.event_type)
                }.values()
            )[: settings.monitor_technical_decomposition_cap]
            for brief in technical_briefs:
                if not can_start_optional("TECHNICAL_DECOMPOSITION"):
                    break
                account = next(
                    (
                        item
                        for item in environment.accounts
                        if item.id in brief.canonical_account_ids
                    ),
                    None,
                )
                program = next(
                    (
                        item
                        for item in environment.programs
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
                    evidence=document_evidence(
                        repository.event_document(brief.id, include_research=True),
                        max_passages=6,
                    )
                    or (
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
                if projection.decomposition and can_start_optional(
                    "TECHNICAL_EXPLANATION"
                ):
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
            # Brief synthesis runs after technical investigation so the governed
            # content hash and seller prose include the current persisted research
            # projection. A stale pre-investigation summary cannot remain current.
            prepared_briefs = projected_briefs()
            for prepared in prepared_briefs:
                persist_assessment(
                    prepared, repository=repository, now=runtime.observed_at()
                )
            synthesis = process_signal_brief_synthesis(
                prepared_briefs,
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
            # Publication remains a deterministic server decision. Gemini may
            # select public reads and improve prose, but cannot pass these gates.
            final_briefs = []
            briefs_by_id: dict[str, list] = {}
            for deterministic in projected_briefs():
                cached = repository.brief_synthesis(
                    brief_cache_id(deterministic), governed_content_hash(deterministic)
                )
                rendered = apply_cached_synthesis(deterministic, cached)
                persisted = persist_assessment(
                    rendered,
                    repository=repository,
                    now=runtime.observed_at(),
                    provider=rendered.language_provider,
                    model=getattr(getattr(provider, "config", None), "model", None),
                )
                if persisted:
                    rendered = replace(
                        rendered,
                        assessment_id=persisted["id"],
                        assessment_version=persisted["version"],
                    )
                briefs_by_id.setdefault(rendered.id, []).append(rendered)
            for investigation in investigations:
                research_run_id = investigation.get("run_id")
                state = (
                    repository.research.get(research_run_id)
                    if research_run_id
                    else None
                )
                event_id = investigation.get("event_id") or (state or {}).get(
                    "event_reference"
                )
                contexts = sorted(
                    briefs_by_id.get(event_id, ()),
                    key=lambda item: (
                        not item.priority_eligible,
                        item.canonical_account_ids[0]
                        if item.canonical_account_ids
                        else "",
                    ),
                )
                brief = contexts[0] if contexts else None
                has_passages = any(
                    document.get("document", {}).get("passages")
                    for document in investigation.get("documents", ())
                )
                gates = {
                    "research_completed": investigation.get("status")
                    == "RESEARCH_RECORDED"
                    and has_passages,
                    "canonical_identity_resolved": bool(
                        brief
                        and brief.resolution_state == "RESOLVED"
                        and brief.canonical_account_ids
                    ),
                    "seller_relevance_eligible": bool(
                        brief
                        and brief.seller_promotion_state
                        in {
                            "RESOLVED_ELIGIBLE",
                            "RESOLVED_NEEDS_REVIEW",
                            "WITHHELD_STALE",
                        }
                    ),
                    "analysis_lifetime_eligible": bool(
                        brief and brief.analysis_status == "READY"
                    ),
                    "commercial_relevance_decided": bool(
                        brief and brief.commercial_relevance_state != "UNASSESSED"
                    ),
                    "technical_investigation_available": bool(
                        brief
                        and (
                            not requires_technical_investigation(brief.event_type)
                            or (
                                brief.technical_opportunity
                                and brief.technical_opportunity.get("provider_status")
                                == "AVAILABLE"
                            )
                        )
                    ),
                    "gemini_brief_available": bool(
                        brief and brief.summary_mode == "GEMINI_ASSISTED"
                    ),
                }
                published = all(gates.values())
                outcome = {
                    "published": published,
                    "state": "PUBLISHED_SELLER_BRIEF"
                    if published
                    else "WITHHELD_BY_CANONICAL_GATES",
                    "event_id": event_id,
                    "brief_id": brief.id if brief else None,
                    "gates": gates,
                    "assessment_contexts": [
                        {
                            "account_id": item.canonical_account_ids[0]
                            if item.canonical_account_ids
                            else None,
                            "assessment_id": item.assessment_id,
                            "assessment_version": item.assessment_version,
                            "commercial_relevance_state": item.commercial_relevance_state,
                            "priority_eligible": item.priority_eligible,
                        }
                        for item in contexts
                    ],
                    "decided_at": runtime.observed_at().isoformat(),
                }
                if (
                    research_run_id
                    and state
                    and state.get("status") == "COMPLETED"
                ):
                    repository.research.record_publication(
                        research_run_id,
                        outcome=outcome,
                        now=runtime.observed_at(),
                    )
                investigation.update(
                    {
                        "published": published,
                        "publication_state": outcome["state"],
                        "publication_gates": gates,
                    }
                )
                final_briefs.append(outcome)
            # Customer/Federal explanation calls share the bounded worker and durable cache.
            explanation_provider = get_ai_provider(AiConfig.from_settings(settings))
            cap = settings.monitor_technical_decomposition_cap
            for account in environment.accounts[:cap]:
                if not can_start_optional("CUSTOMER_EXPLANATION"):
                    break
                scenario = environment.priority_scenarios.get(
                    account.id
                ) or environment.rich_scenarios.get(account.id)
                attractiveness = seller_attractiveness_projection(
                    environment.attractiveness_inputs(account.id),
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
            for account in environment.accounts[:cap]:
                if not can_start_optional("RELATIONSHIP_EXPLANATION"):
                    break
                relationships = RelationshipIntelligenceService(
                    environment
                ).account_relationships(account.id)
                paths = relationship_service.present(relationships)[
                    "seller_projection"
                ]["validated"][:1]
                for path in paths:
                    if not can_start_optional("RELATIONSHIP_EXPLANATION"):
                        break
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
                if not can_start_optional("FEDERAL_EXPLANATION"):
                    break
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
        if failed or market_refresh["status"] == "FAILED"
        else "SUCCESS",
        "configured_sources": configured,
        "skipped_sources": skipped,
        "failed_sources": failed,
        "runs": tuple(asdict(run) for run in runs),
        "brief_synthesis": asdict(synthesis) if synthesis else None,
        "technical_decomposition": technical,
        "research_investigations": investigations,
        "seller_publication": final_briefs if "final_briefs" in locals() else [],
        "governed_explanations": explanations,
        "optional_budget_stops": optional_budget_stops,
        "market_refresh": market_refresh,
        "bounded": {
            "record_limit_per_source": limit or settings.monitor_source_record_limit,
            "collection_deadline_seconds": settings.monitor_worker_max_seconds,
            "minimum_start_budget_seconds": settings.monitor_source_min_start_seconds,
            "deadline_scope": "Source collection is interruptible; optional AI stages require a full configured provider timeout before starting. In-flight provider timeout and transactional persistence may finish after the scheduling deadline.",
        },
    }
    return report, 1 if failed or not runs or deadline_exhausted or market_refresh[
        "status"
    ] == "FAILED" else 0


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
