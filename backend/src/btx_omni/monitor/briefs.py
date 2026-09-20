"""Seller-facing Signal Briefs assembled only from governed Monitor records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from time import monotonic
from typing import TYPE_CHECKING

from btx_omni.ai.contracts import (
    BusinessBriefingRequest,
    ExplanationType,
    GroundedSynthesisRequest,
    LanguageProvider,
    LanguageProviderError,
    ProviderStatus,
    PublicEvidenceRecord,
)
from btx_omni.modules.intelligence.governed_explanation_adapters import (
    persisted_seller_explanation,
    technical_opportunity_subject_key,
)
from btx_omni.modules.scoring.public_inputs import (
    public_risk_assessment,
    public_signal_assessment,
)
from btx_omni.monitor.contracts import IntelligenceEvent, SourceObservation
from btx_omni.monitor.ontology import ResolutionState, SellerRelevanceState
from btx_omni.monitor.targeting import TargetReason

if TYPE_CHECKING:
    from btx_omni.monitor.repository import MonitorRepository
    from btx_omni.monitor.service import MonitorService

EVENT_LABELS = {
    "CONTRACT_AWARD": "Contract award reported",
    "CONTRACT_MODIFICATION": "Contract change reported",
    "SOLICITATION": "New solicitation published",
    "FACILITY_EXPANSION": "Facility expansion reported",
    "CAPACITY_EXPANSION": "Capacity expansion reported",
    "NEW_FACILITY": "New facility reported",
    "REGULATORY_APPROVAL": "Regulatory decision reported",
    "REGULATORY_CHANGE": "Regulatory change reported",
    "GOVERNMENT_FUNDING": "Government funding reported",
    "PROGRAM_LAUNCH": "Program update reported",
}


def _json_default(value: object) -> object:
    """Encode persisted scalar types without weakening evidence validation."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(type(value).__name__)


@dataclass(frozen=True)
class SignalBrief:
    id: str
    headline: str
    what_happened: str
    why_it_may_matter: str
    canonical_account_ids: tuple[str, ...]
    canonical_program_id: str | None
    markets: tuple[str, ...]
    publication_timestamp: datetime | None
    collection_timestamp: datetime
    freshness: str
    evidence_ids: tuple[str, ...]
    source_url: str | None
    source_system: str
    data_mode: str
    resolution_state: str
    seller_promotion_state: str
    what_to_watch: str
    recommended_action: str | None
    missing_fields: tuple[str, ...]
    seller_summary: str
    language_provider: str | None = None
    summary_mode: str = "DETERMINISTIC"
    event_timing: str = "UNKNOWN"
    relevant_event_timestamp: datetime | None = None
    watchlist_eligible: bool = False
    priority_reasons: tuple[TargetReason, ...] = ()
    canonical_facility_id: str | None = None
    technical_opportunity: dict | None = None
    signal_confidence: dict | None = None
    risk_severity: dict | None = None
    event_type: str | None = None
    analysis_status: str = "PENDING_ANALYSIS"
    commercial_relevance_state: str = "UNASSESSED"
    priority_eligible: bool = True
    action_rationale: str | None = None
    material_uncertainties: tuple[str, ...] = ()
    references: tuple[dict, ...] = ()
    evidence_package: dict | None = None
    input_revision: str | None = None
    generation_status: str = "NOT_GENERATED"
    assessment_id: str | None = None
    assessment_version: int | None = None
    geographic_scope: str = "ACCOUNT"
    context_id: str | None = None
    seed_context: dict | None = None


@dataclass(frozen=True)
class BriefSynthesisOutcome:
    brief: SignalBrief
    provider_status: ProviderStatus


@dataclass(frozen=True)
class BriefSynthesisBatch:
    attempted: int
    reused: int
    deferred: int
    assisted: int
    statuses: tuple[ProviderStatus, ...]
    capped: bool


