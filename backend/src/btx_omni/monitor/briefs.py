"""Seller-facing Signal Briefs assembled only from governed Monitor records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import TYPE_CHECKING

from btx_omni.ai.contracts import (
    ExplanationType,
    GroundedSynthesisRequest,
    LanguageProvider,
    LanguageProviderError,
    ProviderStatus,
)
from btx_omni.modules.intelligence.governed_explanation_adapters import (
    persisted_seller_explanation,
    technical_opportunity_subject_key,
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
    clock = now or datetime.now(UTC)
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
    clock = now or datetime.now(UTC)
    subjects = tuple(
        item.canonical_account_id
        for item in event.subject_entities
        if item.canonical_account_id
    )
    collected = observation.observed_at if observation else event.provenance.observed_at
    published = observation.source_published_at if observation else event.source_published_at
    eligible = (
        event.resolution_state is ResolutionState.RESOLVED
        and event.seller_relevance_state is SellerRelevanceState.RESOLVED_ELIGIBLE
    )
    freshness = publication_freshness(
        published, collected_at=collected, threshold_hours=freshness_hours, now=clock
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
    return SignalBrief(
        id=event.id,
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
    governed = (
        f"Headline: {brief.headline}\nWhat happened: {brief.what_happened}\n"
        f"Why it may matter: {brief.why_it_may_matter}\nWhat to watch: {brief.what_to_watch}\n"
        f"Recommended action: {brief.recommended_action or 'Unavailable'}\n"
        f"Freshness: {brief.freshness}\nData mode: {brief.data_mode}"
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
    return (
        brief.seller_promotion_state == SellerRelevanceState.RESOLVED_ELIGIBLE.value
        and brief.freshness == "CURRENT"
        and brief.resolution_state == ResolutionState.RESOLVED.value
        and brief.publication_timestamp is not None
    )


def governed_content_hash(brief: SignalBrief) -> str:
    """Hash every governed input that can affect safe displayed synthesis."""
    governed = asdict(brief)
    governed.pop("seller_summary", None)
    governed.pop("language_provider", None)
    governed.pop("summary_mode", None)
    # Collection time is operational provenance, not an input to seller prose.
    # A source record with unchanged governed content must reuse its synthesis
    # when it is observed again on a subsequent Monitor run.
    governed.pop("collection_timestamp", None)

    def encode(value: object) -> object:
        if isinstance(value, datetime):
            return value.isoformat()
        raise TypeError(type(value).__name__)

    payload = json.dumps(
        governed, default=encode, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def apply_cached_synthesis(brief: SignalBrief, cached: dict | None) -> SignalBrief:
    """Apply only a successful exact-hash cache entry to an eligible brief."""
    if (
        not cached
        or not is_synthesis_eligible(brief)
        or cached.get("governed_content_hash") != governed_content_hash(brief)
        or cached.get("status") != ProviderStatus.AVAILABLE.value
        or not cached.get("summary")
    ):
        return brief
    return replace(
        brief,
        seller_summary=str(cached["summary"]),
        language_provider=str(cached.get("provider") or "gemini"),
        summary_mode="GEMINI_ASSISTED",
    )


def signal_briefs_for_monitor(
    monitor: MonitorService, *, now: datetime | None = None
) -> tuple[SignalBrief, ...]:
    """Project governed briefs without invoking any language provider."""
    projected: list[SignalBrief] = []
    for event in monitor.events.values():
        evidence_ids = {item.evidence_id for item in event.evidence}
        observation = next(
            (
                item
                for item in monitor.observations.values()
                if item.raw_evidence.id in evidence_ids
            ),
            None,
        )
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
        brief = signal_brief(
            event,
            observation,
            freshness_hours=monitor.freshness_threshold_hours(source_id),
            now=now,
            target_reasons=reasons,
        )
        if monitor.repository:
            # Seller reads consume the exact worker-owned durable projection. They never
            # reconstruct a hash by guessing the configured provider model.
            cached = monitor.repository.technical_decomposition_for_event(brief.id)
            if cached and cached.get("projection"):
                technical = json.loads(cached["projection"])
                technical["governed_explanation"] = persisted_seller_explanation(
                    monitor.repository,
                    subject_key=technical_opportunity_subject_key(brief.id),
                    explanation_type=ExplanationType.TECHNICAL_OPPORTUNITY_FIT,
                )
                projected.append(replace(brief, technical_opportunity=technical))
                continue
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
        sorted(filter(is_synthesis_eligible, briefs), key=lambda item: item.id)
    )
    capped = False
    for brief in eligible:
        content_hash = governed_content_hash(brief)
        cached = repository.brief_synthesis(brief.id, content_hash)
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
                    brief_id=brief.id,
                    governed_content_hash=content_hash,
                    summary=None,
                    provider=None,
                    model=None,
                    status=ProviderStatus.NOT_CONFIGURED.value,
                    attempt_count=int(cached.get("attempt_count", 0)) if cached else 0,
                    next_retry_at=None,
                    synthesized_at=clock,
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
            brief_id=brief.id,
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
        )
    return BriefSynthesisBatch(
        attempted, reused, deferred, assisted, tuple(statuses), capped
    )
