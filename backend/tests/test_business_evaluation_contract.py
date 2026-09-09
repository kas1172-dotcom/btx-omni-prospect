import json
from decimal import Decimal
from pathlib import Path

from btx_omni.persistence.import_commercial_sample import (
    ACCOUNT_CROSSWALK,
    INPUT_SHA256,
    load_release_sample,
)


def test_frozen_business_cases_cover_cohort_and_keep_semantic_gates_explicit():
    suite = json.loads((Path(__file__).parent / 'fixtures/omni_business_cases_v2.json').read_text())
    assert suite['source_sha256'] == INPUT_SHA256
    assert len(suite['development']) == 24 and len(suite['held_out']) == 12
    cases = suite['development'] + suite['held_out']
    assert len({case['id'] for case in cases}) == 36
    assert {case['account_id'] for case in suite['development']} == set(ACCOUNT_CROSSWALK.values())
    assert {case['account_id'] for case in suite['held_out']} == set(ACCOUNT_CROSSWALK.values())
    assert suite['grading']['critical_errors_allowed'] == 0
    assert suite['grading']['critical_live_trials'] == 3
    assert set(suite['grading']['required_each_case']) == set(suite['grading']['dimensions'])
    records = {ACCOUNT_CROSSWALK[item['account_id']]: item for item in load_release_sample()['accounts']}
    for case in cases:
        assert case['facts'] and case['action'] and 20 < len(case['question']) <= 700
        for fact in case['facts']:
            if fact.startswith('TTM revenue USD '):
                actual = int(Decimal(fact.removeprefix('TTM revenue USD ').replace(',', '')) * 100)
                assert actual == records[case['account_id']]['ttm_summary']['revenue_minor']
    eaton = records['eaton']
    accepted_ids = {item['shipment_id'] for item in eaton['acceptances']}
    unaccepted = {item['shipment_id']: item for item in eaton['shipments'] if item['shipment_id'] not in accepted_ids}
    assert sum(item['value_minor'] for item in unaccepted.values()) == 23911800
    assert unaccepted['SHP2-EATON-13-1-1']['value_minor'] == 19536000
    assert unaccepted['SHP2-EATON-13-2-1']['value_minor'] == 4375800
    case = next(item for item in suite['development'] if item['id'] == 'DEV-10-R2')
    assert any('USD 239,118.00' in fact for fact in case['facts'])
    assert all('USD 2,391.18' not in fact for fact in case['facts'])
