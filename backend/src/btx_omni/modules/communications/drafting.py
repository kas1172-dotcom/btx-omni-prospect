"""Governed language proposals for communications; no workflow authority lives here."""

from __future__ import annotations

from dataclasses import dataclass

from btx_omni.ai.contracts import (
    GovernedDraft,
    GovernedDraftingRequest,
    LanguageProvider,
    LanguageProviderError,
    ProviderStatus,
)


@dataclass(frozen=True)
class DraftingOutcome:
    proposal: GovernedDraft
    provider_status: ProviderStatus
    assisted: bool


def deterministic_draft_fallback(request: GovernedDraftingRequest) -> GovernedDraft:
    """A safe editable proposal when language assistance is unavailable."""
    subject = (
        request.current_subject or f"Update regarding {request.subject_display_name}"
    )
    body = request.current_body or (
        f"Draft manually from the governed context for {request.subject_display_name}. "
        "Confirm every statement and citation before saving or sending."
    )
    return GovernedDraft(
        subject,
        body,
        request.evidence_ids,
        "deterministic",
        "",
        request.contract_version,
    )


def draft_governed_content(
    request: GovernedDraftingRequest, provider: LanguageProvider | None
) -> DraftingOutcome:
    if provider is None or not provider.configured:
        return DraftingOutcome(
            deterministic_draft_fallback(request), ProviderStatus.NOT_CONFIGURED, False
        )
    draft = getattr(provider, "draft_governed_content", None)
    if not callable(draft):
        return DraftingOutcome(
            deterministic_draft_fallback(request), ProviderStatus.UNAVAILABLE, False
        )
    try:
        proposal = draft(request)
        allowed = set(request.evidence_ids) | {
            item.evidence_id for item in request.public_research
        }
        if (
            not isinstance(proposal, GovernedDraft)
            or not set(proposal.evidence_ids) <= allowed
        ):
            raise ValueError("Draft provider returned unsupported content.")
        return DraftingOutcome(proposal, ProviderStatus.AVAILABLE, True)
    except LanguageProviderError as error:
        return DraftingOutcome(
            deterministic_draft_fallback(request), error.status, False
        )
    except (RuntimeError, TimeoutError, ValueError):
        return DraftingOutcome(
            deterministic_draft_fallback(request), ProviderStatus.UNAVAILABLE, False
        )
