from copy import deepcopy
from decimal import Decimal

from test_commercial_persistence import importer_package

from btx_omni.modules.scoring.commercial_decisions import customer_decisions


def factor(result, family, key):
    return next(f for f in result[family]["factors"] if f["key"] == key)


def test_known_payment_friction_is_not_unknown_quality_or_annual_growth():
    account = importer_package()["accounts"][0]
    account["invoices"][0]["due_date"] = "2026-08-15"
    original = deepcopy(account)
    result = customer_decisions(account, account_id="honeywell", revision="test", current_customer=True)
    assert factor(result, "internal_commercial_risk", "friction")["points"] == 100
    assert factor(result, "customer_health", "friction")["points"] == 0
    missing = result["internal_commercial_risk"]["data_coverage"]["missing_fields"]
    assert "commercial_momentum.prior_ttm_revenue" in missing
    assert "friction.quality_exposure" in missing and "friction.credit_limit" in missing
    assert result["customer_health"]["score"] is None
    assert account == original


def test_unknown_due_date_and_zero_open_backlog_do_not_invent_health():
    account = importer_package()["accounts"][0]
    account["shipments"][0]["quantity"] = 10  # a read-model test, not an importer fixture
    result = customer_decisions(account, account_id="honeywell", revision="test", current_customer=True)
    assert factor(result, "customer_health", "backlog")["points"] is None
    assert factor(result, "customer_health", "friction")["points"] is None


def test_role_interaction_does_not_create_verified_person_coverage_or_prospect_health():
    account = importer_package()["accounts"][0]
    account["interactions"] = [{"interaction_id": "role-note", "date": "2026-08-30", "real_person_ids": []}]
    result = customer_decisions(account, account_id="honeywell", revision="test", current_customer=False)
    assert result["customer_health"]["status"] == "INELIGIBLE"
    engagement = factor(result, "customer_health", "engagement")
    assert engagement["points"] == Decimal(100)
    assert engagement["observed_fields"] == ("dated_interaction",)
    assert "verified_functional_person_coverage" in engagement["required_fields"]


def test_action_review_exposure_does_not_create_work_or_recognized_revenue():
    account = importer_package()["accounts"][0]
    account["actions"] = [{"action_id": "act", "title": "Review the remaining units", "due_date": "2026-09-09", "evidence_record_ids": ["ol"]}]
    result = customer_decisions(account, account_id="honeywell", revision="test", current_customer=True)
    action = result["action_priorities"][0]
    assert action["decision"]["score"] == 85
    assert action["work_status"] == "SOURCE_CASE_FOLLOW_UP_NOT_CREATED_WORK"
    assert action["linked_work_ids"] == []
    assert account["ttm_summary"]["revenue_minor"] == 400
