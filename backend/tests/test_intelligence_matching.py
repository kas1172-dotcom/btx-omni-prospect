from btx_omni.domain.common import EvidenceState, MatchState
from btx_omni.modules.intelligence.signals import normalize_signal
from btx_omni.modules.matching.commercial import (
    MatchReviewState,
    match_component_to_quote,
)
from btx_omni.providers.sample.environment import build_sample_environment


def test_public_signal_normalization_retains_real_company_lineage() -> None:
    sample = build_sample_environment()
    accounts = {account.legal_name: account.id for account in sample.accounts}
    raw = next(item for item in sample.intelligence_events if item.account_name == "Lockheed Martin")
    normalized = normalize_signal(raw, account_name_to_id=accounts, provenance=next(item for item in sample.public_signals if item.account_id == accounts[raw.account_name]).provenance)
    assert normalized.account_id == "lockheed-martin"
    assert normalized.source_url == raw.source_url and normalized.evidence_ids
    assert normalized.evidence_state is EvidenceState.CONFIRMED


def test_simulated_commercial_matching_is_explicit_and_explainable() -> None:
    sample = build_sample_environment()
    exact = match_component_to_quote(sample.matching_components[0], sample.matching_quotes[0])
    structured = match_component_to_quote(sample.matching_components[1], sample.matching_quotes[0])
    assert exact.method is MatchState.EXACT_PART and exact.quote_id == "pq-01001"
    assert structured.method is MatchState.STRUCTURED_SIMILARITY
    assert structured.business_unit == "era-industries" and structured.capability_ids
    assert structured.evidence_state is EvidenceState.CONFIRMED


def test_absent_history_never_fabricates_a_match() -> None:
    sample = build_sample_environment()
    absent = match_component_to_quote(sample.matching_components[0], None)
    assert absent.quote_id is None and absent.method is MatchState.INSUFFICIENT_DATA
    assert absent.review_state is MatchReviewState.AMBIGUOUS


def test_intelligence_contains_only_curated_public_events() -> None:
    sample = build_sample_environment()
    accounts = {account.legal_name for account in sample.accounts}
    assert sample.intelligence_events
    assert {event.account_name for event in sample.intelligence_events} <= accounts
    assert all("sample.invalid" not in event.source_url for event in sample.intelligence_events)
