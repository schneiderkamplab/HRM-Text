import asyncio
import json
import pytest
from scripts import dfm13_search_supplement9 as s

def seed(budget,count):
    with budget.db:
        for i in range(count):budget.db.execute('INSERT INTO searches(key,owner,query,status) VALUES(?,?,?,?)',
            ('old'+str(i),'owner'+str(i),'old query '+str(i),'reserved'))

def test_preserves87_and_charges9_once(tmp_path):
    allowed={'owner'+str(i):'new query '+str(i) for i in range(9)}
    b=s.SupplementBudget(tmp_path,allowed);seed(b,87)
    for owner,query in allowed.items():b.reserve(query,owner)
    assert b.db.execute('SELECT count(*) FROM searches').fetchone()[0]==96
    assert b.db.execute('SELECT count(*) FROM searches WHERE key LIKE "old%"').fetchone()[0]==87
    with pytest.raises(ValueError):b.reserve('new query 0','owner0')
    assert b.db.execute('SELECT count(*) FROM searches').fetchone()[0]==96

def test_global100_cap(tmp_path):
    b=s.SupplementBudget(tmp_path,{'owner0':'extra'});seed(b,100)
    with pytest.raises(ValueError):b.reserve('extra','owner0')

def test_unknown_query_refused(tmp_path):
    b=s.SupplementBudget(tmp_path,{'owner0':'extra'})
    with pytest.raises(ValueError):b.reserve('different','owner0')
    assert b.db.execute('SELECT count(*) FROM searches').fetchone()[0]==0

def test_cached_complete_does_not_charge_twice(tmp_path):
    b=s.SupplementBudget(tmp_path,{'owner0':'extra'})
    key,_=b.reserve('extra','owner0');b.complete(key,b'{}',{})
    _,cached=b.reserve('extra','owner0')
    assert cached[0]==b'{}'
    assert b.db.execute('SELECT count(*) FROM searches').fetchone()[0]==1

def test_teacher_hint_removed_for_unrelated_case():
    class Model:
        tokenizer=None;manifest={}
        async def ask(self,messages,*args):return messages
    text='and do not give a proof of a mathematical minimum unless established; in particular bases 2,3,5,7 do NOT guarantee Miller-Rabin correctness for all 32-bit integers: 3215031751 is a composite counterexample. '
    result=asyncio.run(s.ScopedModel(Model(),None).ask([dict(role='system',content=text)],None,None,None,'repair'))
    assert '3215031751' not in json.dumps(result)

def test_private_key_file_required(tmp_path,monkeypatch):
    monkeypatch.delenv('JINA_API_KEY',raising=False)
    p=tmp_path/'key';p.write_text('test-only-value');p.chmod(0o644)
    with pytest.raises(ValueError):s.load_key(p)
    p.chmod(0o600);assert s.load_key(p)=='test-only-value'

def test_concurrent_last_slot_is_atomic(tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    allowed={'owner0':'extra0','owner1':'extra1'}
    setup=s.SupplementBudget(tmp_path,allowed);seed(setup,99);setup.db.close()
    barrier=threading.Barrier(2)
    def reserve(index):
        budget=s.SupplementBudget(tmp_path,allowed)
        barrier.wait()
        try:
            budget.reserve('extra'+str(index),'owner'+str(index));return True
        except ValueError:return False
        finally:budget.db.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(reserve,range(2)))==1
    final=s.SupplementBudget(tmp_path,allowed)
    assert final.db.execute('SELECT count(*) FROM searches').fetchone()[0]==100
