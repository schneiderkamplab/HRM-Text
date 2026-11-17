from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import random
import sqlite3
import subprocess
import sys
import time
from threading import Barrier

import pytest

from eval_scheduler.model import Action, Job, JobStatus, read_plan
from eval_scheduler.store import SQLiteJobStore, require_local_storage


def job(key="a", **updates):
    return Job(key, Action.REPORT, "test", key).with_updates(**updates)


def test_recovery_rearms_completed_terminal_barriers(tmp_path):
    store = SQLiteJobStore(tmp_path/'jobs.sqlite')
    store.import_jobs([
        job('train', status=JobStatus.FAILED),
        job('eval', deps=('train',)),
        job('gate', action=Action.TERMINAL_BARRIER, deps=('eval',),
            deps_mode='terminal', status=JobStatus.DONE),
        job('outer', action=Action.TERMINAL_BARRIER, deps=('gate',),
            deps_mode='terminal', status=JobStatus.DONE),
        job('next', deps=('train', 'outer')),
    ])
    store.update_jobs({'train': {'status': JobStatus.PENDING}})
    rows = {j.job_id: j for j in store.load_jobs()}
    assert rows['gate'].status == rows['outer'].status == JobStatus.PENDING
    assert {j.job_id for j in store.ready_jobs()} == {'train'}
    store.update_jobs({'train': {'status': JobStatus.DONE}})
    assert {j.job_id for j in store.ready_jobs()} == {'eval'}
    store.update_jobs({'eval': {'status': JobStatus.FAILED}})
    assert {j.job_id for j in store.ready_jobs()} == {'gate'}


def test_terminal_barrier_stays_done_for_unrecoverable_eval(tmp_path):
    store = SQLiteJobStore(tmp_path/'jobs.sqlite')
    store.import_jobs([
        job('eval', status=JobStatus.FAILED),
        job('gate', action=Action.TERMINAL_BARRIER, deps=('eval',),
            deps_mode='terminal', status=JobStatus.DONE),
    ])
    store.update_jobs({'eval': {'attempt': 3}})
    assert store.load_jobs()[1].status == JobStatus.DONE


def test_network_authority_refused(monkeypatch):
    monkeypatch.setattr(Path, 'read_text', lambda self: '1 0 0:1 / / rw - overlay overlay rw\n'
                        '2 1 0:2 / /work/shared rw - wekafs remote rw\n')
    require_local_storage(Path('/tmp/local.sqlite'))
    with pytest.raises(ValueError, match='wekafs'):
        require_local_storage(Path('/work/shared/state.sqlite'))


def test_consistent_backup_includes_running_token(tmp_path):
    store = SQLiteJobStore(tmp_path/'state.sqlite')
    store.import_jobs([job()])
    claim = store.claim_jobs(['a'])['a']
    backup = tmp_path/'backup.sqlite'
    store.backup(backup)
    assert SQLiteJobStore(backup).attempt_token('a') == claim.token
    store.finish('a', claim.token, {'status': JobStatus.DONE})
    store.backup(backup)
    assert SQLiteJobStore(backup).load_jobs()[0].status == JobStatus.DONE


def test_initial_import_reopen_and_tsv(tmp_path):
    path = tmp_path/"jobs.sqlite"
    original = [job(status=JobStatus.DONE, attempt=2, log_dir="logs/test", metadata={"nested": [1,"\u00e6"]}),
                job("b", deps=("a",), initial_batch=8, max_retries=0)]
    store = SQLiteJobStore(path)
    store.import_jobs(original)
    assert SQLiteJobStore(path).load_jobs() == original
    store.export_tsv(tmp_path/"plan.tsv")
    assert read_plan(tmp_path/"plan.tsv") == original
    with pytest.raises(ValueError): store.export_tsv(path)
    with store._connect() as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert db.execute("PRAGMA synchronous").fetchone()[0] == 2
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_epoch_finalization_preserves_wait_claim_and_concurrent_metadata(tmp_path):
    store = SQLiteJobStore(tmp_path/'jobs.sqlite')
    store.import_jobs([job('wait', action=Action.WAIT_CHECKPOINT, metadata={'keep': 1}),
                       job('eval', deps=('wait',), metadata={'keep': 2})])
    claim = store.claim_jobs(['wait'])['wait']
    store.finalize_eval_epoch(['wait', 'eval'], 12.5, ['dfm14_cursor_epoch_pending'],
                              train_step=950000)
    assert store.attempt_token('wait') == claim.token
    assert store.finish('wait', claim.token, {'status': JobStatus.DONE})
    rows = store.load_jobs()
    assert [j.metadata['eval_epoch'] for j in rows] == [12.5, 12.5]
    assert [j.metadata['eval_step'] for j in rows] == [950000, 950000]
    assert [j.metadata['keep'] for j in rows] == [1, 2]
    assert all(j.metadata['dfm14_cursor_epoch_pending'] is False for j in rows)
    store.claim_jobs(['eval'])
    with pytest.raises(ValueError, match='already started'):
        store.finalize_eval_epoch(['wait', 'eval'], 13)
    assert store.load_jobs()[0].metadata['eval_epoch'] == 12.5  # Entire update rolls back.


