"""Explicit, human-confirmed Organization Candidate promotion; Monitor never calls this."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import insert, select, update

from btx_omni.api.runtime import PocRuntime
from btx_omni.domain.common import DataMode
from btx_omni.domain.markets import PRIMARY_MARKETS
from btx_omni.monitor.contracts import OrganizationCandidate
from btx_omni.monitor.ontology import CandidateReviewState, ResolutionState
from btx_omni.monitor.repository import _organization_candidate_from_row
from btx_omni.persistence.durable_accounts import DurablePublicProspect
from btx_omni.persistence.models import (
    durable_public_accounts,
    monitor_candidate_promotion_audits,
    monitor_organization_candidates,
)


class CandidatePromotionError(ValueError):
    """A governed promotion request cannot safely create a canonical Account."""


@dataclass(frozen=True)
class PromotionResult:
    account: DurablePublicProspect
    candidate: OrganizationCandidate
    created: bool


def _promotion_payload(candidate: OrganizationCandidate) -> str:
    value = candidate.provenance
    return json.dumps({
        "source_system": value.source_system,
        "source_record_id": value.source_record_id,
        "source_url": value.source_url,
        "observed_at": value.observed_at.isoformat(),
        "recorded_at": value.recorded_at.isoformat(),
        "classification": value.classification.value,
        "evidence_state": value.evidence_state.value,
        "data_mode": value.data_mode.value,
        "synthetic": value.synthetic,
        "sensitivity_tags": sorted(item.value for item in value.sensitivity_tags),
        "missing_fields": list(value.missing_fields),
    })


class CandidatePromotionService:
    """Owns the one transaction linking a review candidate to a durable Prospect."""

    def promote(self, runtime: PocRuntime, candidate_id: str, *, confirmed: bool) -> PromotionResult:
        if not confirmed:
            raise CandidatePromotionError("explicit promotion confirmation is required.")
        if not runtime.monitor.repository or not runtime.durable_accounts:
            raise CandidatePromotionError("durable candidate promotion is unavailable.")

        engine = runtime.monitor.repository.engine
        with engine.begin() as connection:
            row = connection.execute(
                select(monitor_organization_candidates).where(monitor_organization_candidates.c.id == candidate_id)
            ).mappings().one_or_none()
            if row is None:
                raise CandidatePromotionError("Organization Candidate was not found.")
            audit = connection.execute(select(monitor_candidate_promotion_audits).where(
                monitor_candidate_promotion_audits.c.candidate_id == candidate_id
            )).mappings().one_or_none()
            candidate = _organization_candidate_from_row(dict(row), dict(audit) if audit else None)
            if candidate.promoted_account_id:
                account_row = connection.execute(
                    select(durable_public_accounts).where(durable_public_accounts.c.id == candidate.promoted_account_id)
                ).mappings().one_or_none()
                if account_row is None:
                    raise CandidatePromotionError("candidate promotion audit references no durable canonical Account.")
                existing = next(
                    item for item in runtime.durable_accounts.accounts() if item.account.id == candidate.promoted_account_id
                )
                return PromotionResult(existing, candidate, False)
            if candidate.review_state in {CandidateReviewState.AMBIGUOUS, CandidateReviewState.REJECTED}:
                raise CandidatePromotionError(f"candidate review state {candidate.review_state.value} cannot be promoted.")
            if candidate.review_state not in {CandidateReviewState.PENDING_REVIEW, CandidateReviewState.READY_FOR_PROMOTION}:
                raise CandidatePromotionError(f"candidate review state {candidate.review_state.value} cannot be promoted.")
            if candidate.resolution_state is not ResolutionState.UNRESOLVED or candidate.candidate_account_ids:
                raise CandidatePromotionError("candidate does not have a conflict-free unresolved canonical identity.")
            if not candidate.normalized_name or not candidate.canonical_industry or candidate.canonical_industry not in PRIMARY_MARKETS:
                raise CandidatePromotionError("candidate lacks the evidence-backed identity required for a canonical Account.")
            if candidate.provenance.data_mode is not DataMode.CONNECTED or candidate.provenance.synthetic:
                raise CandidatePromotionError("candidate lacks non-synthetic public provenance required for promotion.")

            promoted_at = datetime.now(UTC)
            try:
                account = runtime.durable_accounts.create_public_prospect(
                    legal_name=candidate.source_name,
                    industries=(candidate.canonical_industry,),
                    provenance=candidate.provenance,
                    domain=candidate.verified_domain,
                    source_identifiers=candidate.source_identifiers,
                    originating_candidate_id=candidate.id,
                    curated_accounts=runtime.environment().accounts,
                    created_at=promoted_at,
                    promoted_at=promoted_at,
                    promotion_provenance=candidate.provenance,
                    connection=connection,
                )
            except ValueError as exc:
                raise CandidatePromotionError(str(exc)) from exc
            connection.execute(update(monitor_organization_candidates).where(
                monitor_organization_candidates.c.id == candidate.id
            ).values(
                review_state=CandidateReviewState.PROMOTED.value,
                updated_at=promoted_at,
            ))
            connection.execute(insert(monitor_candidate_promotion_audits).values(
                candidate_id=candidate.id,
                canonical_account_id=account.account.id,
                promoted_at=promoted_at,
                promotion_provenance=_promotion_payload(candidate),
            ))
            promoted = _organization_candidate_from_row(dict(connection.execute(
                select(monitor_organization_candidates).where(monitor_organization_candidates.c.id == candidate.id)
            ).mappings().one()), {
                "canonical_account_id": account.account.id,
                "promoted_at": promoted_at,
                "promotion_provenance": _promotion_payload(candidate),
            })

        runtime.refresh_durable_accounts()
        return PromotionResult(account, promoted, True)
