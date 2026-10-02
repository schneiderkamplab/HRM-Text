from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import pytest
from scripts import dfm13_search_parallel86 as client


def allowed():
    return [dict(id='owner'+str(i//2),query='q'+str(i)) for i in range(86)]


def test_scope_cache_and_unresolved_reservations(tmp_path):
    b=client.base.SearchBudget(tmp_path);b.db.close()
    client.policy.migrate(tmp_path)
    b=client.Budget(tmp_path,allowed())
    with pytest.raises(ValueError,match='scope'):
        b.reserve('not authorized','owner0')
    key,_=b.reserve('q0','owner0')
    with pytest.raises(ValueError,match='retry prohibited'):
        b.reserve('q0','owner0')
    b.complete(key,b'{"data":[]}',{})
    assert b.reserve('q0','owner0')[1][0]==b'{"data":[]}'
    assert b.db.execute('SELECT count(*) FROM searches').fetchone()[0]==1
    b.db.close()


def test_parallel_final_slots_atomic(tmp_path):
    b=client.base.SearchBudget(tmp_path);client.policy.migrate(tmp_path)
    with b.db:
        b.db.executemany('INSERT INTO searches VALUES(?,?,?,?,NULL,NULL)',
            [('old'+str(i),'old',str(i),'reserved') for i in range(198)])
    b.db.close()
    def reserve(i):
        b=client.Budget(tmp_path,allowed())
        try:
            b.reserve('q'+str(i),'owner'+str(i//2));return True
        except ValueError:
            return False
        finally:
            b.db.close()
    with ThreadPoolExecutor(max_workers=16) as pool:
        assert sum(pool.map(reserve,range(86)))==2


def test_native_pairs_preserve_user_and_failed_observation():
    task=dict(id='test',sample=dict(prompt='original user',original_timestamp='2025-01-01'),
        queries=[dict(index=i,query='q'+str(i),source_asof='2025-01-01',reason='scope') for i in range(2)])
    original=deepcopy(task)
    messages=client.history(task,[dict(status='error',error='HTTP 422'),dict(status='done')],[])
    assert task==original
    assert messages[1]['content']=='original user'
    assert messages[2]['tool_calls'][0]['id']==messages[3]['tool_call_id']
    assert messages[4]['tool_calls'][0]['id']==messages[5]['tool_call_id']
    assert client.base.strict_json(messages[3]['content'])['error']=='HTTP 422'
    candidate=dict(id='test',messages=messages+[dict(role='assistant',content='Bounded answer.')],
        tools=client.base.TOOLS,target_message_indices=[6])
    client.pilot.contract.strict_row(candidate,'original user')


def test_sealed_manifest_has_exact_scopes_and_current_pins():
    manifest=client.prior.read(client.ROOT/'manifest.json')
    assert manifest['queries']==86
    assert manifest['total']==43
    assert manifest['starting_reservations']==114
    assert manifest['already_reserved_queries']==0
    assert manifest['retrieval_concurrency']==16
    assert manifest['concurrency_per_endpoint']==32
    for path,sha in manifest['pins'].items():
        assert client.base.file_hash(client.Path(path))==sha
