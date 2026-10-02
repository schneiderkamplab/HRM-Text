import copy
import importlib.util
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

P=Path(__file__).resolve().parents[1]/'scripts/dfm13_arena_repair_concurrency_migration.py'
spec=importlib.util.spec_from_file_location('repair_migration_test',P)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def sample(running=128,kv=.5,waiting=0):
    return [dict(time=m.time.time(),values={'vllm:num_requests_running':running,
        'vllm:num_requests_waiting':waiting,'vllm:kv_cache_usage_perc':kv}) for _ in range(8)]


def test_only_concurrency_changes():
    old=dict(own_per_server=128,pins={'x':'y'},max_attempts=3,max_kv=.9,shared_cap=512)
    before=copy.deepcopy(old);new=m.increased(old)
    assert old==before
    assert new==dict(old,own_per_server=256)
    new['pins']['x']='changed';assert old['pins']['x']=='y'
    with pytest.raises(ValueError):m.increased(dict(old,own_per_server=256))


@pytest.mark.parametrize('rows',[sample(kv=.81),sample(waiting=1),sample(running=257),sample()[:7],
    [dict(time=0,values=x['values']) for x in sample()]])
def test_unsafe_or_stale_headroom_refused(rows):
    assert not m.headroom(rows)


def test_post_stop_requires_low_sustained_load():
    assert m.headroom(sample())
    assert not m.headroom(sample(),low=True)
    assert m.headroom(sample(running=1,kv=.01),low=True)


def test_current_test_process_cannot_be_signalled():
    with pytest.raises(ValueError,match='command mismatch'):
        m.identity(m.os.getpid(),Path('/not-the-owned-root'))


def test_nonterminal_peer_refuses_before_process_actions(tmp_path,monkeypatch):
    monkeypatch.setattr(m.guard,'terminal_ready',lambda p:False)
    monkeypatch.setattr(m,'identity',lambda *a:pytest.fail('Must not touch owned client yet'))
    with pytest.raises(ValueError,match='Peer not terminal'):
        m.migrate(tmp_path,tmp_path,1,tmp_path/'archive')


@pytest.mark.parametrize('fallback',[False,True])
def test_controlled_migration_preserves_ledger_and_launches_once(tmp_path,monkeypatch,fallback):
    plan=dict(own_per_server=128,manifest=dict(endpoints=['http://unused/v1']*8),max_attempts=3)
    m.repair.base.write_json(tmp_path/'plan.json',plan)
    m.repair.base.write_json(tmp_path/'seal.json',dict(sha256=m.repair.base.file_hash(tmp_path/'plan.json')))
    with sqlite3.connect(tmp_path/'ledger.sqlite') as db:
        for table in ('accepted','rejected','needs_review'):db.execute(f'CREATE TABLE {table}(seq INTEGER,record TEXT)')
        db.execute('INSERT INTO accepted VALUES(1,?)',('{"preserved":true}',))
        db.execute('CREATE TABLE attempts(seq INTEGER,stage TEXT,n INTEGER,status TEXT,hash TEXT,record TEXT)')
        db.execute("INSERT INTO attempts VALUES(2,'correction',2,'inflight','hash','{}')")
        db.execute("INSERT INTO attempts VALUES(1,'fresh_reaudit',1,'complete','hash','{}')")
    owner=dict(pid=123,argv=['exact verified command'],start_ticks='456')
    signals=[];launches=[]
    monkeypatch.setattr(m.guard,'terminal_ready',lambda p:True)
    monkeypatch.setattr(m.repair,'verify',lambda p:m.repair.base.load(p/'plan.json'))
    monkeypatch.setattr(m,'metrics',lambda _:sample(running=128 if fallback else 0,kv=.5 if fallback else .01))
    if fallback:
        ticks=iter(range(0,10000,60))
        monkeypatch.setattr(m.time,'monotonic',lambda:next(ticks))
    monkeypatch.setattr(m,'identity',lambda *a:owner)
    monkeypatch.setattr(m,'pidfd_open',lambda p:987654)
    close=m.os.close
    monkeypatch.setattr(m.os,'close',lambda fd:None if fd==987654 else close(fd))
    monkeypatch.setattr(m,'pidfd_interrupt',lambda fd:signals.append((fd,m.signal.SIGINT)))
    monkeypatch.setattr(m.select,'select',lambda *a:([987654],[],[]))
    monkeypatch.setattr(m.time,'sleep',lambda _:None)
    def launch(command,**kwargs):
        launches.append(command)
        m.repair.base.write_json(tmp_path/'progress.json',dict(pid=456,active=[1]*8))
        return SimpleNamespace(pid=456,poll=lambda:None)
    monkeypatch.setattr(m.subprocess,'Popen',launch)
    result=m.migrate(tmp_path,tmp_path/'peer',123,tmp_path/'archive')
    assert len(signals)==len(launches)==1
    assert signals[0][1]==m.signal.SIGINT
    assert result['status']=='progress_verified'
    assert result['completed_rows_and_stages_preserved'] is True
    expected=128 if fallback else 256
    assert result['own_per_server']==expected
    with sqlite3.connect(tmp_path/'ledger.sqlite') as db:
        assert db.execute('SELECT record FROM accepted').fetchone()[0]=='{"preserved":true}'
        assert db.execute('SELECT status FROM attempts WHERE seq=2').fetchone()[0]=='inflight'
    assert m.repair.base.load(tmp_path/'plan.json')==dict(plan,own_per_server=expected)


