"""Retired interruption prototype; CLI disabled pending separate infra retry budget."""
import argparse
import copy
import ctypes
import json
import os
from pathlib import Path
import select
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import dfm13_arena_repairs as repair
from scripts import dfm13_arena_export_readiness as guard


def pidfd_open(pid):
    libc=ctypes.CDLL(None,use_errno=True)
    libc.pidfd_open.argtypes=[ctypes.c_int,ctypes.c_uint]
    fd=libc.pidfd_open(pid,0)
    if fd<0:raise OSError(ctypes.get_errno(),os.strerror(ctypes.get_errno()))
    return fd


def pidfd_interrupt(fd):
    libc=ctypes.CDLL(None,use_errno=True)
    libc.pidfd_send_signal.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_void_p,ctypes.c_uint]
    if libc.pidfd_send_signal(fd,signal.SIGINT,None,0)<0:
        raise OSError(ctypes.get_errno(),os.strerror(ctypes.get_errno()))


def increased(plan):
    if plan['own_per_server']!=128:
        raise ValueError('Expected unchanged128/server plan')
    result=copy.deepcopy(plan)
    result['own_per_server']=256
    assert [k for k in result if result[k]!=plan[k]]==['own_per_server']
    return result


def identity(pid,root):
    proc=Path('/proc')/str(pid)
    argv=[x.decode() for x in (proc/'cmdline').read_bytes().split(b'\0') if x]
    cwd=(proc/'cwd').resolve()
    script=(Path(argv[1]) if len(argv)>1 else Path('/invalid'))
    if not script.is_absolute():script=cwd/script
    if (len(argv)!=5 or Path(argv[0]).resolve()!=Path(sys.executable).resolve()
            or script.resolve()!=ROOT/'scripts/dfm13_arena_repairs.py'
            or argv[2:4]!=['watch','--root'] or Path(argv[4]).resolve()!=root.resolve()):
        raise ValueError('Owned client command mismatch')
    # starttime is field22; split after comm, whose contents can include spaces.
    start=(proc/'stat').read_text().rsplit(')',1)[1].split()[19]
    return dict(pid=pid,argv=argv,start_ticks=start)


def metrics(endpoints):
    result=[]
    for endpoint in endpoints:
        values={}
        text=urllib.request.urlopen(endpoint.removesuffix('/v1')+'/metrics',timeout=5).read().decode()
        for line in text.splitlines():
            if line and not line.startswith('#'):
                name=line.split('{')[0].split()[0]
                if name in ('vllm:num_requests_running','vllm:num_requests_waiting','vllm:kv_cache_usage_perc'):
                    values[name]=values.get(name,0)+float(line.rsplit(' ',1)[1])
        result.append(dict(endpoint=endpoint,time=time.time(),values=values))
    return result


def headroom(samples,low=False):
    return len(samples)==8 and all(
        time.time()-s['time']<15 and
        s['values'].get('vllm:num_requests_waiting',1)==0 and
        s['values'].get('vllm:kv_cache_usage_perc',1)<(.20 if low else .80) and
        s['values'].get('vllm:num_requests_running',513)<=(16 if low else 256)
        for s in samples)


def state(db):
    return dict(counts={t:db.execute(f'SELECT count(*) FROM {t}').fetchone()[0]
                       for t in ('accepted','rejected','needs_review')},
                attempts=db.execute('SELECT stage,status,count(*) FROM attempts GROUP BY stage,status').fetchall(),
                interrupted=db.execute("SELECT seq,stage,n,hash FROM attempts WHERE status='inflight' ORDER BY seq,stage,n").fetchall())


def refresh_downstream(path,root,old_hashes,archive):
    if path is None:return
    if (path/'manifest.json').exists():
        raise ValueError('Downstream recovery already materialized; refuse migration')
    value=repair.base.load(path/'plan.json')
    if repair.base.file_hash(path/'plan.json')!=repair.base.load(path/'plan-seal.json')['sha256']:
        raise ValueError('Downstream seal drift')
    for name,old in old_hashes.items():
        if value['pins'].get(str(root/name))!=old:
            raise ValueError('Downstream source pin mismatch')
    if archive is not None:
        target=archive/'downstream';target.mkdir()
        for name in ('plan.json','plan-seal.json'):
            (target/name).write_bytes((path/name).read_bytes())
        for name in old_hashes:value['pins'][str(root/name)]=repair.base.file_hash(root/name)
        repair.base.write_json(path/'plan.json',value)
        repair.base.write_json(path/'plan-seal.json',dict(sha256=repair.base.file_hash(path/'plan.json')))