@pytest.mark.parametrize('step', [-1, 1.5, True])
def test_epoch_finalization_rejects_invalid_step(tmp_path, step):
    store = SQLiteJobStore(tmp_path/'jobs.sqlite')
    store.import_jobs([job()])
    with pytest.raises(ValueError, match='training step'):
        store.finalize_eval_epoch(['a'], 3.2, train_step=step)


def test_claim_token_and_crash_reopen(tmp_path):
    path = tmp_path/"jobs.sqlite"
    store = SQLiteJobStore(path); store.import_jobs([job()])
    code = """
import os, sys
from eval_scheduler.store import SQLiteJobStore
s=SQLiteJobStore(sys.argv[1])
c=s.claim_jobs(['a'])['a']
print(c.token, flush=True)
os._exit(0)
"""
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    token = subprocess.check_output([sys.executable,"-c",code,str(path)],env=env,text=True).strip()
    reopened = SQLiteJobStore(path)
    assert reopened.load_jobs()[0].status == JobStatus.RUNNING
    assert reopened.attempt_token("a") == token
    assert reopened.claim_jobs(["a"]) == {}
    assert reopened.finish("a",token,{"status":"done"})
    assert not reopened.finish("a",token,{"status":"failed"})
    assert reopened.attempt_token("a") is None


def test_uncommitted_crash_rolls_back(tmp_path):
    path = tmp_path/"jobs.sqlite"
    store = SQLiteJobStore(path); store.import_jobs([job()])
    code = """
import sqlite3,os,sys
c=sqlite3.connect(sys.argv[1],isolation_level=None)
c.execute('BEGIN IMMEDIATE')
c.execute("UPDATE jobs SET status='running',token='not-committed' WHERE job_id='a'")
os._exit(0)
"""
    subprocess.check_call([sys.executable,"-c",code,str(path)])
    assert SQLiteJobStore(path).load_jobs() == [job()]


def test_two_claimants_get_one_owner(tmp_path):
    path=tmp_path/"jobs.sqlite"
    SQLiteJobStore(path).import_jobs([job()])
    barrier=Barrier(2)
    def claim():
        store=SQLiteJobStore(path)
        barrier.wait()
        return store.claim_jobs(["a"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:claim(),range(2)))
    assert sorted(len(x) for x in results)==[0,1]
    winner=next(x["a"] for x in results if x)
    assert SQLiteJobStore(path).attempt_token("a")==winner.token


def test_retry_tokens_fence_old_completion_without_increment_on_claim(tmp_path):
    store=SQLiteJobStore(tmp_path/"jobs.sqlite")
    store.import_jobs([job(initial_batch=16)])
    first=store.claim_jobs(["a"])["a"]
    assert first.job.attempt==0 and first.job.retry_batch()==16
    assert store.finish("a",first.token,{"status":JobStatus.PENDING,"attempt":1})
    second=store.claim_jobs(["a"])["a"]
    assert first.token!=second.token and second.job.attempt==1 and second.job.retry_batch()==8
    assert not store.finish("a",first.token,{"status":JobStatus.DONE})
    assert store.finish("a",second.token,{"status":JobStatus.DONE})


def test_definition_import_preserves_runtime_but_initial_import_does_not(tmp_path):
    store=SQLiteJobStore(tmp_path/"jobs.sqlite")
    store.import_jobs([job(status=JobStatus.FAILED,attempt=4,log_dir='actual/log')])
    store.import_jobs([job(name="edited", metadata={"new":True})])
    got=store.load_jobs()[0]
    assert got.name=="edited" and got.status==JobStatus.FAILED and got.attempt==4
    assert got.log_dir=='actual/log'
    store.import_jobs([job(name="reset")],preserve_runtime=False)
    assert store.load_jobs()==[job(name="reset")]


