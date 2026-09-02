from btx_omni.ai.contracts import (
    GovernedDraft,
    GovernedDraftingRequest,
    LanguageProviderError,
    ProviderStatus,
    PublicWebFinding,
)
from btx_omni.modules.communications.drafting import draft_governed_content


def request() -> GovernedDraftingRequest:
    return GovernedDraftingRequest(
        subject_display_name="Boeing",
        instruction="Draft a concise manager update.",
        draft_kind="SELLER_COMMUNICATION",
        governed_facts=(
            "Canonical Customer: Boeing.",
            "Technical fit is capability alignment, not supplier participation.",
        ),
        evidence_ids=("ev-1",),
        current_subject="Boeing update",
        current_body="Existing governed draft.",
        public_research=(
            PublicWebFinding(
                "web:1",
                "Public award",
                "https://public.example.test/award",
                "Public source",
                "Award update.",
            ),
        ),
    )


class Provider:
    configured = True

    def __init__(self, value=None):
        self.value = value
        self.calls = 0

    def draft_governed_content(self, _request):
        self.calls += 1
        if isinstance(self.value, Exception):
            raise self.value
        return self.value or GovernedDraft(
            "Boeing update",
            "Proposed governed language.",
            ("ev-1", "web:1"),
            "fake",
            "fake-v1",
            "governed-drafting-v1",
        )


def test_governed_draft_is_a_language_proposal_with_only_supplied_evidence() -> None:
    provider = Provider()
    outcome = draft_governed_content(request(), provider)
    assert outcome.assisted and outcome.provider_status is ProviderStatus.AVAILABLE
    assert provider.calls == 1
    assert set(outcome.proposal.evidence_ids) == {"ev-1", "web:1"}
    assert "supplier participation" in request().governed_facts[1]


def test_invented_model_evidence_is_rejected_and_manual_fallback_remains_usable() -> (
    None
):
    provider = Provider(
        GovernedDraft(
            "Bad",
            "Unsupported claim.",
            ("invented",),
            "fake",
            "fake",
            "governed-drafting-v1",
        )
    )
    outcome = draft_governed_content(request(), provider)
    assert (
        not outcome.assisted and outcome.provider_status is ProviderStatus.UNAVAILABLE
    )
    assert outcome.proposal.body == "Existing governed draft."
    assert outcome.proposal.evidence_ids == ("ev-1",)


def test_provider_failure_preserves_editable_manual_draft_without_mutating_workflow() -> (
    None
):
    outcome = draft_governed_content(
        request(), Provider(LanguageProviderError(ProviderStatus.QUOTA))
    )
    assert not outcome.assisted and outcome.provider_status is ProviderStatus.QUOTA
    assert outcome.proposal.subject == "Boeing update"
    assert outcome.proposal.body == "Existing governed draft."
