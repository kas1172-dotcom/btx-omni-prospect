from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from test_commercial_persistence import importer_package

from btx_omni.ai.contracts import LanguageResult
from btx_omni.modules.assistant.commercial_tools import CommercialToolSession
from btx_omni.modules.assistant.service import OmniService
from btx_omni.modules.commercial.projection import project_commercial_records
from btx_omni.persistence.commercial_import import CommercialImportRepository
from btx_omni.persistence.models import metadata
from btx_omni.providers.sample.environment import build_sample_environment


def imported(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'omni-tools.db'}")
    metadata.create_all(engine)
    repository = CommercialImportRepository(engine)
    original = build_sample_environment()
    repository.import_package(importer_package(), {"test-account": "honeywell"}, original, apply=True)
    revision, records = repository.snapshot()
    return project_commercial_records(original, records, revision=revision)


class SequentialProvider:
    name = "fixture-language-provider"
    configured = True

    def __init__(self, selections):
        self.selections = iter(selections)
        self.requests = []

    def choose_canonical_read(self, request):
        self.requests.append(request)
        return next(self.selections)

    def synthesize(self, request):
        self.synthesis = request
        return LanguageResult(request.governed_answer, self.name, "fixture", request.evidence_ids)


def test_general_model_intent_cannot_discard_explicit_account_for_record_lookup(tmp_path):
    from btx_omni.ai.contracts import IntentInterpretation, ReadIntent

    class BroadInterpreter(SequentialProvider):
        def interpret(self, request):
            return IntentInterpretation(ReadIntent.GENERAL_OVERVIEW)

    provider = BroadInterpreter([
        {'tool': 'read_evidence', 'arguments': {'record_id': 'INV-NOT-IN-BTX-9127'}},
        {'done': True},
    ])
    answer = OmniService(provider).answer(
        imported(tmp_path), account_id='honeywell',
        question='Find invoice INV-NOT-IN-BTX-9127 and its payment date; do not substitute another.',
        observed_at=datetime(2026, 8, 31, tzinfo=UTC),
        context={'surface': 'ACCOUNT_DETAIL', 'selected_account_id': 'honeywell'},
        intelligence_events=(), work_items=(),
    )
    assert answer.account_id == 'honeywell'
    lookup = answer.structured_reads['reads'][0]['result']
    assert lookup['status'] == 'NOT_FOUND_IN_ACCOUNT' and lookup['record'] is None
    assert lookup['account_id'] == 'honeywell'
    assert 'correct record reference' in answer.recommended_action
    assert 'Associated payment dates and amounts are unknown' in answer.content
    assert 'quote-history' not in answer.content


def test_context_specific_tools_are_not_advertised_without_a_selection(tmp_path):
    provider = SequentialProvider([{'done': True}])
    session = CommercialToolSession(imported(tmp_path), 'honeywell')
    session.run(provider, 'Explain the stored account records')
    names = {tool['name'] for tool in provider.requests[0].tools}
    assert 'read_selected_market' not in names and 'read_selected_relationship' not in names
    assert {'read_history', 'read_fulfillment', 'read_evidence', 'read_decisions'} <= names
    attempted = session.run(SequentialProvider([{'tool': 'read_selected_market', 'arguments': {}}]), 'Read exchange rates')
    assert attempted['stop_reason'] == 'READ_SELECTION_FAILED' and not attempted['reads']


def test_model_selected_sequential_reads_use_imported_records_and_feed_followups(tmp_path):
    sample = imported(tmp_path)
    provider = SequentialProvider([
        {"tool": "read_history", "arguments": {}},
        {"tool": "read_fulfillment", "arguments": {}},
        {"tool": "read_evidence", "arguments": {"record_id": "v"}},
        {"done": True},
    ])
    answer = OmniService(provider).answer(sample, account_id="honeywell", question="Explain history, delivery and the acceptance record together",
                                          observed_at=datetime(2026, 8, 31, tzinfo=UTC), context={}, intelligence_events=(), work_items=())
    trace = answer.structured_reads
    assert trace["model_requested_stop"] and trace["stop_reason"] == "MODEL_DONE"
    assert [s["tool"] for s in trace["steps"]] == ["read_history", "read_fulfillment", "read_evidence"]
    assert provider.requests[1].completed_reads[0]["result"]["ttm"]["revenue_minor"] == 400
    assert provider.requests[2].completed_reads[1]["tool"] == "read_fulfillment"
    assert trace["reads"][2]["result"]["record"]["revenue_event_id"] == "v"
    assert '"revenue_money": {"currency": "USD", "major_units": "4.00"' in provider.synthesis.governed_answer
    assert '"revenue_minor": 400' not in provider.synthesis.governed_answer
    assert sample.commercial_ledgers["honeywell"]["ttm_summary"]["revenue_minor"] == 400


