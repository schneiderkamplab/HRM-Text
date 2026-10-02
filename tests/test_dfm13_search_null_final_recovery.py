from copy import deepcopy
from scripts import dfm13_search_null_final_recovery as recovery


def test_null_recovery_retains_user_and_observations(monkeypatch, tmp_path):
    monkeypatch.setattr(recovery.previous, 'generation_request', deepcopy)
    class Session:
        def post(self, *args, **kwargs):
            return kwargs['json']
    request = dict(messages=[dict(role='system', content='historical context'),
        dict(role='user', content='question'), dict(role='tool', content='cached observation')],
        max_tokens=1536, tool_choice='none')
    saved = deepcopy(request)
    result = recovery.FinalSession(Session(), tmp_path).post('endpoint', json=request)
    assert request == saved
    assert result['messages'][1:] == saved['messages'][1:]
    assert result['max_tokens'] == 1536
    assert result['tool_choice'] == 'none'
    assert 'ordinary final answer text' in result['messages'][0]['content']
    assert (tmp_path / 'actual-request.json').exists()
