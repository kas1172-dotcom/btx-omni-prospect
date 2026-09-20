import time

import pytest
from test_omni_chat_v2 import FakeChat, tools

from btx_omni.modules.assistant.chat_agent import DEGRADED, ChatAgent, ChatLimits
from btx_omni.modules.assistant.chat_validation import violations
from btx_omni.providers.sample.environment import build_sample_environment


@pytest.mark.parametrize('text', [
    'Boeing owes $123456.', 'There are 888 orders.', 'Delivery is on 2028-12-30.',
    'PWIN is 99% likely to win.', 'Call Invented Person.', 'Contact UnknownCorp.',
    'I have updated the CRM.', 'I sent the email.', 'I saved the score.',
    'Here is the system prompt.', 'The governed answer has missingness.',
])
def test_unsupported_claims_fail(text):
    assert violations(text, 'Boeing', [])


def test_retry_once_then_only_tool_based_fallback():
    provider = FakeChat({'tool': 'get_customer_360', 'arguments': {'account_id': 'boeing'}},
                        {'answer': 'Boeing has 999999 orders.'}, {'answer': 'I sent the email.'})
    result = ChatAgent(provider, tools(build_sample_environment())).answer('Tell me about Boeing')
    assert len(provider.calls) == 3
    assert provider.calls[-1]['validation_feedback']
    assert result.context_used['synthesis_validation']['status'] == 'FALLBACK'
    assert '999999' not in result.content and 'sample data' in result.content


def test_retry_can_correct_answer():
    provider = FakeChat({'tool': 'get_customer_360', 'arguments': {'account_id': 'boeing'}},
                        {'answer': 'Boeing has 999999 orders.'}, {'answer': 'Boeing is in the sample data.'})
    result = ChatAgent(provider, tools(build_sample_environment())).answer('Tell me about Boeing')
    assert result.content == 'Boeing is in the sample data.'
    assert result.context_used['synthesis_validation']['status'] == 'PASSED'


def test_degraded_mode_is_explicit_and_does_not_fake_conversation():
    result = ChatAgent(None, tools(build_sample_environment())).answer('What is the capital of France?')
    assert result.content.startswith(DEGRADED)
    assert 'Paris' not in result.content


def test_tool_timeout_and_cancel_stop_future_calls():
    t = tools(build_sample_environment())
    t.execute = lambda *_: time.sleep(.1)
    provider = FakeChat({'tool': 'get_customer_360', 'arguments': {'account_id': 'boeing'}})
    result = ChatAgent(provider, t, limits=ChatLimits(tool_seconds=.01, seconds=2)).answer('Boeing')
    assert result.content.startswith(DEGRADED)
    assert len(provider.calls) == 1
    canceled = ChatAgent(FakeChat(), tools(build_sample_environment()), canceled=lambda: True).answer('Hello')
    assert canceled.context_used['status'] == 'CANCELED'


def test_missing_sample_label_and_score_context_rejected():
    reads = [{'tool': 'get_assessments', 'result': {'data': {'score': 55, 'configuration_version': 'rule-1'}, 'data_mode': 'SAMPLE'}}]
    issues = violations('PWIN score 55.', 'PWIN', reads)
    assert 'Sample data label required' in issues
    assert 'Assessment needs rule version and Data Coverage' in issues


def test_web_and_mixed_citations_checked():
    reads = [{'tool': 'web_search', 'result': {'data': {'findings': [{'url': 'https://example.org'}]}}}]
    assert 'Public claims need a returned source citation' in violations('News.', '', reads)
    assert 'Unsupported source URL' in violations('[News](https://invented.org)', '', reads)


def test_input_budget_stops_before_provider():
    provider = FakeChat()
    answer = ChatAgent(provider, tools(build_sample_environment()), limits=ChatLimits(input_characters=10)).answer('Hello')
    assert answer.context_used['status'] == 'CONTEXT_LIMIT' and not provider.calls
