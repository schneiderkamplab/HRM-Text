"""One owned-client interruption with archived allowance; no server actions."""
import argparse
import copy
import json
import os
from pathlib import Path
import select
import sqlite3
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import dfm13_arena_repair_concurrency_migration as old
base=old.repair.base


def archive_interrupted(db, allowance_path):
    if allowance_path.exists():raise ValueError('Only one migration allowance')
    if db.execute("SELECT count(*) FROM attempts WHERE status='interrupted_unknown'").fetchone()[0]:
        raise ValueError('Preexisting interruption requires separate reconciliation')
    rows=db.execute("SELECT seq,stage,n,hash,record FROM attempts WHERE status='inflight' ORDER BY seq,stage,n").fetchall()
    base.write_json(allowance_path,dict(version=1,max_migrations=1,
        attempts=[list(r[:4]) for r in rows],original_records=[r[4] for r in rows],
        time=time.time(),infrastructure_only=True))
    for seq,stage,n,h,record in rows:
        db.execute("UPDATE attempts SET status='interrupted_unknown' WHERE seq=? AND stage=? AND n=? AND status='inflight'",(seq,stage,n))
    db.commit()
    return len(rows)


def migrate(root,peer,pid,archive,downstream):
    if not old.guard.terminal_ready(peer/'ledger.sqlite'):raise ValueError('Peer must be terminal')
    plan=old.repair.verify(root)
    if plan['own_per_server']!=128 or 'infrastructure_allowance' in plan:raise ValueError('Expected unmigrated128 plan')
    progress=base.load(root/'progress.json')
    if progress.get('pid')!=pid or time.time()-progress['time']>20 or not sum(progress.get('queued',[])):
        raise ValueError('No fresh queued work; do not interrupt tail')
    before=old.metrics(plan['manifest']['endpoints'])
    if not old.headroom(before):raise ValueError('Insufficient headroom')
    hashes={n:base.file_hash(root/n) for n in ('plan.json','seal.json')}
    old.refresh_downstream(downstream,root,hashes,None)
    owner=old.identity(pid,root)
    archive.mkdir(exist_ok=False)
    receipt=dict(status='preflight',owner=owner,progress=progress,metrics=before,
        graceful_drain=False,no_server_actions=True,no_admission=True,old_hashes=hashes)
    base.write_json(archive/'receipt.json',receipt)
    fd=old.pidfd_open(pid)
    try:
        if old.identity(pid,root)!=owner:raise ValueError('PID identity changed')
        # Final queue check immediately before signalling only this owned client.
        if not sum(base.load(root/'progress.json').get('queued',[])):
            raise ValueError('Queue drained; interruption cancelled')
        old.pidfd_interrupt(fd)
        if not select.select([fd],[],[],90)[0]:raise RuntimeError('Client did not exit; no escalation')
    finally:os.close(fd)
    with base.lock(root/'controller.lock'):
        if old.repair.verify(root)!=plan:raise ValueError('Plan changed during interruption')
        for name in hashes:(archive/name).write_bytes((root/name).read_bytes())
        with old.repair.readonly(root/'ledger.sqlite') as db:
            with sqlite3.connect(archive/'ledger.sqlite') as target:db.backup(target)
        receipt['backup_sha256']=base.file_hash(archive/'ledger.sqlite')
        allowance=archive/'infrastructure-allowance.json'
        with sqlite3.connect(root/'ledger.sqlite') as db:
            receipt['interrupted_count']=archive_interrupted(db,allowance)
        new=copy.deepcopy(plan)
        new.update(own_per_server=256,infrastructure_allowance=str(allowance),
            migration_allowance_count=1,work_stealing=True,actual_endpoint_recorded=True)
        paths=[allowance,Path(__file__).resolve(),ROOT/'scripts/dfm13_arena_repairs_migrated.py',
            ROOT/'scripts/dfm13_arena_migration_budget.py',ROOT/'tests/test_dfm13_arena_migration_budget.py',
            ROOT/'tests/test_dfm13_arena_safe_tail_migration.py']
        for path in paths:new['pins'][str(path)]=base.file_hash(path)
        base.write_json(root/'plan.json',new)
        base.write_json(root/'seal.json',dict(sha256=base.file_hash(root/'plan.json')))
        old.refresh_downstream(downstream,root,hashes,archive)
        old.repair.verify(root)
        receipt.update(status='sealed',new_hashes={n:base.file_hash(root/n) for n in hashes})
        base.write_json(archive/'receipt.json',receipt)
        # Bounded cancellation-settlement observation, not a per-request abort claim.
        for _ in range(20):
            try:
                observed=old.metrics(plan['manifest']['endpoints'])
                receipt['post_stop_metrics']=observed
                if old.headroom(observed,low=True):break
            except Exception as exc:receipt['metrics_error']=repr(exc)
            time.sleep(3)
    command=[sys.executable,str(ROOT/'scripts/dfm13_arena_repairs_migrated.py'),'watch','--root',str(root)]
    log=root/'client-safe-tail256.log'
    with log.open('ab') as f:
        child=subprocess.Popen(command,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,
                               env=dict(os.environ,PYTHONUNBUFFERED='1'))
    receipt.update(status='resumed',pid=child.pid,command=command,log=str(log),time=time.time())
    base.write_json(archive/'receipt.json',receipt)
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('root','peer','archive','downstream'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--pid',type=int,required=True)
    a=p.parse_args()
    with base.lock(a.root.resolve()/'migration-controller.lock'):
        migrate(a.root.resolve(),a.peer.resolve(),a.pid,a.archive.resolve(),a.downstream.resolve())
