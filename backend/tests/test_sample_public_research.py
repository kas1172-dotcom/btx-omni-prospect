from btx_omni.providers.sample.public_research import medical_regulatory_context


def test_fda_draft_stays_aggregate_and_expires_without_invented_effective_date():
    current = medical_regulatory_context()
    assert current['evidence_state'] == 'CURRENT'
    assert current['effective_date'] is None and not current['account_ids']
    assert current['need_gate'] == 'UNKNOWN' and current['risk_score'] is None
    assert current['record_id'] and current['publisher'] and current['source_url']
    stale = medical_regulatory_context(anchor='2026-10-18')
    assert stale['evidence_state'] == 'STALE'
    assert stale['event_date'] == current['event_date']
