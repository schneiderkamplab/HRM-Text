import json
from scripts import dfm13_search_plain_factual_control as control


def test_plain_critique_blind_to_expected_and_prior_model_opinion():
    payload = dict(requirements={'original_timestamp': '2025-05-05'}, answer='original answer',
                   pages={'https://example.org': 'full evidence'}, verified_checks=[],
                   expected='reject', untrusted_critic={'claim': 'prior opinion'})
    messages = control.critique_messages(payload)
    sent = json.loads(messages[-1]['content'])
    assert 'expected' not in sent and 'untrusted_critic' not in sent
    assert sent['answer'] == payload['answer'] and sent['pages'] == payload['pages']
    assert 'plain-text' in messages[0]['content']
