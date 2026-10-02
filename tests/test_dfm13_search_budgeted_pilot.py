from copy import deepcopy
import json
import pytest
from scripts import dfm13_search_budgeted_pilot as pilot


def prefix():
    return [dict(role='user', content='Original date and request unchanged'),
            dict(role='assistant', content='', tool_calls=[dict(id='real-call', type='function',
                function=dict(name='search', arguments={'query': 'benchmark'}))])]


def test_complete_paragraphs_exact_offsets_not_character_truncation():
    body = 'A complete benchmark paragraph with substantive source content.\n\nAnother complete paragraph about this benchmark and its setting.'
    chunks = pilot.paragraphs(dict(data=[dict(url='https://example.org', content=body)]), ['https://example.org'])
    assert len(chunks) == 2
    assert all(body[c['start']:c['end']] == c['text'] for c in chunks)
    assert all(c['text'].endswith('.') for c in chunks)


def test_evidence_fits_before_generation_and_keeps_real_call():
    original = prefix(); saved = deepcopy(original)
    chunks = [dict(url='https://example.org', title='benchmark', start=0, end=70,
                   text='Complete benchmark evidence about the query. ' * 2)]
    count = lambda messages: len(json.dumps(messages))
    selected = pilot.select_evidence(chunks, 'benchmark', original, count, limit=1500, reserve=400)
    history = pilot.history_with_observation(original, selected, 'benchmark')
    assert count(history) + 400 <= 1500
    assert original == saved and history[:-1] == original
    assert history[-1]['tool_call_id'] == 'real-call'
    assert json.loads(history[-1]['content'])['results'][0]['body'] == chunks[0]['text']


def test_required_context_cannot_be_silently_dropped():
    chunks = [dict(url='https://example.org', title='benchmark', start=0, end=80,
                   text='REQUIRED benchmark setting with enough substantive context to select.')]
    with pytest.raises(ValueError, match='does not fit'):
        pilot.select_evidence(chunks, 'benchmark', prefix(), lambda _: 100, required=['REQUIRED'], limit=120, reserve=30)


def test_generation_transport_caps_output_and_saves_actual_request(tmp_path):
    class Session:
        def post(self, *args, **kwargs):
            return kwargs['json']
    wrapper = pilot.GenerationSession(Session(), tmp_path)
    request = dict(max_tokens=2048, tools=['schema'], tool_choice='auto')
    actual = wrapper.post('endpoint', json=request)
    assert actual['max_tokens'] == 512 and actual['tool_choice'] == 'none'
    assert request['max_tokens'] == 2048
    assert json.loads((tmp_path / 'actual-request.json').read_text()) == actual