@pytest.mark.parametrize("operation",["remove","definition","log_dir","status","attempt","patch"])
def test_running_edits_rejected(tmp_path,operation):
    store=SQLiteJobStore(tmp_path/"jobs.sqlite");store.import_jobs([job()])
    claimed=store.claim_jobs(["a"])["a"]
    with pytest.raises(ValueError):
        if operation=="remove":store.import_jobs([])
        elif operation=="definition":store.import_jobs([job(name="changed")])
        elif operation=="log_dir":store.import_jobs([claimed.job.with_updates(log_dir="changed")],preserve_runtime=False)
        elif operation=="status":store.import_jobs([job()],preserve_runtime=False)
        elif operation=="attempt":store.update_jobs({"a":{"attempt":3}})
        else:store.update_jobs({"a":{"metadata":{"edit":True}}})
    assert store.load_jobs()==[claimed.job]
    assert store.attempt_token("a")==claimed.token
    # Stale TSV status is ignored while an unchanged running definition is imported.
    store.import_jobs([job()])
    assert store.attempt_token("a")==claimed.token
    store.import_jobs([job(log_dir='stale/import/path')])
    assert store.load_jobs()==[claimed.job]


@pytest.mark.parametrize("jobs",[
    [job(),job()], [job(deps=("missing",))], [job(deps=("a",))],
    [job(deps=("b",)),job("b",deps=("a",))], [job(deps_mode="unknown")],
])
def test_bad_graph_import_rolls_back(tmp_path,jobs):
    store=SQLiteJobStore(tmp_path/"jobs.sqlite");store.import_jobs([job("old")])
    with pytest.raises(ValueError):store.import_jobs(jobs)
    assert store.load_jobs()==[job("old")]


def test_nonrunning_edits_graph_validation_and_atomic_runtime_updates(tmp_path):
    store=SQLiteJobStore(tmp_path/"jobs.sqlite")
    store.import_jobs([job(),job("b",deps=("a",))])
    with pytest.raises(ValueError):store.update_jobs({"a":{"deps":("b",)}})
    with pytest.raises(ValueError):store.update_jobs({"a":{"deps":("absent",)}})
    with pytest.raises(KeyError):store.update_jobs({"a":{"status":"done"},"absent":{"status":"done"}})
    assert store.load_jobs()[0].status==JobStatus.PENDING
    store.update_jobs({"a":{"status":"failed","attempt":3}})
    store.update_jobs({"a":{"name":"new"}})
    assert store.load_jobs()[0].attempt==3 and store.load_jobs()[0].status==JobStatus.FAILED
    with pytest.raises(ValueError):store.update_jobs({"a":{"name":"bad","attempt":0}})
    with pytest.raises(ValueError):store.update_jobs({"a":{"status":"running"}})
    with pytest.raises(ValueError):store.update_jobs({"a":{"job_id":"new"}})


def test_status_updates_never_rewrite_definition(tmp_path):
    store=SQLiteJobStore(tmp_path/"jobs.sqlite");store.import_jobs([job()])
    with store._connect() as db:
        db.execute("CREATE TRIGGER no_rewrite BEFORE UPDATE OF definition ON jobs BEGIN SELECT RAISE(ABORT,'definition rewritten'); END")
    store.update_jobs({"a":{"status":"failed","attempt":1}})
    store.update_jobs({"a":{"status":"pending"}})
    claim=store.claim_jobs(["a"])["a"]
    assert store.finish("a",claim.token,{"status":"done"})


def test_ready_and_claim_match_runtime_random_dags(tmp_path):
    from eval_scheduler.runtime import dependencies_satisfied
    rng=random.Random(39)
    store=SQLiteJobStore(tmp_path/"jobs.sqlite")
    for _ in range(30):
        jobs=[]
        for i in range(18):
            optional=rng.random()<.2
            jobs.append(job(str(i), action=Action.EVAL_EUROEVAL if optional else Action.REPORT,
                name='valeu-case' if optional else str(i),
                deps=tuple(str(d) for d in range(i) if rng.random()<.16),
                deps_mode=rng.choice(['success','terminal']), status=rng.choice(list(JobStatus))))
        # Each fixture has its own store, since editing imported RUNNING rows is forbidden.
        target=SQLiteJobStore(tmp_path/(str(_)+'.sqlite'));target.import_jobs(jobs)
        expected=[j.job_id for j in jobs if j.status==JobStatus.PENDING and dependencies_satisfied(j,jobs)]
        assert [j.job_id for j in target.ready_jobs()]==expected
        assert list(target.claim_jobs([j.job_id for j in jobs]))==expected


