"""Offline, locked et/ca-only target increase with exact-process soft drain."""
import argparse
import copy
import ctypes
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import signal
import sqlite3
import time

import yaml

from . import european_synthetic_campaign as campaign
from .io import atomic, file_hash, load, lock, write_json

PYTHON = '/home/ucloud/miniforge3/envs/hrm/bin/python'
FILES = ('config.json', 'manifest.json', 'seal.json')


def pidfd_open(pid):
    # This environment's Python lacks pidfd bindings; glibc exposes them.
    libc=ctypes.CDLL(None,use_errno=True)
    function=libc.pidfd_open
    function.argtypes=[ctypes.c_int,ctypes.c_uint]
    function.restype=ctypes.c_int
    fd=function(pid,0)
    if fd < 0:
        error=ctypes.get_errno()
        raise OSError(error,os.strerror(error))
    return fd


def pidfd_signal(fd, sig):
    libc=ctypes.CDLL(None,use_errno=True)
    function=libc.pidfd_send_signal
    function.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_void_p,ctypes.c_uint]
    function.restype=ctypes.c_int
    if function(fd,sig,None,0) < 0:
        error=ctypes.get_errno()
        raise OSError(error,os.strerror(error))


def expected_command(root):
    return [PYTHON, '-B', '-u', '-m', 'dfm12.european_synthetic_campaign', 'run',
        '--root', str(Path(root).resolve()), '--concurrency-per-server', '16',
        '--timeout', '600', '--max-kv-cache-utilization', '0.90']


def inspect_process(pid, root, proc=Path('/proc')):
    root = Path(root).resolve()
    process = proc / str(pid)
    argv = process.joinpath('cmdline').read_bytes().rstrip(b'\0').decode().split('\0')
    if argv != expected_command(root):
        raise ValueError('Exact controller command mismatch; no signal authorized')
    runtime = load(root / 'runtime.json')
    if (runtime['pid'] != pid or runtime['concurrency_per_server'] != 16
            or runtime['timeout'] != 600 or runtime['max_kv_cache_utilization'] != .90):
        raise ValueError('Runtime receipt mismatch; no signal authorized')
    stat = process.joinpath('stat').read_text().rsplit(')', 1)[1].split()
    return dict(pid=pid, command=argv, start_ticks=stat[19], root=str(root),
                cwd=str(process.joinpath('cwd').resolve()), checked=time.time())


def drain(pid, root, receipt, timeout=1500):
    """Signal only a pidfd whose exact argv/runtime identity was rechecked."""
    receipt = Path(receipt)
    if receipt.exists():
        raise ValueError('Drain receipt already exists; inspect before retrying')
    identity = inspect_process(pid, root)
    campaign.verify(root)
    fd = pidfd_open(pid)
    try:
        if inspect_process(pid, root)['start_ticks'] != identity['start_ticks']:
            raise ValueError('PID identity changed')
        write_json(receipt, dict(identity, phase='signal_pending', signal='SIGTERM', timeout=timeout))
        pidfd_signal(fd, signal.SIGTERM)
        write_json(receipt, dict(identity, phase='draining', signal='SIGTERM', signaled=time.time()))
        if not select.select([fd], [], [], timeout)[0]:
            write_json(receipt, dict(identity, phase='drain_timeout', signal='SIGTERM', finished=time.time()))
            raise TimeoutError('Controller still draining; no escalation or migration performed')
        with lock(Path(root) / 'controller.lock'):
            with sqlite3.connect((Path(root)/'jobs.sqlite').resolve().as_uri()+'?mode=ro', uri=True) as db:
                active = db.execute('SELECT SUM(active) FROM groups').fetchone()[0]
                running = db.execute("SELECT COUNT(*) FROM jobs WHERE status='running'").fetchone()[0]
            if active or running:
                raise ValueError('Controller exited without a clean drain; migration refused')
        result = dict(identity, phase='drained', signal='SIGTERM', finished=time.time(), active=active, running=running)
        write_json(receipt, result)
        return result
    finally:
        os.close(fd)


def plan(old, new):
    expected = copy.deepcopy(old)
    if old['languages'].get('et') != 2 or old['languages'].get('ca') != 2:
        raise ValueError('Require original et/ca divisors of two; no repeated migration')
    expected['languages'].update(et=1, ca=1)
    if new != expected:
        raise ValueError('Only et/ca divisor changes from two to one are authorized')
    before = {(r['language'],r['family']):r['accepted_target'] for r in campaign.milestone_targets(old)}
    after = {(r['language'],r['family']):r['accepted_target'] for r in campaign.milestone_targets(new)}
    changes = [dict(language=k[0], family=k[1], old=before[k], new=v) for k,v in after.items() if before[k]!=v]
    if (sum(before.values()) != 420000 or sum(after.values()) != 490000 or len(changes) != 12
            or any(c['language'] not in ('et','ca') or c['new'] != c['old']*2 for c in changes)):
        raise ValueError('Expected twelve doubled targets and 420K -> 490K total')
    return changes


