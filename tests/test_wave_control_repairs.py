import pytest
from scripts import calibrate_wave_control_repairs as control


def test_only_synthetic_prose_can_change(monkeypatch):
    monkeypatch.setattr(control, 'native_renderer', lambda: type('R', (), {'count': lambda self, m: 10})())
    original = dict(id='one', messages=[dict(role='system', content='Fixed'),
                    dict(role='user', content='Bad grammar'), dict(role='assistant', content='Answer')])
    messages = [dict(x) for x in original['messages']]
    messages[1]['content'] = 'Correct grammar'
    revised = control.candidate(original, dict(status='corrected', messages=messages))
    assert not revised['admission_authorized']
    assert revised['pilot_only']
    assert original['messages'][1]['content'] == 'Bad grammar'
    messages[0]['content'] = 'Altered context'
    with pytest.raises(ValueError, match='Protected context'):
        control.candidate(original, dict(status='corrected', messages=messages))