def test_terminal_transitive_block_and_optional_dep(tmp_path):
    store=SQLiteJobStore(tmp_path/'jobs.sqlite')
    jobs=[job('failure',status=JobStatus.FAILED),job('blocked',deps=('failure',)),
          job('barrier',deps=('blocked',),deps_mode='terminal'),
          job('optional',action=Action.EVAL_EUROEVAL,name='valeu-fi',status=JobStatus.RUNNING),
          job('optional_gate',deps=('optional',))]
    store.import_jobs(jobs)
    assert [j.job_id for j in store.ready_jobs()]==['barrier','optional_gate']


def test_finish_invalid_patch_does_not_consume_token(tmp_path):
    store=SQLiteJobStore(tmp_path/'jobs.sqlite');store.import_jobs([job()])
    claim=store.claim_jobs(['a'])['a']
    for patch in ({'name':'new','status':'done'},{'attempt':1},{'status':'running'},{'status':'done','attempt':-1}):
        with pytest.raises(ValueError):store.finish('a',claim.token,patch)
        assert store.attempt_token('a')==claim.token
    assert not store.finish('unknown',claim.token,{'status':'done'})


def test_removed_job_reintroduced_cannot_reuse_token(tmp_path):
    store=SQLiteJobStore(tmp_path/'jobs.sqlite');store.import_jobs([job()])
    first=store.claim_jobs(['a'])['a']
    store.finish('a',first.token,{'status':'done'})
    store.import_jobs([]);store.import_jobs([job()])
    second=store.claim_jobs(['a'])['a']
    assert not store.finish('a',first.token,{'status':'done'})
    assert second.token!=first.token


def test_admin_fence_persists_allows_finish_and_migrates_v1(tmp_path):
    path=tmp_path/'jobs.sqlite'
    store=SQLiteJobStore(path);store.import_jobs([job(),job('b')])
    claim=store.claim_jobs(['a'])['a']
    # Recreate the exact pre-administration schema, then migrate without losing claims.
    with store._connect() as db:
        db.execute('DROP TABLE administration')
        db.execute('PRAGMA user_version=1')
    store=SQLiteJobStore(path)
    assert not store.get_admin_lock()
    store.set_admin_lock(True)
    reopened=SQLiteJobStore(path)
    assert reopened.get_admin_lock()
    assert reopened.claim_jobs(['b'])=={}
    assert reopened.ready_jobs()==[]
    assert reopened.finish('a',claim.token,{'status':'done'})
    reopened.set_admin_lock(False)
    assert list(reopened.claim_jobs(['b']))==['b']
    with pytest.raises(ValueError):store.set_admin_lock('false')


def test_admin_fence_serializes_with_waiting_claim(tmp_path):
    from threading import Event
    store=SQLiteJobStore(tmp_path/'jobs.sqlite');store.import_jobs([job()])
    started=Event()
    def claim():
        started.set()
        return store.claim_jobs(['a'])
    with ThreadPoolExecutor(max_workers=1) as pool:
        with store._transaction(write=True) as db:
            db.execute('UPDATE administration SET locked=1 WHERE singleton=1')
            future=pool.submit(claim)
            assert started.wait(5)
            assert not future.done()
        assert future.result(timeout=5)=={}
    assert store.load_jobs()[0].status==JobStatus.PENDING


def test_import_requires_admin_lock_opt_in(tmp_path):
    store=SQLiteJobStore(tmp_path/'jobs.sqlite')
    store.import_jobs([job(log_dir='actual')])
    replacement=[job(name='edited',log_dir='stale')]
    with pytest.raises(ValueError,match='active admin lock'):
        store.import_jobs(replacement,require_admin_lock=True)
    assert store.load_jobs()==[job(log_dir='actual')]
    store.set_admin_lock(True)
    store.import_jobs(replacement,require_admin_lock=True)
    assert store.load_jobs()==[job(name='edited',log_dir='actual')]
    assert store.get_admin_lock()
    store.set_admin_lock(False)
    # Existing callers retain the unguarded import API.
    store.import_jobs([job(name='default')])
    assert store.load_jobs()[0].name=='default'


def test_import_checks_fence_after_waiting_for_write_transaction(tmp_path):
    from threading import Event
    store=SQLiteJobStore(tmp_path/'jobs.sqlite');store.import_jobs([job()])
    store.set_admin_lock(True)
    started=Event()
    def importer():
        started.set()
        store.import_jobs([job(name='must-not-import')],require_admin_lock=True)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with store._transaction(write=True) as db:
            db.execute('UPDATE administration SET locked=0 WHERE singleton=1')
            future=pool.submit(importer)
            assert started.wait(5)
            assert not future.done()
        with pytest.raises(ValueError,match='active admin lock'):
            future.result(timeout=5)
    assert store.load_jobs()==[job()]
    assert not store.get_admin_lock()


