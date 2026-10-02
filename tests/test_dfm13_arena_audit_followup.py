import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = Path(__file__).parents[1]/'scripts/dfm13_arena_audit_followup.py'
spec = importlib.util.spec_from_file_location('arena_followup_test', PATH)
followup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(followup)


def test_private_engine_preserves_original():
    original = followup.engine(False)
    updated = followup.engine()
    assert original.VERSION == 'dfm13-arena-audit-v1'
    assert updated.VERSION == followup.VERSION
    assert followup.ADDENDUM not in original.RUBRIC
    assert followup.ADDENDUM in updated.RUBRIC
    assert original.schema() == updated.schema()
    assert len(updated.schema()['properties']) == 6
    assert 'ALL six fields' in updated.RUBRIC
    assert 'at most four issues' in updated.RUBRIC


def fake_source(failures=117, controls=12):
    items = [dict(id=str(i), exposed_manual_control=i<controls) for i in range(1000)]
    def load(path):
        i = int(path.name)
        return {'status':'invalid_response' if controls<=i<controls+failures else 'complete'}
    return SimpleNamespace(verify=lambda p: ({},items), outcome_path=lambda p,i:p/i['id'],
                           load=load, file_hash=lambda p:'hash')


def test_exact_selection():
    _, items, pins = followup.select(fake_source(), Path('/source'))
    assert len(items)==129 and len(pins)==1000
    assert sum(i['exposed_manual_control'] for i in items)==12
    assert sum(i['prior_status']=='invalid_response' for i in items)==117


@pytest.mark.parametrize('failures,controls', [(116,12),(118,12),(117,11)])
def test_refuse_wrong_scope(failures, controls):
    with pytest.raises(ValueError, match='exactly'):
        followup.select(fake_source(failures,controls),Path('/source'))


def test_refuse_unknown_infrastructure():
    base=fake_source()
    base.load=lambda p:{'status':'abort_status_unknown'}
    with pytest.raises(ValueError,match='infrastructure'):
        followup.select(base,Path('/source'))


def test_no_quota_or_complex_transport():
    module=followup.engine()
    payload=module.request({'messages':[{'role':'user','content':'Hello'},
                         {'role':'assistant','content':'Hello!'}], 'target_message_index':1},2048)
    assert payload['response_format']=={'type':'json_object'}
    assert payload['chat_template_kwargs']['enable_thinking'] is False
    assert 'No disposition quotas' in payload['messages'][0]['content']
    assert '20-100 characters' in payload['messages'][0]['content']