@dataclass(frozen=True)
class BriefRetryPolicy:
    auth_failed_seconds: int = 3600
    timeout_seconds: int = 300
    quota_seconds: int = 21600
    unavailable_seconds: int = 900

    def cooldown(self, status: ProviderStatus) -> timedelta | None:
        seconds = {
            ProviderStatus.AUTH_FAILED: self.auth_failed_seconds,
            ProviderStatus.TIMEOUT: self.timeout_seconds,
            ProviderStatus.QUOTA: self.quota_seconds,
            ProviderStatus.UNAVAILABLE: self.unavailable_seconds,
        }.get(status)
        return timedelta(seconds=max(0, seconds)) if seconds is not None else None


def publication_freshness(
    published_at: datetime | None,
    *,
    collected_at: datetime,
    threshold_hours: int,
    now: datetime | None = None,
) -> str:
    from btx_omni.core.clock import as_of_datetime
    clock = as_of_datetime(now)
    if published_at is None:
        return "PUBLICATION_DATE_UNAVAILABLE"
    if published_at > clock:
        return "FUTURE_PUBLICATION_DATE"
    threshold = timedelta(hours=threshold_hours)
    return (
        "CURRENT"
        if clock - published_at <= threshold and collected_at <= clock
        else "STALE"
    )


def signal_brief(
    event: IntelligenceEvent,
    observation: SourceObservation | None,
    *,
    freshness_hours: int,
    now: datetime | None = None,
    target_reasons: tuple[TargetReason, ...] = (),
) -> SignalBrief:
    from btx_omni.core.clock import as_of_datetime
    clock = as_of_datetime(now)
    subjects = tuple(
        item.canonical_account_id
        for item in event.subject_entities
        if item.canonical_account_id
    )
    collected = observation.observed_at if observation else event.provenance.observed_at
    published = (
        observation.source_published_at if observation else event.source_published_at
    )
    eligible = (
        event.resolution_state is ResolutionState.RESOLVED
        and event.seller_relevance_state is SellerRelevanceState.RESOLVED_ELIGIBLE
    )
    from btx_omni.modules.scoring.public_rules import freshness_window_hours
    freshness = publication_freshness(
        published, collected_at=collected, threshold_hours=freshness_window_hours(event.event_type.value), now=clock
    )
    event_timing = (
        "UNKNOWN"
        if event.event_date is None
        else "UPCOMING"
        if event.event_date > clock
        else "OBSERVED"
    )
    seller_state = event.seller_relevance_state.value
    if eligible and freshness != "CURRENT":
        seller_state = f"WITHHELD_{freshness}"
    title = next(
        (claim.value for claim in event.claims if claim.predicate == "source_title"),
        None,
    )
    missing: list[str] = list(event.provenance.missing_fields)
    if not subjects:
        missing.append("canonical Customer resolution")
    if published is None:
        missing.append("publication date")
    if not title:
        missing.append("source summary")
    headline = EVENT_LABELS.get(event.event_type.value, "Public update reported")
    deterministic_summary = f"{headline}. {title}" if title else headline
    seed = json.loads(observation.structured_payload) if observation and observation.structured_payload and event.provenance.source_system in {'curated_monitor_style', 'fictional_rubric_fixture'} else None
    return SignalBrief(
        id=event.id,
        context_id=None,
        headline=headline,
        what_happened=title
        or "The source record is available, but a seller-readable source summary is unavailable.",
        why_it_may_matter=(
            "This governed public update is linked to a canonical Customer or Prospect in the watch universe."
            if subjects
            else "The organization is not yet resolved to a canonical Customer or Prospect; no relationship is implied."
        ),
        canonical_account_ids=subjects,
        canonical_program_id=event.program.canonical_program_id,
        markets=event.markets,
        publication_timestamp=published,
        collection_timestamp=collected,
        freshness=freshness,
        evidence_ids=tuple(item.evidence_id for item in event.evidence),
        source_url=(
            observation.raw_evidence.locator
            if observation
            else event.provenance.source_url
        ),
        source_system=event.provenance.source_system,
        data_mode=event.provenance.data_mode.value,
        resolution_state=event.resolution_state.value,
        seller_promotion_state=seller_state,
        what_to_watch=(
            "Review the cited source for material changes and confirm seller relevance."
            if eligible and freshness == "CURRENT"
            else "Resolve identity and evidence before seller use."
        ),
        recommended_action=(
            "Review the cited evidence and decide whether governed follow-up is warranted."
            if eligible and freshness == "CURRENT"
            else None
        ),
        missing_fields=tuple(dict.fromkeys(missing)),
        seller_summary=deterministic_summary,
        event_timing=event_timing,
        relevant_event_timestamp=event.event_date,
        watchlist_eligible=bool(target_reasons),
        priority_reasons=target_reasons,
        canonical_facility_id=event.canonical_facility_id,
        signal_confidence=public_signal_assessment(
            event, observation, now=clock, freshness_hours=freshness_hours
        ),
        risk_severity=public_risk_assessment(event, observation, now=clock),
        event_type=event.event_type.value,
        geographic_scope="FACILITY" if event.canonical_facility_id else "ACCOUNT",
        seed_context=seed,
    )


