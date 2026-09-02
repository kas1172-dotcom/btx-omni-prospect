"""Bounded, non-authoritative AI entity-candidate interpretation."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, Protocol

from btx_omni.ai.contracts import (
    EntityCandidateProposal,
    EntityCandidateResolutionRequest,
    LanguageProviderError,
)
from btx_omni.monitor.contracts import (
    EntityResolution,
    IntelligenceEvent,
    SourceObservation,
)
from btx_omni.monitor.ontology import ResolutionState
from btx_omni.monitor.repository import MonitorRepository
from btx_omni.monitor.resolution import AccountWatchProfile

_NON_DISCRIMINATIVE = frozenset({"and", "the", "company", "group", "systems", "technology", "technologies", "inc", "corp", "corporation", "llc", "ltd"})


def _tokens(value: str) -> frozenset[str]:
    return frozenset(
        token for token in re.findall(r"[\w]+", value.casefold())
        if len(token) > 2 and token not in _NON_DISCRIMINATIVE
    )


def generate_candidate_account_ids(
    *, mention: str,
    source_text: str,
    profiles: tuple[AccountWatchProfile, ...],
    markets: tuple[str, ...] = (),
    cap: int = 12,
) -> tuple[str, ...]:
    """Return governed, explainable candidates without fuzzy identity matching.

    A token overlap only puts a record in an AI review set.  It never resolves
    identity, and candidates with no discriminative governed evidence are not
    sent to the model.
    """
    mention_tokens = _tokens(mention)
    source_tokens = _tokens(source_text)
    ranked: list[tuple[int, str]] = []
    for profile in profiles:
        governed_names = (profile.legal_name, *profile.aliases, *profile.subsidiaries, *profile.usaspending_recipient_names)
        name_tokens = set().union(*(_tokens(value) for value in governed_names if value))
        overlap = len(mention_tokens & name_tokens)
        context = sum(
            1
            for value in (*profile.facilities, *profile.programs)
            if _tokens(value) & source_tokens
        )
        market = int(bool(set(markets) & set(profile.industries)))
        # A distinctive governed name/alias token is required.  Market and
        # context only narrow an already meaningful set.
        if overlap:
            ranked.append((overlap * 10 + context * 2 + market, profile.canonical_account_id))
    return tuple(account_id for _score, account_id in sorted(ranked, key=lambda item: (-item[0], item[1]))[:cap])


class CandidateProvider(Protocol):
    name: str
    config: Any

    def propose_entity_candidate(
        self, request: EntityCandidateResolutionRequest
    ) -> EntityCandidateProposal: ...


class EntityCandidateResolver:
    """AI may propose only supplied IDs; governed state remains non-canonical."""

    contract_version = "entity-candidate-resolution-v1"

    def __init__(self, provider: CandidateProvider, repository: MonitorRepository | None, profiles: tuple[AccountWatchProfile, ...], *, cap: int = 12) -> None:
        self.provider, self.repository, self.profiles, self.cap = provider, repository, profiles, cap

    def apply(self, event: IntelligenceEvent, observation: SourceObservation) -> IntelligenceEvent:
        subject = event.subject_entities[0] if len(event.subject_entities) == 1 else None
        if subject is None or subject.state is ResolutionState.RESOLVED:
            return event
        candidates = tuple(event.subject_entities[0].candidate_account_ids)[: self.cap]
        # Candidate generation is deliberately bounded before AI. This is a
        # review queue, not fuzzy identity matching, and output remains
        # UNRESOLVED unless separate governed evidence validates it.
        if not candidates:
            candidates = generate_candidate_account_ids(
                mention=subject.mention,
                source_text="\n".join((observation.title, observation.structured_payload or "")),
                profiles=self.profiles,
                markets=event.markets,
                cap=self.cap,
            )
        if not candidates:
            return event
        labels = tuple(next((profile.legal_name for profile in self.profiles if profile.canonical_account_id == account_id), account_id) for account_id in candidates)
        request = EntityCandidateResolutionRequest(
            subject.mention[:300], observation.title[:800], observation.raw_evidence.locator,
            observation.source_identity.source_native_ids, candidates, labels,
            self.contract_version,
        )
        model = str(getattr(getattr(self.provider, "config", None), "model", ""))
        key = hashlib.sha256(json.dumps({"evidence": observation.source_version.content_hash, "request": request.__dict__, "provider": self.provider.name, "model": model}, sort_keys=True, default=list).encode()).hexdigest()
        cached = self.repository.entity_candidate_resolution(key) if self.repository else None
        if cached:
            try:
                proposal = json.loads(cached["projection"])
            except (TypeError, json.JSONDecodeError):
                cached = None
        if not cached:
            try:
                response = self.provider.propose_entity_candidate(request)
                proposal = response.__dict__
            except (LanguageProviderError, TypeError, ValueError):
                return event
            if self.repository:
                self.repository.save_entity_candidate_resolution(cache_key=key, projection=proposal, provider=self.provider.name, model=model or None, status="AVAILABLE", processed_at=datetime.now(UTC))
        proposed = proposal.get("proposed_canonical_account_id") if isinstance(proposal, dict) else None
        ranked = proposal.get("candidate_account_ids") if isinstance(proposal, dict) else None
        if proposed is not None and proposed not in candidates:
            return event
        if not isinstance(ranked, list) or any(item not in candidates for item in ranked):
            ranked = []
        if proposed:
            revised = EntityResolution(subject.mention, None, ResolutionState.UNRESOLVED, "gemini_candidate_pending_validation", "bounded Gemini candidate proposal; not canonical identity evidence", (proposed,))
        elif len(ranked) > 1:
            revised = EntityResolution(subject.mention, None, ResolutionState.AMBIGUOUS, "gemini_candidates_ambiguous", "bounded Gemini candidates require governed review", tuple(ranked))
        else:
            return event
        return replace(event, subject_entities=(revised,), resolution_state=revised.state)
