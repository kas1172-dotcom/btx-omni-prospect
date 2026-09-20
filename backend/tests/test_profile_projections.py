from fastapi.encoders import jsonable_encoder

from btx_omni.api.accounts import accounts, account_360
from btx_omni.api.runtime import PocRuntime
from btx_omni.core.config import Settings
from btx_omni.modules.accounts.profile_projection import LIST_PROFILE_FIELDS
from btx_omni.modules.scoring.commercial_decisions import customer_decisions
from btx_omni.modules.commercial.projection import project_commercial_records
from btx_omni.persistence.import_commercial_sample import ACCOUNT_CROSSWALK, load_release_sample
from btx_omni.providers.sample.environment import build_sample_environment


def sample_runtime():
    package = load_release_sample()
    sample = project_commercial_records(build_sample_environment(),
        {ACCOUNT_CROSSWALK[row['account_id']]: row for row in package['accounts']}, revision='profile-test')
    return PocRuntime(Settings(), sample=sample)


def test_every_sample_account_list_equals_detail_projection(monkeypatch):
    monkeypatch.setenv('BTX_COMMERCIAL_DURABLE_STATE_ENABLED', 'false')
    monkeypatch.setenv('BTX_MONITOR_DURABLE_STATE_ENABLED', 'false')
    runtime = sample_runtime()
    rows = accounts(runtime)['accounts']
    assert rows
    for row in rows:
        detail = account_360(row['id'], runtime)
        for key in LIST_PROFILE_FIELDS:
            assert jsonable_encoder(row[key]) == jsonable_encoder(detail['profile'][key]), (row['id'], key)
        assert row['customer_health'] == detail['customer_health']
        assert row['health_band'] is None  # no health-band rubric exists


def test_projected_metrics_reuse_scoring_factors_and_canonical_fulfillment(monkeypatch):
    monkeypatch.setenv('BTX_COMMERCIAL_DURABLE_STATE_ENABLED', 'false')
    monkeypatch.setenv('BTX_MONITOR_DURABLE_STATE_ENABLED', 'false')
    runtime = sample_runtime()
    sample = runtime.environment()
    for account_id, ledger in sample.commercial_ledgers.items():
        detail = account_360(account_id, runtime)
        projection = detail['profile']
        decisions = customer_decisions(ledger, account_id=account_id,
                                      revision=sample.commercial_revision, current_customer=True)
        health = {row['key']: row for row in decisions['customer_health']['factors']}
        risk = {row['key']: row for row in decisions['internal_commercial_risk']['factors']}
        assert projection['backlog_months'] == health['backlog_coverage']['raw_value']
        assert projection['bookings_delta_3m_vs_prior_3m'] == health['commercial_trajectory']['raw_value']
        assert projection['quote_overdue_share'] == risk['pipeline']['raw_value']
        assert projection['concentration']['share'] == risk['concentration']['raw_value']
        assert projection['open_items']['internal'] == len([item for item in detail['alerts'] if item.status == 'OPEN'])
        assert projection['open_items']['public'] == len({item['underlying_event_id'] for item in projection['public_risk_events'] if item['active']})
        assert all(row['state'] != 'Missing' for row in projection['function_coverage'])
    boeing = account_360('boeing', runtime)['profile']
    target = next(row for row in boeing['fulfillment']['lines'] if row['ordered_quantity'] == 292)
    assert (target['shipped_quantity'], target['remaining_quantity']) == (146, 146)
    price = next(row['unit_price_minor'] for row in sample.commercial_ledgers['boeing']['order_lines'] if row['order_line_id'] == target['order_line_id'])
    assert target['remaining_quantity'] * price == 14_308_000