def test_read_scope_write_rejection_repeat_cancel_and_budget_are_explicit(tmp_path):
    session = CommercialToolSession(imported(tmp_path), "honeywell")
    for name, args in [("send_email", {}), ("read_history", {"account_id": "boeing"}),
                       ("read_evidence", {"record_id": "../../another-account"}),
                       ("compare_quote_revisions", {"quote_id": "another-account"})]:
        with pytest.raises(ValueError):
            session.read(name, args)
    absent = session.read('read_evidence', {'record_id': 'another-account'})
    assert absent['status'] == 'NOT_FOUND_IN_ACCOUNT' and absent['record'] is None
    assert absent['account_id'] == 'honeywell' and 'other_account_id' not in absent
    trace = session.run(SequentialProvider([{'tool': 'read_evidence', 'arguments': {'record_id': 'INV-NOT-IN-BTX-9127'}}, {'done': True}]), 'Find this exact invoice')
    assert trace['stop_reason'] == 'MODEL_DONE'
    assert trace['reads'][0]['result']['status'] == 'NOT_FOUND_IN_ACCOUNT'
    assert trace['steps'][0]['evidence_ids'] == []
    repeated = SequentialProvider([{"tool": "read_history", "arguments": {}}] * 4)
    result = session.run(repeated, "Explain")
    assert result["stop_reason"] == "REPEATED_READ" and len(result["reads"]) == 1 and not result["model_requested_stop"]
    assert session.run(SequentialProvider([]), "Explain", canceled=lambda: True)["stop_reason"] == "CANCELED"
    assert session.run(SequentialProvider([]), "Explain", deadline_seconds=0)["stop_reason"] == "DEADLINE"
    capped = session.run(SequentialProvider([{"tool": "read_history", "arguments": {}}]), "Explain", max_calls=1)
    assert capped["stop_reason"] == "TOOL_BUDGET" and not capped["model_requested_stop"]
    rejected = session.run(SequentialProvider([{"tool": "read_history", "arguments": {}, "score": 100}]), "Explain")
    assert rejected["stop_reason"] == "READ_SELECTION_FAILED" and not rejected["reads"]


def test_invalid_followup_read_is_visible_in_answer_not_only_diagnostics(tmp_path):
    sample = imported(tmp_path)
    provider = SequentialProvider([{'tool': 'read_history', 'arguments': {}}, {'tool': 'invented_read', 'arguments': {}}])
    answer = OmniService(provider).answer(sample, account_id='honeywell', question='Explain history, delivery and the acceptance record together',
                                          observed_at=datetime(2026, 8, 31, tzinfo=UTC), context={}, intelligence_events=(), work_items=())
    assert answer.context_used['canonical_retrieval_status'] == 'PARTIAL'
    assert answer.content.startswith('This answer is limited to completed record reads;')
    assert answer.structured_reads['stop_reason'] == 'READ_SELECTION_FAILED'
    assert any('further retrieval stopped' in message for message in answer.missingness)


def test_selected_account_record_comparison_does_not_require_two_companies(tmp_path):
    sample = imported(tmp_path)
    provider = SequentialProvider([{'tool': 'read_fulfillment', 'arguments': {}}, {'done': True}])
    answer = OmniService(provider).answer(sample, account_id='honeywell', question='Compare delivery and history',
                                          observed_at=datetime(2026, 8, 31, tzinfo=UTC), context={}, intelligence_events=(), work_items=())
    assert answer.account_id == 'honeywell'
    assert answer.structured_reads['steps'][0]['tool'] == 'read_fulfillment'
    from btx_omni.modules.assistant.orchestration import OmniOrchestrator
    assert len(OmniOrchestrator._comparison_accounts_named('compare honeywellness and boeing', sample)) == 1


def test_fulfillment_tool_retains_acceptance_gaps_even_when_remaining_is_zero(tmp_path):
    from copy import deepcopy
    from dataclasses import replace

    sample = imported(tmp_path)
    ledger = deepcopy(sample.commercial_ledgers["honeywell"])
    ledger["cancellations"] = [{"cancellation_id": "cancel", "order_line_id": "ol", "date": "2026-08-21", "quantity": 4, "value_minor": 400}]
    # Isolated projection regression: a cancellation can close remaining shipment
    # quantity without resolving acceptance on the already-shipped balance.
    sample = replace(sample, commercial_ledgers={"honeywell": ledger})
    result = CommercialToolSession(sample, "honeywell").read("read_fulfillment", {})
    assert result["open_line_count"] == 0
    assert result["lines"][0]["shipped_unaccepted_quantity"] == 2
    assert result["recorded_history_totals"]["shipped_unaccepted_quantity"] == 2
    assert 'accepted_quantity' not in result['recorded_history_totals']
    assert 'not TTM totals' in result['omitted_totals']
    assert result["ttm_summary"] == ledger["ttm_summary"]
