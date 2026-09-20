from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from test_customer_health_v2 import scenario
from test_public_signal_assessment import NOW, records, score

from btx_omni.modules.scoring.account_attractiveness import AccountAttractivenessInputs
from btx_omni.modules.scoring.action_priority import rank_actions
from btx_omni.modules.scoring.monitoring_coverage import monitoring_complete
from btx_omni.modules.scoring.opportunity_gates import opportunity_gates
from btx_omni.modules.scoring.prospect_fit import prospect_fit_projection
from btx_omni.modules.scoring.public_rules import freshness_points, risk_points
from btx_omni.monitor.contracts import NormalizedClaim
from btx_omni.persistence.durable_accounts import (
    _account_from_payload,
    _account_payload,
)
from btx_omni.providers.sample.environment import build_sample_environment


def test_action_classes_completeness_score_due_created_identity_and_filtering():
    def row(identity, value, **kwargs):
        return {'id': identity, 'status': 'OPEN', 'underlying_decision': value, **kwargs}
    rows = [row('high-opportunity', {'score': 99}), row('risk', {'score': 72, 'disposition': 'ESCALATE_NOW'}),
        row('safety', {'score': 1}, confirmed_block=True), row('validate', {'score': 90, 'disposition': 'VALIDATE_IMMEDIATELY'}),
        row('unknown', {'score': None, 'score_range': {'low': 20, 'high': 100}}),
        row('done', {'score': 100}, status='COMPLETED'), row('dismissed', {'score': 100}, status='DISMISSED'),
        row('snoozed', {'score': 100}, status='SNOOZED'), row('invalid', {'score': 100}, valid=False)]
    assert [r['id'] for r in rank_actions(rows)] == ['safety', 'risk', 'validate', 'high-opportunity', 'unknown']
    assert rank_actions(rows) == rank_actions(list(reversed(rows)))
    ties = [row('z', {'score': 80}), row('b', {'score': 80}, due_date='2026-10-01'), row('a', {'score': 80}, due_date='2026-10-01')]
    assert [r['id'] for r in rank_actions(ties)] == ['a', 'b', 'z']
    assert len(rank_actions(ties + ties)) == 3


def test_complete_prospect_fit_survives_canonical_persistence_roundtrip():
    account = next(a for a in build_sample_environment().accounts if a.id == 'textron')
    facts = {'target_cohort_match': {'state': 'PRIMARY'}, 'manufacturing_fit': {'state': 'ONE_MATCHING_SITE'},
        'scale': {'organization_ttm_revenue_usd': 100_000_000}, 'outsourcing_posture': {'state': 'EXTERNAL_SUPPLIERS'},
        'strategic_archetype': {'state': 'TIER_ONE'}, 'existing_btx_access': {'state': 'RELEVANT_NAMED_CONTACT'}}
    observations = {key: {**value, 'account_id': account.id, 'evidence_ids': [f'review-{key}'], 'source_urls': ['https://example.org/review'],
        'reviewed_as_of': '2026-08-31', 'review_state': 'VERIFIED'} for key, value in facts.items()}
    account = replace(account, prospect_fit_evidence=observations)
    restored = _account_from_payload(_account_payload(account))
    result = prospect_fit_projection(restored, applicable=True, as_of=date(2026, 8, 31))
    assert result.score == 80 and result.coverage == 1
    assert result.factors[2].points == Decimal('11.25')
    assert prospect_fit_projection(restored, applicable=False).score is None
    stale = prospect_fit_projection(restored, applicable=True, as_of=date(2027, 8, 31))
    assert stale.score is None and stale.coverage == 0
    observations['scale']['account_id'] = 'another-account'
    assert prospect_fit_projection(account, applicable=True, as_of=date(2026, 8, 31)).score is None


def test_opportunity_gates_are_three_state_and_do_not_derive_from_score():
    account = scenario()
    opportunity = account['opportunities'][0]
    selections = {'btx_manufacturing_fit.material_match': 'ROUTINE', 'btx_manufacturing_fit.process_tolerance_match': 'ROUTINE',
        'btx_manufacturing_fit.certification_compliance_fit': 'ALL_MET', 'program_durability.expected_production_horizon': 'FIVE_TO_NINE_YEARS',
        'program_durability.repeat_production_pattern': 'ESTABLISHED_RECURRING', 'program_durability.commitment_strength': 'FUNDED_AWARDED_CONTRACTED',
        'program_durability.industry_specific_maturity_evidence': 'PARTIAL_CREDIBLE'}
    priority = {'score': Decimal(90), 'data_coverage': {'ratio': 1}}
    inputs = AccountAttractivenessInputs(selections)
    assert opportunity_gates(account, opportunity, inputs, priority)['qualified'] == 'UNKNOWN'
    opportunity['qualification_evidence'] = {'opportunity_id': opportunity['opportunity_id'], 'reviewed_as_of': account['as_of'],
        'evidence_ids': [opportunity['opportunity_id']], 'identity_and_site_confirmed': True, 'sourced_dated_need': True,
        'scoped_component_and_external_sourcing': True, 'no_disqualifiers': True, 'program_current': True,
        'review_window_on': '2026-09-10', 'essential_assertion_confidence': dict.fromkeys(['identity', 'need', 'capability', 'timing'], 75)}
    assert opportunity_gates(account, opportunity, inputs, priority)['durable_best_bet'] is True
    selections['program_durability.expected_production_horizon'] = 'UNDER_TWO_YEARS_OR_ONE_OFF'
    assert opportunity_gates(account, opportunity, inputs, priority)['durable'] == 'NO'
    opportunity['qualification_evidence']['no_disqualifiers'] = False
    assert opportunity_gates(account, opportunity, inputs, priority)['qualified'] == 'NO'