def synthesize_signal_brief(
    brief: SignalBrief, provider: LanguageProvider
) -> SignalBrief:
    """Optionally improve prose while preserving the governed brief verbatim.

    No collection, resolution, freshness, promotion, or evidence decision depends
    on this function. Provider failure returns the deterministic brief unchanged.
    """
    return synthesize_signal_brief_with_status(brief, provider).brief


def synthesize_signal_brief_with_status(
    brief: SignalBrief, provider: LanguageProvider
) -> BriefSynthesisOutcome:
    if not is_synthesis_eligible(brief):
        return BriefSynthesisOutcome(brief, ProviderStatus.UNAVAILABLE)
    if not provider.configured:
        return BriefSynthesisOutcome(brief, ProviderStatus.NOT_CONFIGURED)
    structured = getattr(provider, "synthesize_business_brief", None)
    if callable(structured) and brief.evidence_package:
        package = brief.evidence_package
        public = tuple(
            PublicEvidenceRecord(
                str(item["evidence_id"]),
                str(item["title"]),
                str(item["extract"]),
                item.get("source_url"),
                json.dumps(
                    {
                        "publication_date": item.get("publication_date"),
                        "retrieved_at": item.get("retrieved_at"),
                        "extraction_complete": item.get("extraction_complete"),
                    },
                    default=_json_default,
                    sort_keys=True,
                ),
            )
            for item in package.get("public_evidence", ())
        )
        try:
            result = structured(
                BusinessBriefingRequest(
                    event_id=brief.id,
                    evidence_package=package,
                    evidence=public,
                    allowed_evidence_ids=tuple(item.evidence_id for item in public),
                )
            )
        except LanguageProviderError as error:
            return BriefSynthesisOutcome(brief, error.status)
        except (RuntimeError, ValueError, TypeError, json.JSONDecodeError):
            return BriefSynthesisOutcome(brief, ProviderStatus.UNAVAILABLE)
        if any(
            item not in {e.evidence_id for e in public} for item in result.evidence_ids
        ):
            return BriefSynthesisOutcome(brief, ProviderStatus.UNAVAILABLE)
        return BriefSynthesisOutcome(
            replace(
                brief,
                headline=result.headline,
                what_happened=result.what_changed,
                why_it_may_matter=result.why_it_matters,
                recommended_action=result.recommended_action
                if brief.recommended_action is not None
                else None,
                action_rationale=result.action_rationale,
                material_uncertainties=result.material_uncertainties,
                evidence_ids=result.evidence_ids or brief.evidence_ids,
                seller_summary=result.why_it_matters,
                language_provider=result.provider,
                summary_mode="GEMINI_ASSISTED",
                generation_status="GEMINI_ASSISTED",
            ),
            ProviderStatus.AVAILABLE,
        )
    technical = brief.technical_opportunity or {}
    matched = tuple(
        f"{item.get('candidate_name')} → {item.get('component_name') or item.get('status')}"
        for item in technical.get("matches", ())[:6]
    )
    investigated = (
        f"\nInvestigated public context: {technical.get('event_summary') or 'No additional event summary.'}"
        f"\nControlled component review: {'; '.join(matched) if matched else 'No controlled BTX component match.'}"
        f"\nResearch uncertainties: {'; '.join(technical.get('uncertainties', ())[:6]) or 'None recorded.'}"
        if technical
        else "\nInvestigated public context: no current persisted technical investigation is available."
    )
    governed = (
        f"Headline: {brief.headline}\nWhat happened: {brief.what_happened}\n"
        f"Why it may matter: {brief.why_it_may_matter}\nWhat to watch: {brief.what_to_watch}\n"
        f"Recommended action: {brief.recommended_action or 'Unavailable'}\n"
        f"Freshness: {brief.freshness}\nData mode: {brief.data_mode}{investigated}"
    )
    try:
        result = provider.synthesize(
            GroundedSynthesisRequest(
                question="Summarize this governed public signal for a seller.",
                governed_answer=governed,
                evidence_ids=brief.evidence_ids,
                missingness=brief.missing_fields,
            )
        )
    except LanguageProviderError as error:
        return BriefSynthesisOutcome(brief, error.status)
    except (RuntimeError, ValueError):
        return BriefSynthesisOutcome(brief, ProviderStatus.UNAVAILABLE)
    if result.evidence_ids != brief.evidence_ids:
        return BriefSynthesisOutcome(brief, ProviderStatus.UNAVAILABLE)
    return BriefSynthesisOutcome(
        replace(
            brief,
            seller_summary=result.content,
            language_provider=result.provider,
            summary_mode="GEMINI_ASSISTED",
        ),
        ProviderStatus.AVAILABLE,
    )