def test_ready_limit(tmp_path):
    store=SQLiteJobStore(tmp_path/'jobs.sqlite')
    store.import_jobs([job(),job('b',deps=('a',)),job('c')])
    assert store.ready_jobs(limit=0)==[]
    assert [j.job_id for j in store.ready_jobs(limit=1)]==['a']
    assert [j.job_id for j in store.ready_jobs(limit=2)]==['a','c']
    for limit in (-1,1.5,True):
        with pytest.raises(ValueError):store.ready_jobs(limit=limit)


def test_40k_bounded_claims_and_shared_status_updates(tmp_path,monkeypatch):
    import eval_scheduler.store as module
    store=SQLiteJobStore(tmp_path/'jobs.sqlite')
    start=time.perf_counter()
    store.import_jobs(job(str(i),metadata={'payload':'x'*1024}) for i in range(40000))
    imported=time.perf_counter()-start
    decoded=[]
    original=module._job
    def decode(row):
        decoded.append(row['job_id'])
        return original(row)
    monkeypatch.setattr(module,'_job',decode)
    def no_scan(*args):
        pytest.fail('Runtime operations must not load the full plan')
    monkeypatch.setattr(store,'_rows',no_scan)
    start=time.perf_counter()
    ready=store.ready_jobs(limit=128)
    ready_seconds=time.perf_counter()-start
    assert len(ready)==len(decoded)==128
    decoded.clear()
    start=time.perf_counter()
    claims=store.claim_jobs(str(i) for i in range(39872,40000))
    claim_seconds=time.perf_counter()-start
    assert len(claims)==len(decoded)==128
    decoded.clear()
    start=time.perf_counter()
    store.update_jobs({str(i):{'status':'done','log_dir':f'logs/{i}'} for i in range(128)})
    update_seconds=time.perf_counter()-start
    assert len(decoded)==128
    # Query plan must search requested IDs, not scan all pending definitions.
    with store._connect() as db:
        db.execute('CREATE TEMP TABLE requested(job_id TEXT PRIMARY KEY)')
        sql=module.READY_SQL.format(candidates='requested r CROSS JOIN jobs j',
                                   candidate_filter='j.job_id=r.job_id AND')
        plan=[r['detail'] for r in db.execute('EXPLAIN QUERY PLAN '+sql,{'limit':-1})]
        assert any('SEARCH j USING INDEX sqlite_autoindex_jobs_1 (job_id=?)' in p for p in plan)
        assert any('SEARCH d USING COVERING INDEX dependencies_parent (dependency=?)' in p for p in plan)
    print(f'40K jobs: import={imported:.3f}s ready128={ready_seconds:.3f}s '
          f'claim128={claim_seconds:.3f}s update128={update_seconds:.3f}s')
    # Loose regression ceiling, not a hardware-specific microbenchmark target.
    assert max(ready_seconds,claim_seconds,update_seconds)<5


def test_isolated_simulation_cli(tmp_path):
    import json
    output=tmp_path/'simulation'
    env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    result=subprocess.run([sys.executable,'-m','eval_scheduler.simulation',
                           '--output',str(output),'--jobs','160','--batch-size','8'],
                          env=env,text=True,capture_output=True,check=True)
    report=json.loads((output/'report.json').read_text())
    assert json.loads(result.stdout)['status']=='passed'
    assert report['jobs']==160 and report['claim_count']==8
    assert report['readiness_before']['equal'] and report['readiness_after']['equal']
    assert all(report['checks'].values())
    assert report['finish_latency_seconds']['count']==8
    from eval_scheduler.simulation import run
    with pytest.raises(FileExistsError):run(output,jobs=160)
    assert json.loads((output/'report.json').read_text())==report


def test_user_training_pause_blocks_claim_but_allows_publication(tmp_path):
    store=SQLiteJobStore(tmp_path/'jobs.sqlite')
    store.import_jobs([
        job('train',action=Action.TRAIN_UNTIL_STEP,metadata={'user_training_pause':True}),
        job('publication'),
        job('future',deps=('train',),deps_mode='terminal'),
    ])
    assert {j.job_id for j in store.ready_jobs()}=={'publication'}
    assert not store.claim_jobs(['train'])
    assert store.claim_jobs(['publication'])
    store.update_jobs({'train':{'metadata':{'user_training_pause':False}}})
    assert store.claim_jobs(['train'])
