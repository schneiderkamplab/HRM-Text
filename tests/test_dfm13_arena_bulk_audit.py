import importlib.util
import asyncio
import pytest
from pathlib import Path

spec=importlib.util.spec_from_file_location('bulk_test',Path(__file__).parents[1]/'scripts/dfm13_arena_bulk_audit.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_material_check_simple_output():
    row=dict(messages=[dict(role='user',content='Hi'),dict(role='assistant',content='Hello')],target_message_index=1)
    p=module.request(row)
    assert p['chat_template_kwargs']=={'enable_thinking':False}
    assert set(p['response_format']['json_schema']['schema']['properties'])=={'verdict','reason'}
    assert 'complete rather than cut off' in p['messages'][0]['content']


def test_durable_ledger(tmp_path):
    db=module.database(tmp_path)
    db.execute('INSERT INTO jobs(seq,source,line,offset,length,source_id) VALUES(1,0,1,0,10,"test")');db.commit();db.close()
    db=module.database(tmp_path)
    assert db.execute('SELECT status FROM jobs').fetchone()==('pending',)
    db.close()


@pytest.mark.parametrize('value',[0,1025,True,'512'])
def test_invalid_concurrency(tmp_path,value):
    with pytest.raises(ValueError,match='concurrency_per_server'):
        asyncio.run(module.run(tmp_path,{'concurrency_per_server':value}))
