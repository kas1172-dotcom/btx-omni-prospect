from btx_omni.domain.common import EvidenceState, MatchState
from btx_omni.modules.intelligence.signals import normalize_signal
from btx_omni.modules.matching.commercial import (
    MatchReviewState,
    match_component_to_quote,
)
from btx_omni.providers.sample.environment import build_sample_environment


def test_signal_normalization_retains_lineage_resolution_and_evidence_state() -> None:
    sample = build_sample_environment()
    accounts = {account.legal_name: account.id for account in sample.accounts}
    raw = next(item for item in sample.intelligence_events if item.account_name == "Defense Prime One")
    normalized = normalize_signal(raw, account_name_to_id=accounts, provenance=next(item for item in sample.public_signals if item.account_id == accounts[raw.account_name]).provenance)
    assert normalized.account_id == "acct-02-001"
    assert normalized.source_url == raw.source_url and normalized.evidence_ids
    assert normalized.evidence_state is EvidenceState.CONFIRMED
    assert "Defense Platform" in normalized.relevance_explanation


def test_defense_award_open_quote_exact_and_structured_correlations_are_explainable() -> None:
    sample = build_sample_environment()
    exact = match_component_to_quote(sample.matching_components[0], sample.matching_quotes[0])
    structured = match_component_to_quote(sample.matching_components[1], sample.matching_quotes[0])
    assert exact.method is MatchState.EXACT_PART and exact.quote_id == "quote-acct-02-001"
    assert structured.method is MatchState.STRUCTURED_SIMILARITY
    assert structured.business_unit == "Southwest" and structured.capability_ids == ("precision-machining",)
    assert structured.evidence_state is EvidenceState.INFERRED


def test_conflict_missing_and_absent_history_never_fabricate_a_match() -> None:
    sample = build_sample_environment()
    conflict = match_component_to_quote(sample.matching_components[2], sample.matching_quotes[1])
    missing = match_component_to_quote(sample.matching_components[3], sample.matching_quotes[1])
    absent = match_component_to_quote(sample.matching_components[0], None)
    assert (conflict.method, conflict.review_state) == (MatchState.NO_MATCH, MatchReviewState.CONFLICT)
    assert (missing.method, missing.review_state) == (MatchState.INSUFFICIENT_DATA, MatchReviewState.AMBIGUOUS)
    assert absent.quote_id is None and absent.method is MatchState.INSUFFICIENT_DATA


def test_intelligence_scenarios_preserve_external_internal_separation_and_conflict() -> None:
    sample = build_sample_environment()
    events = {event.account_name: event for event in sample.intelligence_events}
    assert events["Silicon Expansion Co"].kind.value == "EXPANSION"
    assert events["External Top Target"].evidence_state is EvidenceState.INFERRED
    assert events["Internal Core Customer"].evidence_state is EvidenceState.CONFIRMED
    assert events["Conflicted Evidence Labs"].evidence_state is EvidenceState.CONFLICTING