def database_snapshot(db, ledger=False):
    """Streaming logical hashes exclude only the two authorized mutable fields."""
    result = {}
    names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    for table in names:
        quoted = '"' + table.replace('"','""') + '"'
        columns = [r[1] for r in db.execute(f'PRAGMA table_info({quoted})')]
        if ledger and table == 'groups':
            columns.remove('target')
        selected = ','.join('"'+c.replace('"','""')+'"' for c in columns)
        where = " WHERE key != 'manifest_sha256'" if ledger and table == 'metadata' else ''
        h, count = hashlib.sha256(), 0
        for row in db.execute(f'SELECT {selected} FROM {quoted}{where} ORDER BY {selected}'):
            h.update(json.dumps(row,ensure_ascii=False,separators=(',',':')).encode()+b'\n')
            count += 1
        result[table] = dict(rows=count, sha256=h.hexdigest())
    return result


def backup_database(source, destination):
    with sqlite3.connect(Path(source).resolve().as_uri()+'?mode=ro',uri=True) as src:
        with sqlite3.connect(destination) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('SQLite backup integrity failure')


def migrate(root, config_path, backup, drain_receipt):
    root, backup = Path(root).resolve(), Path(backup).resolve()
    drained = load(drain_receipt)
    if drained.get('phase') != 'drained' or drained.get('root') != str(root):
        raise ValueError('Verified clean-drain receipt required')
    with lock(root/'controller.lock'):
        original = campaign.verify(root)
        old_config = load(root/'config.json')
        new_config = yaml.safe_load(Path(config_path).read_text())
        changes = plan(old_config, new_config)
        with sqlite3.connect(root/'jobs.sqlite', isolation_level=None) as db:
            if db.execute('SELECT SUM(active) FROM groups').fetchone()[0] or db.execute(
                    "SELECT 1 FROM jobs WHERE status='running' LIMIT 1").fetchone():
                raise ValueError('Ledger has active work; clean drain required')
            before = database_snapshot(db, ledger=True)
            selections = root/'spec-selections.sqlite'
            with sqlite3.connect(selections.as_uri()+'?mode=ro',uri=True) as specdb:
                selection_before = database_snapshot(specdb)
            backup.mkdir(parents=True, exist_ok=False)
            for name in FILES:
                shutil.copy2(root/name, backup/name)
            backup_database(root/'jobs.sqlite',backup/'jobs.sqlite')
            backup_database(selections,backup/'spec-selections.sqlite')
            for name in ('runtime.json','progress.json','admission-status.json'):
                if (root/name).exists():
                    shutil.copy2(root/name,backup/name)
            receipt = dict(schema='european-et-ca-target-migration-v1', phase='backed_up', root=str(root),
                drain_receipt=str(Path(drain_receipt).resolve()), changes=changes,
                old_target=420000,new_target=490000,helper_sha256=file_hash(__file__),
                config_source_sha256=file_hash(config_path), state_before=before,
                selections_before=selection_before,
                backups={p.name:file_hash(p) for p in backup.iterdir() if p.is_file()})
            write_json(backup/'receipt.json',receipt)
            try:
                db.execute('BEGIN IMMEDIATE')
                for c in changes:
                    changed=db.execute('UPDATE groups SET target=? WHERE language=? AND family=? AND target=?',
                        (c['new'],c['language'],c['family'],c['old'])).rowcount
                    if changed != 1:
                        raise ValueError('Ledger target changed since verified plan')
                updated=copy.deepcopy(original)
                write_json(root/'config.json',new_config)
                updated['target']=490000
                updated['input_pins']['config.json']=file_hash(root/'config.json')
                write_json(root/'manifest.json',updated)
                seal=file_hash(root/'manifest.json')
                write_json(root/'seal.json',dict(manifest_sha256=seal))
                if db.execute("UPDATE metadata SET value=? WHERE key='manifest_sha256'",(seal,)).rowcount != 1:
                    raise ValueError('Missing SQLite campaign seal')
                if database_snapshot(db,ledger=True) != before:
                    raise ValueError('Unauthorized ledger state change')
                db.execute('COMMIT')
                with sqlite3.connect(selections.as_uri()+'?mode=ro',uri=True) as specdb:
                    if database_snapshot(specdb) != selection_before:
                        raise ValueError('Source selection/cursor state changed')
                campaign.verify(root)
                receipt.update(phase='complete',finished=time.time(),manifest_sha256=seal,
                    preserved_implementation_pins=updated['implementation_pins']==original['implementation_pins'],
                    preserved_external_pins=updated['external_pins']==original['external_pins'],
                    state_after=database_snapshot(db,ledger=True),selections_unchanged=True)
                write_json(backup/'receipt.json',receipt)
            except BaseException as exc:
                if db.in_transaction:
                    db.execute('ROLLBACK')
                with sqlite3.connect(backup/'jobs.sqlite') as saved:
                    saved.backup(db)
                for name in FILES:
                    with atomic(root/name) as handle:
                        handle.write((backup/name).read_text())
                receipt.update(phase='rolled_back',error=repr(exc),finished=time.time())
                write_json(backup/'receipt.json',receipt)
                raise
            return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('inspect','drain','migrate'))
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--pid',type=int)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--backup',type=Path)
    parser.add_argument('--config',type=Path,default=campaign.CONFIG)
    args=parser.parse_args()
    if args.command in ('inspect','drain'):
        if args.pid is None:
            parser.error('inspect/drain requires --pid')
        result=inspect_process(args.pid,args.root) if args.command=='inspect' else drain(args.pid,args.root,args.receipt)
    else:
        if args.backup is None:
            parser.error('migrate requires --backup')
        result=migrate(args.root,args.config,args.backup,args.receipt)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
