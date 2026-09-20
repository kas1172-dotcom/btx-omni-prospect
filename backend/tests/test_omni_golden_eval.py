import pytest
from omni_eval_support import CASES, check_case, environment, run_case


@pytest.fixture(scope='module')
def golden_environment():
    return environment()


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['id'])
def test_golden_chat_contract(case, golden_environment):
    answer, provider = run_case(case, golden_environment)
    assert not (failures := check_case(case, answer, provider)), failures


def test_eval_size_and_required_categories():
    assert len(CASES) >= 60
    assert {'refusal', 'not_found', 'permission', 'injection', 'web', 'mixed', 'orders', 'scores', 'off_topic', 'degraded'} <= {c['category'] for c in CASES}
