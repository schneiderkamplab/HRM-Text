import importlib.util
from pathlib import Path
import pytest

P=Path(__file__).resolve().parents[1]/'scripts/dfm13_arena_review_only_recovery.py'
spec=importlib.util.spec_from_file_location('review_only_test',P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


@pytest.mark.parametrize('stage,complete,expected',[
    ('retry_audit',False,True),('fresh_reaudit',False,True),
    ('correction',False,False),('retry_audit',True,False)])
def test_review_only_selection(stage,complete,expected):
    assert m.eligible(stage,dict(finish_reason='length',content='x'+' '*200),complete)==expected


def test_no_reasoning_or_genuine_long_retry():
    assert not m.eligible('retry_audit',dict(finish_reason='length',content=None),False)
    assert not m.eligible('retry_audit',dict(finish_reason='length',content='substantive text'),False)


def test_terminal_required_before_materialization(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'verify_plan',lambda root:dict(source=str(tmp_path/'active')))
    with pytest.raises(ValueError,match='not terminal'):
        m.materialize(tmp_path)


def test_whole_target_explicit_contract():
    row=dict(id='x',target_message_index=1,messages=[dict(role='user',content='2+2?'),dict(role='assistant',content='5')])
    request=m.whole_target(m.pilot.repair.strong.request(row))
    assert request['response_format']=={'type':'json_object'}
    assert request['chat_template_kwargs']['enable_thinking'] is True
    assert 'WHOLE target' in request['messages'][0]['content']
    assert 'Exact output contract' in request['messages'][0]['content']
