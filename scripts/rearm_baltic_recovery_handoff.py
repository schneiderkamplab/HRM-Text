"""Explicit offline pin upgrade after Baltic technical migration and restart."""
import json
import argparse
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

import psutil

from dfm12 import wave4_compact_handoff as handoff
from dfm12.io import file_hash, load, lock, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baltic384-migration', type=Path)
    parser.add_argument('--wave4-768', action='store_true')
    parser.add_argument('--baltic768-migration', type=Path)
    args = parser.parse_args()
    upgrade384 = args.baltic384_migration is not None
    suffix = 'baltic768' if args.baltic768_migration else '768-async' if args.wave4_768 else '384' if upgrade384 else 'recovery'
    root = Path('data/dfm13/wave4/synthetic-compact-after-baltic-20261004-v2').resolve()
    recovery = Path('data/dfm13/baltic/compact-empty-rationale-recovery-20261004-v1').resolve()
    with lock(root/'handoff.lock'), lock(root/'controller.lock'):
        queue = load(root/'handoff.json')
        parent = Path(queue['baltic'])
        if not args.wave4_768:
            migration = load(args.baltic768_migration or (args.baltic384_migration if upgrade384 else recovery/'migration.json'))
            assert migration['manifest_sha256'] == file_hash(parent/'manifest.json')
        handoff.baltic_proof_controller(parent)
        runtime = load(parent/'runtime.json')
        client = psutil.Process(runtime['pid'])
        assert client.status() != psutil.STATUS_ZOMBIE
        expected_module = ('dfm12.baltic_concurrency768' if args.baltic768_migration else
                           'dfm12.baltic_zero_spacing' if args.wave4_768 else
                           'dfm12.baltic_concurrency384' if upgrade384 else 'dfm12.compact_keep_recovery')
        assert handoff.baltic_client_module(parent) == expected_module
        assert expected_module in client.cmdline()
        assert handoff.inspect_baltic(parent)['state'] == 'waiting'
        assert not (root/'launch-intent.json').exists()
        archive = root/f'pre-{suffix}-rearm'
        assert not archive.exists(), 'Existing upgrade journal: inspect before retry'
        manifest = load(root/'manifest.json')
        old_sha = file_hash(root/'manifest.json')
        assert old_sha == queue['wave4_manifest_sha256'] == load(root/'seal.json')['manifest_sha256']
        own = str(Path(handoff.__file__).resolve())
        assert manifest['implementation_pins'][own] == queue['handoff_implementation_sha256']
        for field in ('implementation_pins', 'external_pins', 'input_pins'):
            for path, sha in manifest.get(field, {}).items():
                if field == 'implementation_pins' and path == own:
                    continue
                target = root/path if field == 'input_pins' else Path(path)
                assert file_hash(target) == sha, f'Unrelated pin drift: {path}'
        with sqlite3.connect(root/'jobs.sqlite') as db:
            assert db.execute('SELECT count(*) FROM jobs').fetchone()[0] == 0
            assert db.execute('SELECT sum(active) FROM groups').fetchone()[0] == 0
            assert db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()[0] == old_sha
            archive.mkdir()
            for name in ('manifest.json', 'seal.json', 'handoff.json', 'handoff-status.json'):
                if (root/name).exists():
                    write_json(archive/name, load(root/name))
            manifest['implementation_pins'][own] = file_hash(own)
            from dfm12 import compact_keep_recovery, compact_keep_rationale
            for module in (compact_keep_recovery, compact_keep_rationale):
                path = Path(module.__file__).resolve()
                manifest['implementation_pins'][str(path)] = file_hash(path)
            if upgrade384:
                from dfm12 import baltic_concurrency384
                path = Path(baltic_concurrency384.__file__).resolve()
                manifest['implementation_pins'][str(path)] = file_hash(path)
            if args.baltic768_migration:
                from dfm12 import baltic_concurrency768
                path = Path(baltic_concurrency768.__file__).resolve()
                manifest['implementation_pins'][str(path)] = file_hash(path)
            if args.wave4_768:
                from dfm12 import baltic_async_io, baltic_io_runtime, baltic_zero_spacing, wave4_async_runtime
                for module in (baltic_async_io, baltic_io_runtime, baltic_zero_spacing, wave4_async_runtime):
                    path = Path(module.__file__).resolve()
                    manifest['implementation_pins'][str(path)] = file_hash(path)
                manifest.update(max_concurrency_per_server=768, default_concurrency_per_server=768,
                    io_runtime_module='dfm12.wave4_async_runtime', admission_spacing_seconds=0,
                    authorization='User2026-10-04:770K W4 after Baltic completion and audit;768/server, zero fixed spacing, asynchronous I/O')
            write_json(root/'manifest.json', manifest)
            sha = file_hash(root/'manifest.json')
            write_json(root/'seal.json', {'manifest_sha256': sha})
            db.execute("UPDATE metadata SET value=? WHERE key='manifest_sha256'", (sha,))
        queue.update(baltic_manifest_sha256=file_hash(parent/'manifest.json'),
                     wave4_manifest_sha256=sha, handoff_implementation_sha256=file_hash(own))
        write_json(root/'handoff.json', queue)
        handoff.verify(root)
        write_json(root/f'{suffix}-rearm-verification.json', dict(
            time=time.time(), old_manifest_sha256=old_sha, new_manifest_sha256=sha,
            baltic_manifest_sha256=queue['baltic_manifest_sha256'],
            baltic_pid=client.pid, baltic_create_time=client.create_time(),
            completion_controller=expected_module+'.controller',
            semantic_adapter_applied=False))
    command = [sys.executable, '-u', '-m', 'dfm12.wave4_compact_handoff',
               'watch', '--root', str(root)]
    with (root/f'watcher-{suffix}.log').open('ab', buffering=0) as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                 start_new_session=True)
    receipt = dict(pid=child.pid, create_time=psutil.Process(child.pid).create_time(),
                   start_ticks=Path(f'/proc/{child.pid}/stat').read_text().split()[21],
                   command=command)
    write_json(root/f'watcher-{suffix}-launch.json', receipt)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