def test_one_primary_source_full_specificity_and_verified_site_matches_normative_total():
    event, observation = records()
    eid = event.evidence[0].evidence_id
    values = {'recipient': 'KLA Corporation', 'instrument_id': 'official-instrument', 'action_type': 'award', 'amount': '1000000',
        'amount_basis': 'obligated dollars', 'effective_date': '2026-09-07', 'work_description': 'specified manufacturing research',
        'site_identity_verified': 'true', 'authoritative_identifier_verified': 'true'}
    claims = tuple(c for c in event.claims if c.predicate not in values) + tuple(NormalizedClaim(k, v, (eid,), 'deterministic_structured_mapping', 'source fixture') for k, v in values.items())
    result = score(replace(event, claims=claims), observation)
    assert result['score'] == Decimal('88.75')
    assert result['seller_recommendation_eligible'] is True
    conflict = NormalizedClaim('amount', '2000000', (eid,), 'deterministic_structured_mapping', 'conflicting source fixture')
    conflicted = score(replace(event, claims=claims + (conflict,)), observation)
    assert 'amount' in conflicted['specificity_missing_fields']
    assert conflicted['score'] < result['score']


def test_public_policy_boundaries_and_missing_not_zero():
    assert [freshness_points(age, 720) for age in [0, 180, 181, 360, 361, 720, 721]] == [100, 100, 75, 75, 50, 50, 0]
    assert freshness_points(-1, 720) is None
    assert risk_points('materiality', {'affected_revenue_share_percent': '50'}) is None
    assert risk_points('materiality', {'affected_revenue_share_percent': '0', 'affected_backlog_share_percent': '0'}) == 0
    assert risk_points('breadth', {'risk_breadth': 'PROGRAM'}) == 25
    # Rubric v2 section 7 / R3 retires the misleading reversibility key.
    assert risk_points('mitigation', {'risk_mitigation': 'FULLY_MITIGATED'}) == 0
    assert risk_points('mitigation', {'risk_mitigation': 'DIFFICULT'}) is None


def test_monitoring_zero_requires_complete_current_sources():
    status = SimpleNamespace(state='HEALTHY', last_success_at=NOW)
    monitor = SimpleNamespace(watch_targets={'source': [SimpleNamespace(canonical_account_id='account')]}, repository=None,
        durable_snapshot=lambda: None, operational_status=lambda *a, **k: status)
    assert monitoring_complete(monitor, 'account') is True
    status.state = 'PARTIAL'
    assert monitoring_complete(monitor, 'account') is False
    assert monitoring_complete(monitor, 'other') is False


def test_updated_reference_inputs_import_replay_and_scores_survive_reopen(tmp_path):
    from sqlalchemy import create_engine

    from btx_omni.modules.commercial.evidence import resolve_commercial_evidence
    from btx_omni.modules.scoring.commercial_decisions import customer_decisions
    from btx_omni.persistence import models
    from btx_omni.persistence.commercial_import import CommercialImportRepository
    from btx_omni.persistence.import_commercial_sample import (
        ACCOUNT_CROSSWALK,
        load_release_sample,
    )

    engine = create_engine(f'sqlite:///{tmp_path / "scoring.sqlite"}')
    models.metadata.create_all(engine)
    repo = CommercialImportRepository(engine)
    package = load_release_sample()
    environment = build_sample_environment()
    first = repo.import_package(package, ACCOUNT_CROSSWALK, environment, apply=True)
    replay = repo.import_package(package, ACCOUNT_CROSSWALK, environment, apply=True)
    assert first['created'] > 0
    assert replay['created'] == replay['updated'] == replay['removed'] == 0
    engine.dispose()
    restored = repo.accounts()
    for source in package['accounts']:
        aid = ACCOUNT_CROSSWALK[source['account_id']]
        assert restored[aid] == source
        decisions = customer_decisions(restored[aid], account_id=aid, revision=repo.revision(), current_customer=True)
        for family in ('customer_health', 'internal_commercial_risk'):
            assert decisions[family]['score'] is not None
            assert decisions[family]['data_coverage']['ratio'] == 1
            for factor in decisions[family]['factors']:
                assert all(resolve_commercial_evidence(restored[aid], eid) for eid in factor['evidence_ids'])
        # Deliberately unqualified pursuits still cannot acquire PWIN/capacity.
        assert all(o['pwin']['score'] is None and o['delivery_feasibility']['score'] is None for o in decisions['opportunities'])
        assert all(not r.get('real_person_ids') for r in source['interactions'])
    engine.dispose()