def is_synthesis_eligible(brief: SignalBrief) -> bool:
    analysis_ready = brief.analysis_status == "READY" or (
        brief.evidence_package is None and brief.freshness == "CURRENT"
    )
    return (
        brief.seller_promotion_state
        in {
            SellerRelevanceState.RESOLVED_ELIGIBLE.value,
            SellerRelevanceState.RESOLVED_NEEDS_REVIEW.value,
            "WITHHELD_STALE",
        }
        and brief.resolution_state == ResolutionState.RESOLVED.value
        and brief.publication_timestamp is not None
        and analysis_ready
        and brief.commercial_relevance_state != "INCOMPLETE"
    )


def governed_content_hash(brief: SignalBrief) -> str:
    """Hash every governed input that can affect safe displayed synthesis."""
    governed = asdict(brief)
    if brief.evidence_package:
        # Generated language is an output, never an input to its own cache key.
        # The evidence package carries the exact public passages, deterministic
        # decisions, commercial records, identity scope, and their revisions.
        for field_name in (
            "headline",
            "what_happened",
            "why_it_may_matter",
            "recommended_action",
            "action_rationale",
            "material_uncertainties",
            "evidence_ids",
            "references",
            "what_to_watch",
        ):
            governed.pop(field_name, None)
    governed.pop("seller_summary", None)
    governed.pop("language_provider", None)
    governed.pop("summary_mode", None)
    governed.pop("generation_status", None)
    governed.pop("assessment_id", None)
    governed.pop("assessment_version", None)
    # Collection time is operational provenance, not an input to seller prose.
    # A source record with unchanged governed content must reuse its synthesis
    # when it is observed again on a subsequent Monitor run.
    governed.pop("collection_timestamp", None)

    payload = json.dumps(
        governed, default=_json_default, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def brief_cache_id(brief: SignalBrief) -> str:
    if not brief.evidence_package:
        return brief.id
    account_id = (
        brief.canonical_account_ids[0]
        if len(brief.canonical_account_ids) == 1
        else "UNRESOLVED"
    )
    return (
        "assessment:" + hashlib.sha256(f"{brief.id}|{account_id}".encode()).hexdigest()
    )


def apply_cached_synthesis(brief: SignalBrief, cached: dict | None) -> SignalBrief:
    """Apply only a successful exact-hash cache entry to an eligible brief."""
    if (
        not cached
        or not is_synthesis_eligible(brief)
        or cached.get("governed_content_hash") != governed_content_hash(brief)
        or cached.get("status") != ProviderStatus.AVAILABLE.value
        or not (cached.get("summary") or cached.get("projection"))
    ):
        return brief
    projection = cached.get("projection") or {}
    if isinstance(projection, str):
        try:
            projection = json.loads(projection)
        except json.JSONDecodeError:
            projection = {}
    allowed = {field.name for field in fields(SignalBrief)}
    safe = {
        key: value
        for key, value in projection.items()
        if key in allowed
        and key
        not in {
            "id",
            "canonical_account_ids",
            "canonical_program_id",
            "evidence_package",
            "signal_confidence",
            "risk_severity",
            "priority_eligible",
            "commercial_relevance_state",
            "generation_status",
        }
    }
    for key in ("material_uncertainties", "evidence_ids"):
        if key in safe:
            safe[key] = tuple(safe[key])
    return replace(
        brief,
        **safe,
        seller_summary=str(
            cached.get("summary")
            or safe.get("why_it_may_matter")
            or brief.seller_summary
        ),
        language_provider=str(cached.get("provider") or "gemini"),
        summary_mode="GEMINI_ASSISTED",
        generation_status="GEMINI_ASSISTED",
    )


def persisted_brief_projection(brief: SignalBrief, *, include_language: bool) -> dict:
    projection = {
        "headline": brief.headline,
        "what_happened": brief.what_happened,
        "why_it_may_matter": brief.why_it_may_matter,
        "recommended_action": brief.recommended_action,
        "action_rationale": brief.action_rationale,
        "material_uncertainties": brief.material_uncertainties,
        "evidence_ids": brief.evidence_ids,
        "analysis_status": brief.analysis_status,
        "generation_status": brief.generation_status,
        "evidence_package": brief.evidence_package,
    }
    return (
        projection
        if include_language
        else {**projection, "generation_status": "DETERMINISTIC_READY"}
    )


def signal_briefs_for_monitor(
    monitor: MonitorService,
    *,
    now: datetime | None = None,
    environment=None,
    projection_limit: int | None = None,
    account_ids: frozenset[str] | None = None,
) -> tuple[SignalBrief, ...]:
    """Project governed briefs without invoking any language provider.

    Seller read models may request a bounded, relevance-first window. The
    operational worker deliberately leaves ``projection_limit`` unset so it
    continues to assess every retained event. Account-scoped consumers filter
    before the window is applied, preventing unrelated recent events from
    displacing the selected account's assessment.
    """
    from btx_omni.core.clock import as_of_datetime
    from btx_omni.monitor.service import current_event_contexts
    now = now or as_of_datetime(getattr(getattr(monitor, 'settings', None), 'demo_as_of_date', None))

    repository = getattr(monitor, "repository", None)
    selected_assessments: tuple[dict, ...] = ()
    selected_by_context: dict[tuple[str, str | None], dict] = {}
    assessment_rank: dict[tuple[str, str | None], int] = {}
    persisted_display_mode = False
    if repository and projection_limit is not None:
        display_reader = getattr(repository, "current_display_assessments", None)
        if callable(display_reader):
            persisted_display_mode = bool(
                repository.current_intelligence_assessments(limit=1)
            )
            selected_assessments = display_reader(
                limit=projection_limit, account_ids=account_ids
            )
        else:
            # Compatibility for non-durable test adapters; production repositories
            # own selection in ``current_display_assessments``.
            selected_assessments = repository.current_intelligence_assessments(
                limit=max(1000, projection_limit * 20)
            )
            if account_ids:
                selected_assessments = tuple(
                    item
                    for item in selected_assessments
                    if item.get("account_id") in account_ids
                )
            selected_assessments = selected_assessments[:projection_limit]
            persisted_display_mode = bool(selected_assessments)
        selected_by_context = {
            (item["event_id"], item.get("account_id")): item
            for item in selected_assessments
        }
        assessment_rank = {
            key: index for index, key in enumerate(selected_by_context)
        }
    selected_event_ids = {item["event_id"] for item in selected_assessments}
    candidates: list[SignalBrief] = []
    for event, observation in current_event_contexts(monitor):
        if persisted_display_mode and event.id not in selected_event_ids:
            continue
        source_id = event.provenance.source_system
        subject_ids = {
            item.canonical_account_id
            for item in event.subject_entities
            if item.canonical_account_id
        }
        reasons = tuple(
            reason
            for target in monitor.watch_targets.get(source_id, ())
            if target.canonical_account_id in subject_ids
            for reason in target.reasons
        )
        base = signal_brief(
            event,
            observation,
            freshness_hours=monitor.freshness_threshold_hours(source_id),
            now=now,
            target_reasons=reasons,
        )
        contextual = (
            tuple(
                replace(base, canonical_account_ids=(account_id,))
                for account_id in base.canonical_account_ids
            )
            if environment is not None and base.canonical_account_ids
            else (base,)
        )
        candidates.extend(
            brief
            for brief in contextual
            if (
                not account_ids
                or bool(account_ids.intersection(brief.canonical_account_ids))
            )
            and (
                projection_limit is None
                or not persisted_display_mode
                or (
                    brief.id,
                    brief.canonical_account_ids[0]
                    if len(brief.canonical_account_ids) == 1
                    else None,
                )
                in selected_by_context
            )
        )

    def seller_window_key(brief: SignalBrief) -> tuple:
        account_id = (
            brief.canonical_account_ids[0]
            if len(brief.canonical_account_ids) == 1
            else None
        )
        assessment = selected_by_context.get((brief.id, account_id))
        projection = assessment.get("projection", {}) if assessment else {}
        relevance_order = {
            "ESTABLISHED_COMMERCIAL_RELEVANCE": 0,
            "ESTABLISHED_ACCOUNT_REVIEW": 1,
            "PLAUSIBLE_FIT_REQUIRES_VALIDATION": 2,
            "INFORMATIONAL": 3,
            "INCOMPLETE": 4,
        }
        return (
            assessment_rank.get((brief.id, account_id), 10**9),
            0 if assessment else 1,
            0 if projection.get("priority_eligible") else 1,
            relevance_order.get(projection.get("commercial_relevance_state"), 5),
            -assessment["created_at"].timestamp() if assessment else 0,
            {
                "RESOLVED_ELIGIBLE": 0,
                "RESOLVED_NEEDS_REVIEW": 1,
                "AMBIGUOUS": 2,
                "UNRESOLVED": 3,
                "REJECTED": 4,
            }.get(brief.seller_promotion_state, 5),
            0 if brief.resolution_state == "RESOLVED" else 1,
            -brief.publication_timestamp.timestamp()
            if brief.publication_timestamp
            else float("inf"),
            brief.id,
            brief.canonical_account_ids,
        )

    candidates.sort(key=seller_window_key)
    if projection_limit is not None:
        if projection_limit < 1:
            return ()
        candidates = candidates[:projection_limit]

    projected: list[SignalBrief] = []
    for brief in candidates:
        technical = None
        if repository:
            # Seller reads consume the exact worker-owned durable projection. They never
            # reconstruct a hash by guessing the configured provider model.
            technical_account_id = (
                brief.canonical_account_ids[0]
                if len(brief.canonical_account_ids) == 1
                else None
            )
            cached = repository.technical_decomposition_for_event(
                brief.id, technical_account_id
            )
            if cached and cached.get("projection"):
                technical = json.loads(cached["projection"])
                technical["governed_explanation"] = persisted_seller_explanation(
                    monitor.repository,
                    subject_key=technical_opportunity_subject_key(brief.id),
                    explanation_type=ExplanationType.TECHNICAL_OPPORTUNITY_FIT,
                )
        brief = replace(brief, technical_opportunity=technical) if technical else brief
        if environment is not None and repository:
            from btx_omni.monitor.business_briefings import (
                apply_evidence_package,
                apply_persisted_assessment,
                assemble_evidence_package,
            )
            account_id = (
                brief.canonical_account_ids[0]
                if len(brief.canonical_account_ids) == 1
                else None
            )
            persisted = selected_by_context.get((brief.id, account_id))
            if persisted is not None:
                brief = apply_persisted_assessment(brief, persisted)
            elif not persisted_display_mode:
                brief = apply_evidence_package(
                    brief,
                    assemble_evidence_package(
                        brief,
                        environment=environment,
                        repository=repository,
                        now=now,
                    ),
                )
                brief = apply_persisted_assessment(
                    brief,
                    repository.intelligence_assessment(
                        brief.id,
                        account_id=account_id,
                        input_revision=brief.input_revision,
                    ),
                )
        projected.append(brief)
    return tuple(projected)


def process_signal_brief_synthesis(
    briefs: tuple[SignalBrief, ...],
    *,
    provider: LanguageProvider,
    repository: MonitorRepository,
    cap: int,
    retry_policy: BriefRetryPolicy | None = None,
    deadline_monotonic: float | None = None,
    minimum_attempt_seconds: float = 0,
    now: datetime | None = None,
) -> BriefSynthesisBatch:
    """Attempt a capped set of new or retry-eligible hashes outside read endpoints."""
    clock = now or datetime.now(UTC)
    policy = retry_policy or BriefRetryPolicy()
    attempted = reused = deferred = assisted = 0
    statuses: list[ProviderStatus] = []
    eligible = tuple(
        sorted(
            filter(is_synthesis_eligible, briefs),
            key=lambda item: (
                not item.priority_eligible,
                -float((item.signal_confidence or {}).get("coverage", 0) or 0),
                item.id,
            ),
        )
    )
    capped = False
    for brief in eligible:
        content_hash = governed_content_hash(brief)
        cache_id = brief_cache_id(brief)
        cached = repository.brief_synthesis(cache_id, content_hash)
        cached_status = (
            ProviderStatus(cached["status"])
            if cached and cached.get("status") in ProviderStatus._value2member_map_
            else None
        )
        if cached_status is ProviderStatus.AVAILABLE:
            reused += 1
            continue
        if not provider.configured:
            if cached_status is not ProviderStatus.NOT_CONFIGURED:
                repository.save_brief_synthesis(
                    brief_id=cache_id,
                    governed_content_hash=content_hash,
                    summary=None,
                    provider=None,
                    model=None,
                    status=ProviderStatus.NOT_CONFIGURED.value,
                    attempt_count=int(cached.get("attempt_count", 0)) if cached else 0,
                    next_retry_at=None,
                    synthesized_at=clock,
                    projection=persisted_brief_projection(
                        brief, include_language=False
                    ),
                    source_revision=(brief.evidence_package or {}).get(
                        "source_revision"
                    ),
                    input_revision=brief.input_revision,
                )
            deferred += 1
            continue
        next_retry_at = cached.get("next_retry_at") if cached else None
        if next_retry_at and next_retry_at.tzinfo is None:
            next_retry_at = next_retry_at.replace(tzinfo=UTC)
        if cached_status not in {None, ProviderStatus.NOT_CONFIGURED} and (
            next_retry_at is None or clock < next_retry_at
        ):
            deferred += 1
            continue
        if attempted >= max(0, cap):
            capped = True
            break
        if (
            deadline_monotonic is not None
            and deadline_monotonic - monotonic() < minimum_attempt_seconds
        ):
            capped = True
            break
        outcome = synthesize_signal_brief_with_status(brief, provider)
        attempted += 1
        statuses.append(outcome.provider_status)
        assisted += int(outcome.brief.summary_mode == "GEMINI_ASSISTED")
        cooldown = policy.cooldown(outcome.provider_status)
        repository.save_brief_synthesis(
            brief_id=cache_id,
            governed_content_hash=content_hash,
            summary=(
                outcome.brief.seller_summary
                if outcome.provider_status is ProviderStatus.AVAILABLE
                else None
            ),
            provider=outcome.brief.language_provider,
            model=getattr(
                getattr(provider, "config", None),
                "model",
                getattr(provider, "model", None),
            ),
            status=outcome.provider_status.value,
            attempt_count=(int(cached.get("attempt_count", 0)) if cached else 0) + 1,
            next_retry_at=clock + cooldown if cooldown else None,
            synthesized_at=clock,
            projection=(
                persisted_brief_projection(outcome.brief, include_language=True)
                if outcome.provider_status is ProviderStatus.AVAILABLE
                else persisted_brief_projection(brief, include_language=False)
            ),
            source_revision=(outcome.brief.evidence_package or {}).get(
                "source_revision"
            ),
            input_revision=outcome.brief.input_revision,
        )
    return BriefSynthesisBatch(
        attempted, reused, deferred, assisted, tuple(statuses), capped
    )
