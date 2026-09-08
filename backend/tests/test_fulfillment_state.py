from datetime import date

from test_commercial_persistence import importer_package

from btx_omni.modules.commercial.lifecycle import fulfillment_state


def test_partial_shipment_acceptance_and_proposal_remain_distinct():
    ledger = importer_package()["accounts"][0]
    ledger["fulfillment_plans"] = [{"plan_id": "plan", "order_line_id": "ol", "buyer_accepted": False, "proposed_ship_date": "2026-09-12"}]
    result = fulfillment_state(ledger, canonical_account_id="honeywell", revision="r1")
    line = result["lines"][0]
    assert line["remaining_quantity"] == 4
    assert line["shipped_unaccepted_quantity"] == 2
    assert line['shipped_unaccepted_value_minor'] == 200
    assert sum(row['unaccepted_value_minor'] for row in line['shipments']) == 200
    assert line["recognized_revenue_minor"] == 400
    assert line["committed_date"] == "2026-08-20"
    assert line["execution_status"] == "BLOCKED"
    assert {c["type"] for c in result["constraints"]} == {"MISSED_COMMITMENT", "UNACCEPTED_RECOVERY_PROPOSAL"}


def test_future_shipments_do_not_resolve_historical_commitment():
    ledger = importer_package()["accounts"][0]
    ledger["shipments"].append({"shipment_id": "future", "order_line_id": "ol", "quantity": 4, "shipped_date": "2026-09-02"})
    result = fulfillment_state(ledger, canonical_account_id="honeywell", revision="r1")
    assert result["lines"][0]["remaining_quantity"] == 4
    assert "future" not in result["lines"][0]["evidence_ids"]


def test_cancellation_uses_canonical_date_and_does_not_create_revenue():
    ledger = importer_package()["accounts"][0]
    ledger["cancellations"] = [{"cancellation_id": "cancel", "order_line_id": "ol", "date": "2026-08-21", "quantity": 4, "value_minor": 400}]
    line = fulfillment_state(ledger, canonical_account_id="honeywell", revision="r1")["lines"][0]
    assert line["remaining_quantity"] == 0
    assert line["cancelled_quantity"] == 4
    assert line["recognized_revenue_minor"] == 400
    assert not line["overdue"]


def test_historical_query_excludes_future_orders_shipments_and_undated_recovery_plans():
    ledger = importer_package()['accounts'][0]
    ledger['fulfillment_plans'] = [{'plan_id': 'undated', 'order_line_id': 'ol', 'buyer_accepted': False, 'proposed_ship_date': '2026-09-12'}]
    before_order = fulfillment_state(ledger, canonical_account_id='honeywell', revision='r', as_of=date(2026, 8, 1))
    assert before_order['lines'] == before_order['constraints'] == []
    early = fulfillment_state(ledger, canonical_account_id='honeywell', revision='r', as_of=date(2026, 8, 5))
    assert early['as_of'] == '2026-08-05'
    assert early['lines'][0]['shipped_quantity'] == 0
    assert early['lines'][0]['remaining_quantity'] == 10
    assert early['constraints'] == []
    assert early['temporal_limits']['undated_plans_excluded_from_historical_query'] == 1
    current = fulfillment_state(ledger, canonical_account_id='honeywell', revision='r', as_of=date(2026, 9, 8))
    assert current['as_of'] == ledger['as_of']
    assert {c['type'] for c in current['constraints']} == {'MISSED_COMMITMENT', 'UNACCEPTED_RECOVERY_PROPOSAL'}
