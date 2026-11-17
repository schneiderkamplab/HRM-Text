import pytest

from scripts.dfm16_mimir_judge import MimirContent, MimirLanguage, MimirProbe, MODEL_ID
from scripts.dfm16_mimir_probe_cases import cases


def test_separate_criteria_and_no_label_leak(tmp_path):
    row = dict(language='en', task='qa', messages=[], expected='reject')
    language = MimirLanguage(tmp_path, tmp_path/'language', 'http://localhost:1/v1')
    content = MimirContent(tmp_path, tmp_path/'content', 'http://localhost:1/v1')
    language.model = content.model = MODEL_ID
    a, b = language.prepare(row), content.prepare(row)
    assert 'linguistic quality' in a['messages'][0]['content']
    assert 'Ignore grammar' in b['messages'][0]['content']
    assert 'expected' not in str(a) and 'expected' not in str(b)
    assert a['chat_template_kwargs'] == b['chat_template_kwargs'] == {'enable_thinking': False}


def test_context_overflow_is_detected_without_truncation(tmp_path):
    adapter = MimirContent(tmp_path, tmp_path/'content', 'http://localhost:1/v1')
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            assert kwargs['enable_thinking'] is False
            assert 'truncation' not in kwargs
            return [1]*4090
    adapter.tokenizer = Tokenizer()
    assert not adapter.fits(dict(language='en', task='qa', messages=[]))


def test_probe_strict_labels():
    def response(text):
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': text}}]}
    assert MimirProbe.parse_review(response('nej'))['decision'] == 'reject'
    assert MimirProbe.parse_review(response('yes'))['decision'] == 'accept'
    with pytest.raises(ValueError):
        MimirProbe.parse_review(response('yes, but actually no'))
    examples = list(cases())
    assert len(examples) == 24
    assert sum(r['expected'] == 'accept' for r in examples) == 12


def test_text_units_exclude_chat_and_keep_story_intact():
    from scripts.dfm16_mimir_text_units import text_units
    story = 'First paragraph.\n\nSecond paragraph.'
    row = dict(id='x', language='en', task='revision', comparison_cohort='v3',
        messages=[dict(role='user', content='secret instruction'),
                  dict(role='assistant', content=story)])
    units = list(text_units([row]))
    assert len(units) == 2
    assert {u['aspect'] for u in units} == {'language', 'coherence'}
    assert all(u['text'] == story and story in u['prompt'] for u in units)
    assert all('secret instruction' not in u['prompt'] for u in units)
    assert len({u['id'] for u in units}) == 2
