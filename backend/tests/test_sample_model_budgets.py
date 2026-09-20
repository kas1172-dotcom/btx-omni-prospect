import json

from btx_omni.modules.assistant.commercial_tools import CommercialToolSession
from btx_omni.providers.sample.enhancement import enhance_environment
from btx_omni.providers.sample.environment import build_sample_environment


class Reader:
    def __init__(self, selections):
        self.selections = iter(selections)

    def choose_canonical_read(self, request):
        return next(self.selections, {'done': True})


def test_rich_fixtures_reach_model_without_exceeding_evidence_budget():
    sample = enhance_environment(build_sample_environment())
    for aid in ('boeing', 'demo-fictional-watch', 'demo-fictional-risk', 'demo-regional-defense'):
        for tool in ('read_history', 'read_decisions'):
            receipt = CommercialToolSession(sample, aid).run(Reader([{'tool': tool, 'arguments': {}}]), 'Explain the evidenced scenario')
            assert receipt['stop_reason'] == 'MODEL_DONE', (aid, tool, receipt['stop_reason'])
            assert len(receipt['reads']) == 1
            assert receipt['steps'][0]['result_characters'] <= 24000
    session = CommercialToolSession(sample, 'demo-fictional-watch')
    decisions = session.read('read_decisions', {})
    first = decisions['opportunities'][0]['pwin']
    receipt = session.run(Reader([{'tool': 'read_decisions', 'arguments': {}},
        {'tool': 'read_decision', 'arguments': {'family': 'pwin', 'subject_id': first['subject_id']}}]), 'Explain this PWIN calculation')
    assert receipt['stop_reason'] == 'MODEL_DONE' and len(receipt['reads']) == 2
    assert receipt['reads'][1]['result']['factors'] == first['factors']
    assert receipt['reads'][0]['result']['detail_policy']
    example = session.run(Reader([{'tool': 'read_history', 'arguments': {}},
        {'tool': 'read_rubric_example', 'arguments': {'example_id': 'award_9_days'}}]), 'Explain the illustrative confidence total')
    assert example['stop_reason'] == 'MODEL_DONE' and len(example['reads']) == 2
    assert str(example['reads'][1]['result']['receipt']['assessment']['score']) == '86.25'
    assert len(json.dumps(example['reads'], default=str)) <= 48000
