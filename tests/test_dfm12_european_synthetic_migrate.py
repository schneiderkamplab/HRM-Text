import copy
import json
import os
from pathlib import Path
import sqlite3

import pytest
import yaml

from dfm12 import european_synthetic_campaign as campaign
from dfm12 import european_synthetic_migrate as migration
from dfm12.io import file_hash, load, lock, write_json


def configs():
    new=yaml.safe_load(campaign.CONFIG.read_text())
    new['languages'].update(et=1,ca=1)
    old=copy.deepcopy(new)
    old['languages'].update(et=2,ca=2)
    return old,new


def test_plan_only_doubles_twelve_groups():
    old,new=configs()
    changes=migration.plan(old,new)
    assert len(changes)==12
    assert {c['language'] for c in changes}=={'et','ca'}
    assert sum(c['new']-c['old'] for c in changes)==70000


@pytest.mark.parametrize('change',['campaign','other_language','family','model','already_done'])
def test_plan_rejects_scope_changes(change):
    old,new=configs()
    if change=='campaign':new['campaign']='different'
    elif change=='other_language':new['languages']['de']=1
    elif change=='family':new['families']['math-code']['full_priority_rows']*=2
    elif change=='model':new['auditor']='other'
    else:old=copy.deepcopy(new)
    with pytest.raises(ValueError):migration.plan(old,new)


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    old,new=configs()
    oldpath=tmp_path/'old.yaml';oldpath.write_text(yaml.safe_dump(old))
    newpath=tmp_path/'new.yaml';newpath.write_text(yaml.safe_dump(new))
    asset=tmp_path/'asset';asset.write_text('static asset')
    monkeypatch.setattr(campaign,'_asset_paths',lambda p:[asset])
    seeds=tmp_path/'seeds';seeds.mkdir()
    root=tmp_path/'campaign'
    campaign.prepare(root,seeds,config_path=oldpath,tokenizer_dir=tmp_path/'tokenizer')
    provider=campaign._provider().SourceProvider(seeds,root,old)
    with provider.db:
        provider.db.execute("INSERT INTO cursors VALUES ('et/et',123)")
        provider.db.execute("INSERT INTO used_sources VALUES ('et/et','source-id')")
    provider.close()
    with sqlite3.connect(root/'jobs.sqlite') as db:
        db.execute("UPDATE groups SET accepted=1,attempts=1,next_slot=100001 WHERE language='et' AND family='math-code'")
        db.execute("INSERT INTO jobs(id,language,family,slot,status,origin,spec_json,fingerprint) VALUES ('id','et','math-code',100000,'accepted','production','{}','fingerprint')")
        db.execute("INSERT INTO fingerprints VALUES ('fingerprint','id')")
    receipt=tmp_path/'drain.json'
    write_json(receipt,dict(phase='drained',root=str(root.resolve())))
    return root,newpath,tmp_path/'backup',receipt


def test_migration_preserves_everything_except_targets_and_seals(fixture):
    root,config,backup,receipt=fixture
    original=load(root/'manifest.json')
    result=migration.migrate(root,config,backup,receipt)
    assert result['phase']=='complete'
    assert result['state_before']==result['state_after']
    assert result['selections_unchanged']
    assert result['preserved_implementation_pins'] and result['preserved_external_pins']
    assert campaign.verify(root)['target']==490000
    assert load(backup/'manifest.json')==original
    with sqlite3.connect(root/'jobs.sqlite') as db:
        assert db.execute('SELECT SUM(target),SUM(accepted),SUM(attempts) FROM groups').fetchone()==(490000,1,1)
        assert db.execute("SELECT next_slot FROM groups WHERE language='et' AND family='math-code'").fetchone()[0]==100001
        assert db.execute('SELECT id FROM jobs').fetchone()[0]=='id'
    with sqlite3.connect(backup/'jobs.sqlite') as db:
        assert db.execute('SELECT SUM(target) FROM groups').fetchone()[0]==420000
    with pytest.raises(ValueError):migration.migrate(root,config,backup.parent/'another',receipt)


