from test_commercial_ledger import small_ledger

from btx_omni.modules.commercial.evidence import resolve_commercial_evidence


def test_evidence_resolution_preserves_record_and_does_not_search_other_accounts():
    ledger = small_ledger()
    found = resolve_commercial_evidence(ledger, "v")
    assert found["record"] == ledger["revenue_events"][0]
    assert found["truth_class"] == "POC_SCENARIO_RECORD"
    assert resolve_commercial_evidence(ledger, "another-account-revenue") is None


def test_public_metadata_must_be_referenced_in_the_selected_account(monkeypatch):
    from btx_omni.modules.commercial import evidence

    monkeypatch.setattr(evidence, "public_sources", lambda: {"inside": {"url": "https://example.test/inside"}, "outside": {"url": "https://example.test/outside"}})
    ledger = small_ledger()
    ledger["programs"][0]["source_ids"] = ["inside"]
    assert resolve_commercial_evidence(ledger, "inside")["kind"] == "public_source"
    assert resolve_commercial_evidence(ledger, "outside") is None