def migrate(root,peer,pid,archive,downstream=None):
    if not guard.terminal_ready(peer/'ledger.sqlite'):
        raise ValueError('Peer not terminal and unlocked')
    plan=repair.verify(root);new=increased(plan)
    old_hashes={n:repair.base.file_hash(root/n) for n in ('plan.json','seal.json')}
    refresh_downstream(downstream,root,old_hashes,None)
    before=metrics(plan['manifest']['endpoints'])
    if not headroom(before):raise ValueError('Insufficient fresh headroom')
    owner=identity(pid,root)
    archive.mkdir(exist_ok=False)
    receipt=dict(status='preflight_passed',time=time.time(),owner=owner,before_metrics=before,
                 old_hashes=old_hashes,source=str(root),peer=str(peer),
                 helper_sha256=repair.base.file_hash(Path(__file__)),
                 tests_sha256=repair.base.file_hash(ROOT/'tests/test_dfm13_arena_repair_concurrency_migration.py'),
                 graceful_drain=False,unknown_attempts_preserved=True,no_server_actions=True)
    repair.base.write_json(archive/'receipt.json',receipt)
    fd=pidfd_open(pid)
    try:
        if identity(pid,root)!=owner:raise ValueError('Process identity changed')
        pidfd_interrupt(fd)
        if not select.select([fd],[],[],90)[0]:
            raise RuntimeError('Owned client did not exit; no escalation or second launcher')
    finally:os.close(fd)
    with repair.base.lock(root/'controller.lock'):
        if repair.verify(root)!=plan:raise ValueError('Plan changed during stop')
        for name in old_hashes:(archive/name).write_bytes((root/name).read_bytes())
        with repair.readonly(root/'ledger.sqlite') as db:
            receipt['before_ledger']=state(db)
            with sqlite3.connect(archive/'ledger.sqlite') as target:db.backup(target)
        receipt['ledger_backup_sha256']=repair.base.file_hash(archive/'ledger.sqlite')
        # Connections were closed, but no per-request abort acknowledgement exists.
        # Preserve all unknowns and the existing max3 policy; never invent completion.
        stable=0
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            try:
                observed=metrics(plan['manifest']['endpoints'])
                stable=stable+1 if headroom(observed,low=True) else 0
                receipt['after_stop_metrics']=observed
            except Exception as exc:
                stable=0;receipt['metrics_error']=repr(exc)
            if stable>=3:break
            time.sleep(3)
        if stable>=3:
            repair.base.write_json(root/'plan.json',new)
            repair.base.write_json(root/'seal.json',dict(sha256=repair.base.file_hash(root/'plan.json')))
            refresh_downstream(downstream,root,old_hashes,archive)
            repair.verify(root)
            receipt['own_per_server']=256
        else:
            # Resume original bounded work instead of leaving an idle paused campaign.
            receipt['own_per_server']=128
            receipt['fallback_reason']='No sustained low-load confirmation; unchanged original plan'
        with repair.readonly(root/'ledger.sqlite') as db:
            if state(db)!=receipt['before_ledger']:raise ValueError('Ledger changed under exclusive lock')
        receipt['new_hashes']={n:repair.base.file_hash(root/n) for n in old_hashes}
        receipt['status']='sealed_for_single_writer_resume'
        repair.base.write_json(archive/'receipt.json',receipt)
    command=[sys.executable,str(ROOT/'scripts/dfm13_arena_repairs.py'),'watch','--root',str(root)]
    log=root/f"client-concurrency{receipt['own_per_server']}-{archive.name}.log"
    with log.open('ab') as output:
        child=subprocess.Popen(command,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,
                               start_new_session=True,env=dict(os.environ,PYTHONUNBUFFERED='1'))
    receipt.update(status='resumed',pid=child.pid,command=command,log=str(log),resumed=time.time())
    repair.base.write_json(archive/'receipt.json',receipt)
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        if child.poll() is not None:
            raise RuntimeError('Resumed client exited; inspect saved log, do not duplicate launch')
        progress=repair.base.load(root/'progress.json') if (root/'progress.json').exists() else {}
        if progress.get('pid')==child.pid and any(progress.get('active',[])):
            with repair.readonly(root/'ledger.sqlite') as db:
                db.execute('ATTACH DATABASE ? AS saved',('file:'+str(archive/'ledger.sqlite')+'?mode=ro',))
                for table in ('accepted','rejected','needs_review'):
                    changed=db.execute(f'SELECT count(*) FROM saved.{table} s LEFT JOIN main.{table} m ON m.seq=s.seq WHERE m.seq IS NULL OR m.record!=s.record').fetchone()[0]
                    if changed:raise ValueError('Previously final rows changed after resume')
                changed=db.execute("SELECT count(*) FROM saved.attempts s LEFT JOIN main.attempts m ON m.seq=s.seq AND m.stage=s.stage AND m.n=s.n WHERE s.status='complete' AND (m.seq IS NULL OR m.status!='complete' OR m.record!=s.record OR m.hash!=s.hash)").fetchone()[0]
                if changed:raise ValueError('Completed stage cache changed after resume')
            receipt.update(status='progress_verified',progress=progress,completed_rows_and_stages_preserved=True)
            repair.base.write_json(archive/'receipt.json',receipt)
            break
        time.sleep(3)
    print(json.dumps(receipt),flush=True)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--peer',type=Path,required=True)
    parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--downstream',type=Path)
    parser.add_argument('--wait',action='store_true')
    args=parser.parse_args()
    parser.error('Migration disabled: interrupted attempts consume the original max3 budget. '
                 'Keep128/server until separately bounded infrastructure recovery is implemented.')
    root,peer=args.root.resolve(),args.peer.resolve()
    with repair.base.lock(root/'migration-controller.lock'):
        if args.wait:
            while not guard.terminal_ready(peer/'ledger.sqlite'):
                identity(args.pid,root)
                time.sleep(15)
        migrate(root,peer,args.pid,args.archive.resolve(),args.downstream.resolve() if args.downstream else None)


if __name__=='__main__':main()
