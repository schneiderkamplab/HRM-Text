import pytest

from scripts.multilingual_smoke_latex import TASKS, prose, render


def document():
    return {'responses': [dict(language=lang, task=task, prompt='Prompt\n\nInput & α',
        response='Answer % ї', output_tokens=3, finish_reason='stop',
        judgment={'scores': [3,2,1], 'assessment': 'A specific assessment.'})
        for lang in ('da','el') for task in TASKS]}


def test_pages_and_content():
    tex = render(document())
    assert tex.count('\\clearpage') == 1
    assert tex.count('Evaluation: 3 / 2 / 1') == 6
    assert tex.count(r'Answer \% ї') == 6
    assert tex.count('A specific assessment.') == 6
    assert r'Input \& α' in tex


def test_no_lost_long_loop_text():
    value = '¡' * 500
    assert prose(value).replace(r'\allowbreak{}', '') == value


def test_checkpoint_label_is_not_hardcoded():
    d = document()
    d['label'] = 'XL 2990K EMA'
    tex = render(d)
    assert tex.count('XL 2990K EMA') == 2
    assert '2930K' not in tex


def test_incomplete_and_duplicate_rejected():
    d = document()
    d['responses'].pop()
    with pytest.raises(ValueError):
        render(d)
    d = document()
    d['responses'].append(d['responses'][0])
    with pytest.raises(ValueError):
        render(d)
