#!/usr/bin/env python3
"""One owned TP8 server beside training; no artificial free-memory reserve."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dfm12.diagnostic_server import command_env, identity, pidfd_open, pidfd_signal
from dfm12.io import lock, write_json


def remember(record):
    # vLLM workers may rewrite their environment; the private launch session survives.
    known = {p['pid']:p for p in record['owned']}
    for process in psutil.process_iter(['pid']):
        try:
            if os.getsid(process.pid) == record['server_session']:
                item = identity(process.pid)
                if item['create_time'] >= record['created_at']:
                    known[process.pid] = item
        except (psutil.Error, OSError):
            pass
    record['owned'] = list(known.values())


def cleanup(root, record):
    actions = []
    for sig in (signal.SIGTERM, signal.SIGKILL):
        remember(record)
        for item in record['owned']:
            fd = None
            try:
                fd = pidfd_open(item['pid'])
                now = identity(item['pid'])
                if (now['start_ticks'] == item['start_ticks']
                        and now['session_id'] == record['server_session']):
                    pidfd_signal(fd, sig)
                    actions.append(dict(pid=item['pid'], signal=sig.name))
            except (psutil.Error, OSError):
                pass
            finally:
                if fd is not None:
                    os.close(fd)
        time.sleep(3)
    remember(record)
    survivors = []
    for item in record['owned']:
        try:
            if (identity(item['pid'])['start_ticks'] == item['start_ticks']
                    and psutil.Process(item['pid']).status() != psutil.STATUS_ZOMBIE):
                survivors.append(item)
        except (psutil.Error, OSError):
            pass
    result = dict(actions=actions, survivors=survivors, time=time.time())
    write_json(root / 'ownership.json', record)
    write_json(root / 'cleanup.json', result)
    return result


def memory():
    output = subprocess.check_output(['nvidia-smi', '--query-gpu=index,uuid,memory.total,memory.free',
        '--format=csv,noheader,nounits'], text=True, timeout=5)
    devices = []
    for line in output.splitlines():
        index, gpu, total, free = [v.strip() for v in line.split(',')]
        devices.append(dict(index=int(index), uuid=gpu, total_mib=int(total), free_mib=int(free)))
    if [d['index'] for d in devices] != list(range(8)):
        raise RuntimeError('Require exactly physical GPUs 0..7')
    return dict(time=time.time(), devices=devices)


def startup_fits(before):
    return all(d['free_mib'] >= d['total_mib']*.045 for d in before['devices'])


def adopt(root):
    """Replace only supervision; leave the already-ready inference process intact."""
    with lock(root / '.owner.lock'):
        record = json.loads((root / 'ownership.json').read_text())
        server = next(i for i in record['owned'] if i['pid'] == record['server_session'])
        current = identity(server['pid'])
        if current['start_ticks'] != server['start_ticks'] or current['session_id'] != record['server_session']:
            raise RuntimeError('Server identity changed; refuse adoption')
        record['supervisor'] = identity(os.getpid())
        stopping = False
        def stop(*_):
            nonlocal stopping
            stopping = True
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        reason = 'supervisor_error'
        try:
            while True:
                remember(record)
                write_json(root / 'ownership.json', record)
                if stopping or (root / 'stop.request').exists():
                    reason = 'stop_requested'; break
                try:
                    current = identity(server['pid'])
                    alive = (current['start_ticks'] == server['start_ticks']
                             and psutil.Process(server['pid']).status() != psutil.STATUS_ZOMBIE)
                except (psutil.Error, OSError):
                    alive = False
                if not alive:
                    reason = 'server_exited'; break
                try:
                    current_memory = memory()
                    write_json(root / 'memory.json', current_memory)
                except (OSError, subprocess.SubprocessError) as exc:
                    current_memory = dict(devices=[], error=repr(exc))
                ready = False
                try:
                    with urllib.request.urlopen(record['endpoint']+'/models', timeout=1) as response:
                        ready = any(m['id']=='dfm13-gemma4' for m in json.load(response)['data'])
                except Exception:
                    pass
                write_json(root / 'status.json', dict(time=time.time(),phase='ready' if ready else 'unavailable',
                    pid=server['pid'],supervisor=os.getpid(),free_memory_guard=False,
                    free_mib=[d['free_mib'] for d in current_memory['devices']]))
                time.sleep(2)
        finally:
            result = cleanup(root, record)
            write_json(root / 'status.json', dict(time=time.time(),phase='stopped',reason=reason,
                                                 survivors=result['survivors']))


def supervise(root):
    with lock(root / '.owner.lock'):
        if (root / 'ownership.json').exists():
            raise RuntimeError('Existing lifecycle; use a fresh root')
        before = memory()
        if not startup_fits(before):
            raise RuntimeError('Insufficient free memory for the 4.5% server budget')
        for port in (8810, 33100):
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', port))
        write_json(root / 'before.json', before)
        owner = uuid.uuid4().hex
        command, env = command_env(before, owner)
        for option, value in {'--served-model-name':'dfm13-gemma4', '--port':'8810',
                '--tensor-parallel-size':'8', '--gpu-memory-utilization':'.045',
                '--max-num-seqs':'16', '--max-num-batched-tokens':'2048',
                '--max-model-len':'32768'}.items():
            command[command.index(option)+1] = value
        command += ['--enable-auto-tool-choice', '--tool-call-parser', 'gemma4', '--reasoning-parser', 'gemma4']
        command += ['--no-enable-flashinfer-autotune']
        env['VLLM_PORT'] = '33100'
        for key in ('RANK','LOCAL_RANK','WORLD_SIZE','LOCAL_WORLD_SIZE','MASTER_ADDR','MASTER_PORT','GROUP_RANK','ROLE_RANK'):
            env.pop(key, None)
        stopping = False
        def stop(*_):
            nonlocal stopping
            stopping = True
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        record = dict(owner=owner, owned=[], supervisor=identity(os.getpid()), command=command,
                      training_owned=False, endpoint='http://127.0.0.1:8810/v1')
        process = None
        reason = 'supervisor_error'
        try:
            with (root / 'server.log').open('x') as log:
                process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            initial = identity(process.pid)
            record.update(server_session=process.pid, created_at=initial['create_time'], owned=[initial])
            write_json(root / 'ownership.json', record)
            started = time.monotonic()
            while True:
                current = memory()
                write_json(root / 'memory.json', current)
                remember(record)
                write_json(root / 'ownership.json', record)
                if process.poll() is not None:
                    reason = 'server_exited'; break
                if stopping or (root / 'stop.request').exists():
                    reason = 'stop_requested'; break
                ready = False
                try:
                    with urllib.request.urlopen(record['endpoint']+'/models',timeout=1) as response:
                        ready = any(m['id']=='dfm13-gemma4' for m in json.load(response)['data'])
                except Exception:
                    pass
                write_json(root / 'status.json', dict(time=time.time(), phase='ready' if ready else 'starting',
                    pid=process.pid, supervisor=os.getpid(), free_memory_guard=False,
                    free_mib=[d['free_mib'] for d in current['devices']]))
                if not ready and time.monotonic()-started > 1200:
                    reason = 'startup_timeout'; break
                time.sleep(2)
        finally:
            result = cleanup(root, record) if process is not None else dict(survivors=[])
            write_json(root / 'status.json', dict(time=time.time(), phase='stopped', reason=reason,
                                                survivors=result['survivors']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--supervise', action='store_true')
    parser.add_argument('--adopt', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    if args.adopt:
        adopt(root)
    elif args.supervise:
        supervise(root)
    else:
        root.mkdir(parents=True, exist_ok=False)
        with (root / 'supervisor.log').open('x') as log:
            p = subprocess.Popen([sys.executable, '-u', __file__, '--root', str(root), '--supervise'],
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        receipt = dict(supervisor=identity(p.pid), root=str(root), single_tp8_server=True)
        write_json(root / 'launch.json', receipt)
        print(json.dumps(receipt))
