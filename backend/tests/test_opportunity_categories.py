"""Read-only category projection; deliberately independent of imported sample data."""
from types import SimpleNamespace

import pytest

from btx_omni.modules.commercial import opportunities


@pytest.fixture
def sample(monkeypatch):
    monkeypatch.setattr(opportunities, 'opportunity_decisions', lambda *args, **kwargs: [
        {'opportunity_id': 'opp-1', 'component_id': 'part-1', 'score': 73}])
    return SimpleNamespace(
        accounts=[SimpleNamespace(id='account-1', legal_name='Acme',
                                  relationship=SimpleNamespace(value='CURRENT_CUSTOMER'),
                                  industries=('Space', 'Defense'), business_units=('not-an-owner',))],
        commercial_ledgers={'account-1': {'opportunities': [{'opportunity_id': 'opp-1'}], 'as_of': '2026-09-20'}},
        commercial_revision='revision-1', btx_facilities=[], crm_deals=[])


def test_market_alphabetical_and_missing_owner_is_null(sample):
    row = opportunities.account_opportunities(sample, 'account-1')[0]
    assert row['market'] == 'Defense'
    assert row['bu'] is None
    assert row['score'] == 73  # Existing decision fields remain unchanged.


@pytest.mark.parametrize('flag', ['primary', 'is_primary'])
def test_explicit_primary_market_takes_precedence(sample, flag):
    sample.commercial_ledgers['account-1']['market_assignments'] = [
        {'market': 'Defense'}, {'market': 'Space', flag: True}]
    assert opportunities.account_opportunities(sample, 'account-1')[0]['market'] == 'Space'


def test_missing_categories_are_null(sample):
    sample.accounts[0].industries = ()
    row = opportunities.account_opportunities(sample, 'account-1')[0]
    assert row['market'] is None
    assert row['bu'] is None


def test_bu_uses_only_matching_account_and_opportunity_owner(sample):
    sample.crm_deals = [SimpleNamespace(id='opp-1', account_id='account-1', business_unit='chandler'),
                        SimpleNamespace(id='opp-1', account_id='other', business_unit='wrong')]
    assert opportunities.account_opportunities(sample, 'account-1')[0]['bu'] == 'chandler'


def test_absent_ledger_still_returns_no_rows(sample):
    assert opportunities.account_opportunities(sample, 'missing') == []
