"""Final UI/model-facing assertions: no live services or manual seed entry."""
from decimal import Decimal

import pytest
from fastapi import Response
from sqlalchemy import create_engine

from btx_omni.api.account_planning import planning
from btx_omni.api.accounts import account_360
from btx_omni.api.commercial import commercial_evidence
from btx_omni.api.itineraries import SaveItinerary, current_itinerary, save_itinerary
from btx_omni.api.markets import markets
from btx_omni.api.runtime import PocRuntime
from btx_omni.core.config import Settings
from btx_omni.domain.work import Principal, PrincipalRole
from btx_omni.modules.assistant.commercial_tools import CommercialToolSession
from btx_omni.modules.commercial.ledger import validate_commercial_account
from btx_omni.modules.scoring.families import overall_customer_risk
from btx_omni.persistence.models import metadata

ACTOR = Principal('demo-role:reviewer', 'SAMPLE reviewer role', PrincipalRole.MANAGER)


@pytest.fixture
def runtime(tmp_path):
    url = f'sqlite:///{tmp_path / "journeys.db"}'
    engine = create_engine(url)
    metadata.create_all(engine)
    engine.dispose()
    return PocRuntime(Settings(_env_file=None, database_url=url, sample_enhancement_enabled=True, monitor_mode='disabled'))


def test_j2_j3_api_defaults_and_model_context_are_available_without_writes(runtime):
    result = planning(runtime, ACTOR)
    assert len(result['strategic_partnerships']) == 2
    assert len(result['business_unit_history'][0]['sister_business_unit_sites']) == 3
    assert not runtime.account_planning.view(ACTOR.user_id)['partnership_records']
    context = CommercialToolSession(runtime.environment(), 'demo-regional-defense').read('read_history', {})
    assert context['case_briefing']['planning_context']['forecast'] is None
    result = markets(runtime=runtime)
    assert result['sample_coverage']['region_counts'] == {'AZ': 3}
    assert result['curated_public_context'][0]['event_type'] == 'DRAFT_GUIDANCE'
    medical = next(r for r in result['series'] if r['metadata']['native_code'] == 'N3391')
    assert medical['status'] == 'AVAILABLE'


def test_j1_prefilled_itinerary_has_no_contact_or_meeting_or_travel_inventions(runtime):
    draft = current_itinerary(runtime, ACTOR)['itinerary']
    assert len(draft['stops']) == 9 and draft['origin_latitude']
    assert draft['version'] is None and runtime.itineraries.get(ACTOR.user_id) is None
    for stop in draft['stops']:
        assert not stop['contact_name'] and stop['meeting_status'] == 'NOT_REQUESTED'
        assert stop['travel_duration_minutes'] is stop['travel_distance_miles'] is None
    # Persisting a reviewed default uses the normal optimistic-version API.
    from btx_omni.api.itineraries import ItineraryStopInput
    stops = [{k: v for k, v in row.items() if k in ItineraryStopInput.model_fields} for row in draft['stops']]
    saved = save_itinerary(SaveItinerary(title=draft['title'], origin_label=draft['origin_label'],
        origin_latitude=draft['origin_latitude'], origin_longitude=draft['origin_longitude'], stops=stops,
        idempotency_key='demo-itinerary-review'), runtime, ACTOR)
    assert saved['version'] == 1
    assert current_itinerary(runtime, ACTOR)['itinerary']['version'] == 1


def test_prospect_fit_stale_history_keeps_evidence_and_no_point_score(runtime):
    from btx_omni.modules.scoring.prospect_fit import (
        prospect_fit_payload,
        prospect_fit_projection,
    )
    account = next(a for a in runtime.environment().accounts if a.id == 'demo-regional-aero')
    result = prospect_fit_payload(prospect_fit_projection(account, applicable=True, as_of='2027-04-01'))
    assert result['score'] is None
    assert all(f['evidence_state'] == 'STALE' and f['evidence_ids'] for f in result['factors'])
    assert result['rule_version'] == 'BTX_SCORING_RUBRIC_V2.0'


def test_j5_j7_visible_profile_contains_public_and_synthetic_context(runtime):
    profile = account_360('boeing', runtime)
    assert profile['account_attractiveness']['rule_version'] == 'BTX_SCORING_RUBRIC_V2.0'
    context = profile['sample_context']
    assert context['synthetic'] and context['data_mode'] == 'SAMPLE'
    assert context['expansion_context']
    assert profile['commercial_briefing']['fulfillment']['remaining_quantity'] == 146


def test_live_customer_risk_wrapper_is_62_not_only_a_standalone_vector(runtime):
    result = commercial_evidence('demo-fictional-risk', 'decisions', Response(), actor=ACTOR, runtime=runtime)
    assert result['internal_commercial_risk']['score'] == Decimal('52.50')
    assert result['public_risk_rollup']['score'] == Decimal('76.25')
    assert result['overall_customer_risk']['score'] == Decimal('62.00')
    assert result['overall_customer_risk']['convergence_uplift'] == 0
    assert result['overall_customer_risk']['applicable_floors'] == []
    assert result['action_priorities'][0]['decision']['rule_version'] == 'BTX_SCORING_RUBRIC_V2.0'
    from btx_omni.monitor.briefs import signal_briefs_for_monitor
    model = CommercialToolSession(runtime.environment(), 'demo-fictional-risk',
        signal_briefs=signal_briefs_for_monitor(runtime.monitor)).read('read_decisions', {})
    assert model['overall_customer_risk']['score'] == result['overall_customer_risk']['score']
    assert model['public_risk_events'][0]['synthetic'] is True
    critical = commercial_evidence('demo-fictional-critical', 'decisions', Response(), actor=ACTOR, runtime=runtime)
    assert critical['overall_customer_risk']['execution_blocked'] is True
    assert critical['overall_customer_risk']['score_range']['low'] >= 85


def test_all_authored_ledgers_reconcile_and_commercial_rows_are_labeled(runtime):
    assert next(a for a in runtime.environment().accounts if a.id == 'demo-fictional-watch').relationship.value == 'CURRENT_CUSTOMER'
    for account in runtime.environment().commercial_ledgers.values():
        validate_commercial_account(account)
        assert account['synthetic'] is True and account['data_mode'] == 'SAMPLE'
        for key in ('quotes', 'quote_revisions', 'quote_lines', 'orders', 'order_lines', 'shipments',
                    'revenue_events', 'invoices', 'payments', 'service_events', 'interactions', 'actions'):
            for row in account[key]:
                assert row['synthetic'] is True and row['data_mode'] == 'SAMPLE'
                assert not row.get('email') and not row.get('real_person_ids')


def test_runtime_clock_override_and_durable_import_separation(runtime):
    runtime.settings.demo_as_of_date = '2026-10-01'
    assert runtime.observed_at().date().isoformat() == '2026-10-01'
    with pytest.raises(ValueError, match='read-only fixture view'):
        PocRuntime(Settings(_env_file=None, database_url=runtime.settings.database_url,
                            sample_enhancement_enabled=True, commercial_durable_state_enabled=True))


def test_unknown_customer_risk_range_retains_weights_and_possible_floor():
    result = overall_customer_risk(current_customer=True, internal_score=Decimal('52.5'),
                                   public_score=None, public_confirmed=False)
    assert result['score'] is None
    # Upper end includes the public-critical floor at the unknown factor's maximum.
    assert result['score_range'] == {'low': Decimal('31.50'), 'high': Decimal(75)}
    assert result['calculation_trace']['internal_contribution'] == Decimal('31.50')
    assert result['calculation_trace']['public_contribution'] is None
