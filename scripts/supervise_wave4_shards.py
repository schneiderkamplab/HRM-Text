"""Explicitly activated eight-shard client supervisor; never controls servers."""
import argparse
import importlib.util
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time

import psutil

from dfm12.io import file_hash, load, lock, write_json
from dfm12.wave4_shard_prepare import verify_output

THREAD_CAPS = dict(RAYON_NUM_THREADS='2', OMP_NUM_THREADS='1',
                   MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')


def command(root, index):
    return [sys.executable, '-u', '-m', 'dfm12.wave4_shard_runtime',
            '--root', str(root/f'shard-{index}')]


def aggregate(root, shards):
    groups = []
    for shard in shards:
        path = root/f"shard-{shard['worker']}"/'jobs.sqlite'
        with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            rows = [dict(r) for r in db.execute('SELECT * FROM groups')]
        if {r['language'] for r in rows} != set(shard['languages']):
            raise ValueError('Shard language ownership drift')
        groups.extend(rows)
    keys = [(r['language'], r['family']) for r in groups]
    if len(keys) != len(set(keys)):
        raise ValueError('Overlapping shard groups')
    return dict(time=time.time(), groups=groups, accepted=sum(r['accepted'] for r in groups),
                active=sum(r['active'] for r in groups), target=sum(r['target'] for r in groups),
                attempts=sum(r['attempts'] for r in groups))


def supervise(root, expected_hash):
    root = root.resolve()
    receipt = verify_output(root)
    if receipt.get('target') != 770000 or receipt.get('expected_target') != 770000:
        raise ValueError('Exact 770000 campaign target required')
    source = Path(receipt['source_root'])
    module = importlib.util.find_spec('dfm12.wave4_shard_runtime')
    if module is None or file_hash(module.origin) != expected_hash:
        raise ValueError('Frozen shard runtime required')
    with lock(source/'controller.lock'), lock(root/'supervisor.lock'):
        if (root/'supervisor-launch.json').exists():
            raise ValueError('Prior launch exists; explicit recovery required, never automatic replay')
        if file_hash(source/'manifest.json') != receipt['source_manifest_sha256']:
            raise ValueError('Source manifest changed since preparation')
        from dfm12.wave4_compact_handoff import verify_independent_launch
        verify_independent_launch(source)
        with sqlite3.connect((source/'jobs.sqlite').as_uri()+'?mode=ro', uri=True) as db:
            if db.execute('SELECT coalesce(sum(active),0) FROM groups').fetchone()[0] or db.execute(
                    "SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]:
                raise ValueError('Original controller active')
            if db.execute('SELECT count(*) FROM jobs').fetchone()[0] != receipt['source_job_count']:
                raise ValueError('Source advanced since preparation')
        env = dict(os.environ, **THREAD_CAPS)
        pins = dict(load(source/'manifest.json')['implementation_pins'])
        import dfm12.wave4_shard_prepare as preparation
        pins[str(Path(module.origin).resolve())] = expected_hash
        pins[str(Path(preparation.__file__).resolve())] = file_hash(preparation.__file__)
        write_json(root/'shard-runtime.json', dict(runtime_module='dfm12.wave4_shard_runtime',
            launch_authorized=True, prepared_sha256=file_hash(root/'prepared.json'),
            implementation_pins=pins))
        from dfm12.wave4_shard_runtime import verify_partition
        for shard in receipt['shards']:
            verify_partition(root/f"shard-{shard['worker']}")
        if file_hash(module.origin) != expected_hash:
            raise ValueError('Runtime changed during preflight')
        children = []
        stopping = False
        def stop_owned(*_):
            nonlocal stopping
            if stopping:
                return
            stopping = True
            for child in children:
                if child.poll() is None:
                    child.send_signal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, stop_owned)
        signal.signal(signal.SIGINT, stop_owned)
        write_json(root/'activation.json', dict(runtime_sha256=expected_hash,
            runtime_module='dfm12.wave4_shard_runtime', user_authorized=True,
            thread_caps=THREAD_CAPS, concurrency_per_endpoint=768,
            no_server_changes=True, time=time.time()))
        try:
            for shard in receipt['shards']:
                if stopping:
                    break
                with (root/f"shard-{shard['worker']}"/'runner.log').open('ab', buffering=0) as log:
                    children.append(subprocess.Popen(command(root,shard['worker']), env=env,
                        stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
            identities = [dict(pid=p.pid, create_time=psutil.Process(p.pid).create_time(), command=p.args) for p in children]
            write_json(root/'supervisor-launch.json', dict(pid=os.getpid(),
                create_time=psutil.Process().create_time(), children=identities))
            write_json(source/'progress-redirect.json', dict(time=time.time(),
                phase='redirected_to_language_shards', progress=str(root/'progress.json'),
                launch=str(root/'supervisor-launch.json'), original_ledger_frozen=True))
            while any(p.poll() is None for p in children):
                state = aggregate(root,receipt['shards'])
                state.update(phase='draining' if stopping else 'running',
                             children=[dict(pid=p.pid,exit_code=p.poll()) for p in children])
                write_json(root/'progress.json',state)
                if any(p.poll() not in (None,0) for p in children):
                    stop_owned()
                time.sleep(5)
        finally:
            stop_owned()
            for child in children:
                child.wait()
        state = aggregate(root,receipt['shards'])
        complete = (len(children)==8 and all(p.returncode==0 for p in children)
                    and state['active']==0 and state['accepted']==state['target'])
        state.update(phase='complete' if complete else 'stopped_or_failed', success=complete,
                     exits=[p.returncode for p in children], no_automatic_restart=True)
        write_json(root/'progress.json',state)
        write_json(root/'terminal.json',state)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--runtime-sha256', required=True)
    args=parser.parse_args()
    supervise(args.root,args.runtime_sha256)