def test_locked_controller_refuses_migration(fixture):
    root,config,backup,receipt=fixture
    with lock(root/'controller.lock'):
        with pytest.raises(BlockingIOError):migration.migrate(root,config,backup,receipt)
    assert not backup.exists()


def test_active_work_refuses_migration(fixture):
    root,config,backup,receipt=fixture
    with sqlite3.connect(root/'jobs.sqlite') as db:
        db.execute("UPDATE groups SET active=1 WHERE language='et' AND family='math-code'")
    with pytest.raises(ValueError,match='active'):migration.migrate(root,config,backup,receipt)
    assert not backup.exists()


def test_failed_write_rolls_back_files_and_database(fixture,monkeypatch):
    root,config,backup,receipt=fixture
    before={n:file_hash(root/n) for n in migration.FILES}
    original=migration.write_json
    def broken(path,value):
        if Path(path)==root/'seal.json':raise RuntimeError('injected write failure')
        original(path,value)
    monkeypatch.setattr(migration,'write_json',broken)
    with pytest.raises(RuntimeError,match='injected'):migration.migrate(root,config,backup,receipt)
    assert before=={n:file_hash(root/n) for n in migration.FILES}
    assert campaign.verify(root)['target']==420000
    assert load(backup/'receipt.json')['phase']=='rolled_back'


def test_exact_command_and_runtime_identity(tmp_path):
    root=tmp_path/'campaign';root.mkdir()
    proc=tmp_path/'proc';pid=123
    process=proc/str(pid);process.mkdir(parents=True)
    write_json(root/'runtime.json',dict(pid=pid,concurrency_per_server=16,timeout=600,max_kv_cache_utilization=.90))
    command=migration.expected_command(root)
    (process/'cmdline').write_bytes(('\0'.join(command)+'\0').encode())
    (process/'stat').write_text('123 (controller) '+' '.join(['S']+['0']*18+['789']))
    assert migration.inspect_process(pid,root,proc)['start_ticks']=='789'
    command[4]='dfm12.multilingual_quarter'
    (process/'cmdline').write_bytes(('\0'.join(command)+'\0').encode())
    with pytest.raises(ValueError,match='command mismatch'):migration.inspect_process(pid,root,proc)


def test_missing_clean_drain_refused(fixture):
    root,config,backup,receipt=fixture
    write_json(receipt,dict(phase='draining',root=str(root)))
    with pytest.raises(ValueError,match='clean-drain'):migration.migrate(root,config,backup,receipt)


@pytest.mark.parametrize('mode',['success','pid_reused','timeout'])
def test_pidfd_drain_signals_only_verified_identity(fixture,monkeypatch,mode):
    root,_,_,existing=fixture
    receipt=existing.parent/'real-drain.json'
    reads=[];signals=[]
    def inspect(pid,root):
        reads.append(pid)
        return dict(pid=pid,root=str(root),command=migration.expected_command(root),
            start_ticks='other' if mode=='pid_reused' and len(reads)>1 else 'same')
    readfd,writefd=os.pipe()
    os.close(writefd)
    monkeypatch.setattr(migration,'inspect_process',inspect)
    monkeypatch.setattr(migration,'pidfd_open',lambda pid:readfd)
    monkeypatch.setattr(migration,'pidfd_signal',lambda fd,sig:signals.append((fd,sig)))
    monkeypatch.setattr(migration.select,'select',lambda *args:([] if mode=='timeout' else [readfd],[],[]))
    if mode=='pid_reused':
        with pytest.raises(ValueError,match='identity changed'):migration.drain(123,root,receipt)
        assert not signals
    elif mode=='timeout':
        with pytest.raises(TimeoutError):migration.drain(123,root,receipt)
        assert load(receipt)['phase']=='drain_timeout'
        assert len(signals)==1
    else:
        assert migration.drain(123,root,receipt)['phase']=='drained'
        assert signals==[(readfd,migration.signal.SIGTERM)]


def test_actual_pidfd_open_own_process_without_signal():
    fd=migration.pidfd_open(os.getpid())
    assert fd>=0
    os.close(fd)
