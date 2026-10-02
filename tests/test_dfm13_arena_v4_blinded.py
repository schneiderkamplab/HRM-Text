import importlib.util
from pathlib import Path

import pytest

spec=importlib.util.spec_from_file_location('arena_blind_test',Path(__file__).parents[1]/'scripts/dfm13_arena_v4_blinded.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def rows():
    example=dict(messages=[dict(role='user',content='Hi'),dict(role='assistant',content='Hello')],target_message_index=1)
    return [dict(id=str(i),example=example,row_sha256=module.base.digest(example)) for i in range(40)]


def test_exact_count_and_hashes():
    data=rows();module.check_samples(data)
    with pytest.raises(ValueError):module.check_samples(data[:-1])
    data[1]['id']=data[0]['id']
    with pytest.raises(ValueError):module.check_samples(data)
    data=rows();data[0]['row_sha256']='wrong'
    with pytest.raises(ValueError):module.check_samples(data)


def test_unchanged_reviewer():
    payload=module.engine.request(module.engine.evidence(rows()[0]['example']),'neutral',False)
    assert payload['messages'][0]['content']==module.engine.PROMPT+'\n'+module.engine.ROLES['neutral']
    assert payload['max_tokens']==3072


def test_freeze_refuses_incomplete(tmp_path,monkeypatch):
    monkeypatch.setattr(module.engine,'verify',lambda root:({},[{'id':'one'}]))
    module.base.write_json(tmp_path/'outcomes/one.json',dict(status='not_dispatched'))
    with pytest.raises(ValueError,match='not terminal'):module.freeze(tmp_path)


def test_freeze_hashes_and_no_overwrite(tmp_path,monkeypatch):
    monkeypatch.setattr(module.engine,'verify',lambda root:({},[{'id':str(i)} for i in range(40)]))
    for i in range(40):module.base.write_json(tmp_path/'outcomes'/f'{i}.json',dict(status='complete'))
    for name in ('manifest.json','seal.json','jobs.jsonl','assessment.json'):module.base.write_json(tmp_path/name,{})
    receipt=module.freeze(tmp_path);assert receipt['references_read'] is False
    assert len(module.base.load(tmp_path/'predictions-frozen.json')['outcomes'])==40
    with pytest.raises(ValueError,match='already frozen'):module.freeze(tmp_path)
