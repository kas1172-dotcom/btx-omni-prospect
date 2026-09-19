from copy import deepcopy
from types import SimpleNamespace

from fastapi import Response

from btx_omni.api.accounts import _profile_health
from btx_omni.api.commercial import opportunity_workspace
from btx_omni.modules.commercial.projection import project_commercial_records
from btx_omni.modules.scoring.commercial_decisions import opportunity_decisions
from btx_omni.persistence.import_commercial_sample import (
    ACCOUNT_CROSSWALK,
    load_release_sample,
)
from btx_omni.providers.sample.environment import build_sample_environment


def environment():
    package = load_release_sample()
    ledgers = {ACCOUNT_CROSSWALK[a['account_id']]: a for a in package['accounts']}
    return project_commercial_records(build_sample_environment(), ledgers, revision='scope-test')


def test_workspace_reuses_existing_pursuits_and_customer_identity():
    sample = environment()
    before = deepcopy(sample.commercial_ledgers)
    result = opportunity_workspace(Response(), actor=None, runtime=SimpleNamespace(environment=lambda: sample))
    assert len(result['opportunities']) == sum(len(a['opportunities']) for a in before.values())
    row = next(r for r in result['opportunities'] if r['account_id'] == 'huxwrx')
    assert row['lane'] == 'CUSTOMER_EXPANSION'
    assert row['title'] == 'Warehouse rack-bracket replenishment review'
    assert row['attractiveness']['subject_id'] == row['opportunity_id']
    assert row['opportunity_priority']['subject_id'] == row['opportunity_id']
    assert row['next_action']
    assert sample.commercial_ledgers == before


def test_new_pursuit_does_not_inherit_old_component_commitment():
    ledger = environment().commercial_ledgers['honeywell']
    decision = opportunity_decisions(ledger, account_id='honeywell', revision='test')[0]
    factor = next(f for f in decision['opportunity_priority']['factors'] if f['key'] == 'program_durability')
    assert not factor['observed_fields']
    assert decision['qualification_status'] == 'UNKNOWN'
    assert decision['pwin']['status'] == 'INELIGIBLE'
    assert decision['attractiveness']['score'] is None


def test_customer_health_is_independent_of_new_opportunity_inputs():
    sample = environment()
    account = next(a for a in sample.accounts if a.id == 'honeywell')
    original = _profile_health(sample, account)
    sample.commercial_ledgers['honeywell']['opportunities'][0]['material_uncertainties'] = ['Changed pursuit only']
    assert _profile_health(sample, account) == original
    assert original['family'] == 'customer_health'
    assert original['subject_id'] == 'honeywell'
    assert original['score'] is not None


def test_omni_ranks_complete_opportunities_not_customer_scores():
    from datetime import UTC, datetime

    from btx_omni.modules.assistant.orchestration import OmniOrchestrator
    from btx_omni.modules.scoring.account_attractiveness import FACTORS
    sample = environment()
    for key in ['honeywell', 'boeing']:
        ledger = sample.commercial_ledgers[key]
        opportunity = ledger['opportunities'][0]
        scope = {'opportunity_id': opportunity['opportunity_id'], 'reviewed_as_of': ledger['as_of'], 'evidence_ids': [opportunity['opportunity_id']]}
        # Isolated complete input fixture, not authoring production evidence.
        opportunity['score_observations'] = [
            {**scope, 'path': f'{factor.key}.{child.rubric.key}', 'bin': child.rubric.bins[0].key}
            for factor in FACTORS for child in factor.subfactors
        ] + [{**scope, 'path': factor.key, 'bin': factor.single_rubric.bins[0].key}
             for factor in FACTORS if not factor.subfactors]
    answer = OmniOrchestrator().answer(sample, account_id=None,
        question='Which accounts have the highest attractiveness scores?', observed_at=datetime(2026, 9, 19, tzinfo=UTC))
    assert 'Opportunities ranked by Attractiveness' in answer.content
    assert answer.content.index('Boeing') < answer.content.index('Honeywell')
    assert 'Ground-assembly support-fixture pursuit' in answer.content
    assert 'APU service-support cover expansion' in answer.content
    assert 'OPP2-' not in answer.content
    assert set(answer.citations) == {'OPP2-BOEING', 'OPP2-HONEYWELL'}


def test_hero_briefings_are_distinct_and_do_not_claim_new_public_participation():
    sample = environment()
    ids = ['honeywell', 'boeing', 'kla', 'spacex', 'lockheed-martin', 'huxwrx']
    records = [sample.commercial_ledgers[key]['opportunities'][0] for key in ids]
    assert len({r['business_context'] for r in records}) == 6
    assert all(r['material_uncertainties'] and not r['briefing_provenance']['external_verification'] for r in records)
    assert 'does not establish BTX Javelin participation' in records[4]['business_context']


def test_omni_keeps_selected_pursuit_on_simplification_and_rejects_wrong_scope():
    from datetime import UTC, datetime

    import pytest

    from btx_omni.modules.assistant.service import OmniService
    sample = environment()
    context = {'selected_commercial_opportunity': {'account_id': 'honeywell', 'opportunity_id': 'OPP2-HONEYWELL', 'revision': 'scope-test'}}
    arguments = {'account_id': 'honeywell', 'observed_at': datetime(2026, 9, 19, tzinfo=UTC), 'context': context, 'intelligence_events': (), 'work_items': ()}
    first = OmniService().answer(sample, question='Explain this opportunity', **arguments)
    second = OmniService().answer(sample, question='Explain this more simply', **arguments)
    assert first.context_used == second.context_used
    assert first.recommended_action == second.recommended_action
    assert 'OPP2-' not in first.content
    assert 'not booked revenue' in first.content
    with pytest.raises(ValueError, match='scope differ'):
        OmniService().answer(sample, question='Explain', **{**arguments, 'account_id': 'boeing'})
    context['selected_commercial_opportunity']['revision'] = 'stale'
    with pytest.raises(ValueError, match='has changed'):
        OmniService().answer(sample, question='Explain', **arguments)
