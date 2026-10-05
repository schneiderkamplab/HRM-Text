"""Supervise one explicitly authorized group rebalance, without server control."""
from contextlib import ExitStack
import argparse
import importlib
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time

import psutil

from dfm12.io import file_hash,load,lock,write_json
from dfm12.wave4_shard_prepare import verify_output
from scripts.supervise_wave4_shards import THREAD_CAPS


def aggregate(root,shards):
    groups=[]
    for shard in shards:
        with sqlite3.connect((root/f"shard-{shard['worker']}"/'jobs.sqlite').as_uri()+'?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row
            rows=[dict(r) for r in db.execute('SELECT * FROM groups')]
        if {(r['language'],r['family']) for r in rows} != {tuple(k) for k in shard['groups']}:
            raise ValueError('Group ownership drift')
        groups.extend(rows)
    if len(groups)!=len({(r['language'],r['family']) for r in groups}):raise ValueError('Overlapping groups')
    return dict(time=time.time(),groups=groups,**{k:sum(r[k] for r in groups) for k in ('accepted','target','active','attempts')})


def supervise(root,module_name,expected_hash):
    root=root.resolve();receipt=verify_output(root)
    if receipt['version']!=2 or receipt['target']!=770000:raise ValueError('Explicit group rebalance required')
    predecessor=Path(receipt['predecessor_root']);source=Path(receipt['source_root'])
    module=importlib.import_module(module_name)
    if file_hash(module.__file__)!=expected_hash:raise ValueError('Runtime pin mismatch')
    with ExitStack() as stack:
        for path in (source/'controller.lock',predecessor/'supervisor.lock',root/'supervisor.lock'):
            stack.enter_context(lock(path))
        for i in range(8):stack.enter_context(lock(predecessor/f'shard-{i}'/'controller.lock'))
        if (root/'supervisor-launch.json').exists():raise ValueError('Prior launch requires explicit recovery')
        old=load(predecessor/'prepared.json')
        # Frozen predecessor evidence, not its obsolete prelaunch DB hashes.
        if file_hash(predecessor/'shard-runtime.json')!=receipt['predecessor_runtime_sha256']:
            raise ValueError('Predecessor runtime seal changed')
        from dfm12.wave4_shard_runtime import verify_partition
        before=dict(accepted=0,target=0,active=0,attempts=0)
        for i in range(8):
            folder=predecessor/f'shard-{i}';verify_partition(folder)
            with sqlite3.connect((folder/'jobs.sqlite').as_uri()+'?mode=ro',uri=True) as db:
                values=db.execute('SELECT sum(accepted),sum(target),sum(active),sum(attempts) FROM groups').fetchone()
                for k,v in zip(before,values):before[k]+=v
        if before!=receipt['preserved_totals'] or before['active']:raise ValueError('Predecessor advanced or active')
        import dfm12.wave4_group_rebalance as migration
        pins=dict(load(predecessor/'shard-runtime.json')['implementation_pins'])
        for path in (module.__file__,migration.__file__,__file__):pins[str(Path(path).resolve())]=file_hash(path)
        write_json(root/'shard-runtime.json',dict(runtime_module=module_name,launch_authorized=True,
            prepared_sha256=file_hash(root/'prepared.json'),implementation_pins=pins))
        for shard in receipt['shards']:module.verify_partition(root/f"shard-{shard['worker']}")
        if file_hash(module.__file__)!=expected_hash:raise ValueError('Runtime changed during preflight')
        env=dict(os.environ,**THREAD_CAPS);children=[];stopping=False
        def stop(*_):
            nonlocal stopping
            if stopping:return
            stopping=True
            for p in children:
                if p.poll() is None:p.send_signal(signal.SIGTERM)
        signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
        write_json(root/'activation.json',dict(runtime_module=module_name,runtime_sha256=expected_hash,
            baseline=before,thread_caps=THREAD_CAPS,concurrency_per_endpoint=768,time=time.time()))
        try:
            for shard in receipt['shards']:
                if stopping:break
                folder=root/f"shard-{shard['worker']}"
                with (folder/'runner.log').open('ab',buffering=0) as log:
                    children.append(subprocess.Popen([sys.executable,'-u','-m',module_name,'--root',str(folder)],
                        env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True))
            write_json(root/'supervisor-launch.json',dict(pid=os.getpid(),create_time=psutil.Process().create_time(),
                children=[dict(pid=p.pid,create_time=psutil.Process(p.pid).create_time(),command=p.args) for p in children]))
            for parent in (source,predecessor):
                write_json(parent/'progress-redirect.json',dict(phase='redirected_to_group_shards',
                    progress=str(root/'progress.json'),launch=str(root/'supervisor-launch.json'),time=time.time()))
            while any(p.poll() is None for p in children):
                state=aggregate(root,receipt['shards'])
                state.update(phase='draining' if stopping else 'running',baseline_accepted=before['accepted'],
                             children=[dict(pid=p.pid,exit_code=p.poll()) for p in children])
                write_json(root/'progress.json',state)
                if any(p.poll() not in (None,0) for p in children):stop()
                time.sleep(5)
        finally:
            stop()
            for p in children:p.wait()
        state=aggregate(root,receipt['shards'])
        success=len(children)==8 and all(p.returncode==0 for p in children) and state['active']==0
        state.update(phase='runnable_pass_finished' if success else 'stopped_or_failed',
            runnable_pass_success=success,full_target_complete=success and state['accepted']==770000,
            exits=[p.returncode for p in children],no_automatic_replay=True)
        write_json(root/'progress.json',state);write_json(root/'terminal.json',state)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--runtime-module',default='dfm12.wave4_group_runtime')
    p.add_argument('--runtime-sha256',required=True)
    a=p.parse_args();supervise(a.root,a.runtime_module,a.runtime_sha256)
