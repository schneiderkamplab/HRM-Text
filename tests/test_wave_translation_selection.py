import pytest

from dfm12.wave_translation_selection import PairSelection


def row(text, tokens=60):
    return dict(task='translation', language='lv', reverse_language='lt', rendered_tokens=tokens,
        messages=[dict(role='user', content='Translate'), dict(role='assistant', content=text)],
        reverse_messages=[dict(role='user', content='Translate'), dict(role='assistant', content='LT ' + text)])


def verdict(keep=True):
    return dict(keep=keep, language_quality=5, coherence=5, usefulness=5, reason='OK')


def test_shared_cap_deduplication_and_direct_preference(tmp_path):
    selection = PairSelection(tmp_path / 'pairs.sqlite', ['lt', 'lv'], 100)
    selection.add(row('same'), verdict(), 'pivot-lt-lv', 'pivot')
    selection.add(row('same'), verdict(), 'direct-lt-lv', 'direct')
    selection.add(row('small', 40), verdict(), 'pivot-other', 'pivot')
    selection.add(row('too-large', 101), verdict(), 'direct-other', 'direct')
    selected = list(selection.selected())
    assert len(selected) == 2
    assert selected[0]['component'] == 'direct-lt-lv'
    assert selected[-1]['cumulative_tokens'] == 100
    assert sum(r['combined_tokens'] for r in selected) == 100
    assert list(selection.selected()) == selected
    with pytest.raises(ValueError, match='Nonpositive'):
        selection.add(row('rejected'), verdict(False), 'direct', 'direct')
    with pytest.raises(ValueError, match='pair mismatch'):
        selection.add(dict(row('wrong'), language='en'), verdict(), 'direct', 'direct')
    selection.close()
    with pytest.raises(ValueError, match='configuration changed'):
        PairSelection(tmp_path / 'pairs.sqlite', ['lt', 'lv'], 200)