def test_downstream_pin_mismatch_fails_before_modifying(tmp_path):
    m.repair.base.write_json(tmp_path/'plan.json',dict(pins={}))
    m.repair.base.write_json(tmp_path/'plan-seal.json',dict(sha256=m.repair.base.file_hash(tmp_path/'plan.json')))
    before=(tmp_path/'plan.json').read_bytes()
    with pytest.raises(ValueError,match='pin mismatch'):
        m.refresh_downstream(tmp_path,tmp_path,{'plan.json':'expected'},None)
    assert (tmp_path/'plan.json').read_bytes()==before


def test_downstream_refresh_archives_and_changes_only_two_pins(tmp_path):
    source=tmp_path/'source';source.mkdir()
    downstream=tmp_path/'downstream';downstream.mkdir()
    archive=tmp_path/'archive';archive.mkdir()
    for name in ('plan.json','seal.json'):m.repair.base.write_json(source/name,{'new':True})
    old={name:'old-'+name for name in ('plan.json','seal.json')}
    plan=dict(pins={str(source/name):value for name,value in old.items()},limit=32,no_admission=True)
    plan['pins']['unrelated']='keep'
    m.repair.base.write_json(downstream/'plan.json',plan)
    m.repair.base.write_json(downstream/'plan-seal.json',dict(sha256=m.repair.base.file_hash(downstream/'plan.json')))
    m.refresh_downstream(downstream,source,old,archive)
    new=m.repair.base.load(downstream/'plan.json')
    assert m.repair.base.load(archive/'downstream/plan.json')==plan
    assert new['limit']==32 and new['no_admission'] is True
    assert new['pins']['unrelated']=='keep'
    assert {p:new['pins'][str(source/p)] for p in old}=={p:m.repair.base.file_hash(source/p) for p in old}


def test_retired_cli_refuses_before_any_process_action(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(m.sys,'argv',['migration','--root',str(tmp_path),'--peer',str(tmp_path),
                                    '--pid','123','--archive',str(tmp_path/'archive')])
    monkeypatch.setattr(m,'migrate',lambda *a:pytest.fail('Retired CLI must not migrate'))
    with pytest.raises(SystemExit) as exc:m.main()
    assert exc.value.code==2
    assert 'Migration disabled' in capsys.readouterr().err
