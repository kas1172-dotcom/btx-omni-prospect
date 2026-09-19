from copy import deepcopy

from test_commercial_persistence import importer_package

from btx_omni.modules.scoring.commercial_decisions import customer_decisions


def factor(result, family, key):
    return next(f for f in result[family]["factors"] if f["key"] == key)


def test_known_payment_friction_is_not_unknown_quality_or_annual_growth():
    account = importer_package()["accounts"][0]
    account["invoices"][0]["due_date"] = "2026-08-15"
    original = deepcopy(account)
    result = customer_decisions(account, account_id="honeywell", revision="test", current_customer=True)
    # Invoice value alone cannot establish the rubric's worst service/payment condition.
    assert factor(result, "internal_commercial_risk", "friction")["points"] is None
    assert factor(result, "customer_health", "attached_risk_history")["points"] is None
    assert 'friction' not in {f['key'] for f in result['customer_health']['factors']}
    missing = result["internal_commercial_risk"]["data_coverage"]["missing_fields"]
    assert "commercial_momentum.commercial_momentum" in missing
    assert "friction.friction" in missing
    assert result["customer_health"]["score"] is None
    assert account == original


def test_unknown_due_date_and_zero_open_backlog_do_not_invent_health():
    account = importer_package()["accounts"][0]
    account["shipments"][0]["quantity"] = 10  # a read-model test, not an importer fixture
    result = customer_decisions(account, account_id="honeywell", revision="test", current_customer=True)
    assert factor(result, "customer_health", "backlog_coverage")["points"] is None
    assert factor(result, "customer_health", "attached_risk_history")["points"] is None


def test_role_interaction_does_not_create_verified_person_coverage_or_prospect_health():
    account = importer_package()["accounts"][0]
    account["interactions"] = [{"interaction_id": "role-note", "date": "2026-08-30", "real_person_ids": []}]
    result = customer_decisions(account, account_id="honeywell", revision="test", current_customer=False)
    assert result["customer_health"]["status"] == "INELIGIBLE"
    engagement = factor(result, "customer_health", "relationship_coverage")
    assert engagement["points"] is None
    assert engagement["observed_fields"] == ()
    assert factor(result, "customer_health", "engagement_cadence")["points"] is None


def test_action_review_exposure_does_not_create_work_or_recognized_revenue():
    account = importer_package()["accounts"][0]
    account["actions"] = [{"action_id": "act", "title": "Review the remaining units", "due_date": "2026-09-09", "evidence_record_ids": ["ol"]}]
    result = customer_decisions(account, account_id="honeywell", revision="test", current_customer=True)
    action = result["action_priorities"][0]
    # Action Priority is a queue position, never a fabricated blended index.
    assert action["decision"]["score"] is None
    assert 'score_range' not in action['decision']
    assert action['decision']['priority_rank'] == 1
    assert action['decision']['priority_class'] == 3
    assert action["work_status"] == "SOURCE_CASE_FOLLOW_UP_NOT_CREATED_WORK"
    assert action["linked_work_ids"] == []
    assert account["ttm_summary"]["revenue_minor"] == 400


def test_huxwrx_customer_uses_existing_imported_history_without_prospect_overlay():
    from copy import deepcopy

    from btx_omni.modules.commercial.projection import project_commercial_records
    from btx_omni.persistence.import_commercial_sample import load_release_sample
    from btx_omni.providers.sample.environment import build_sample_environment

    ledger = next(a for a in load_release_sample()["accounts"] if a["account_id"] == "ACC-HUXWRX")
    before = deepcopy(ledger)
    environment = project_commercial_records(build_sample_environment(), {"huxwrx": ledger}, revision="classification-correction")
    account = next(a for a in environment.accounts if a.id == "huxwrx")
    assert account.relationship.value == "CURRENT_CUSTOMER"
    assert ledger == before
    assert len(ledger["orders"]) == 30
    assert len(ledger["shipments"]) == 38
    assert ledger["ttm_summary"]["revenue_minor"] == 53728976
    assert not any(p.id == "huxwrx-sample-opportunity" for p in environment.programs)
    assert not any(c.id == "cc-huxwrx-sample-opportunity" for c in environment.component_classes)
