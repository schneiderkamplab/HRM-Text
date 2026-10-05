"""Explicit drained W4-only parallel-I/O migration and detached restart."""
import argparse
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

import psutil

from dfm12 import wave4_compact_handoff as handoff
from dfm12 import wave4_parallel_io as runtime
from dfm12.io import file_hash, load, lock, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--expected-sha256', required=True)
    p.add_argument('--replaces-sha256')
    p.add_argument('--reservation-io', action='store_true')
    p.add_argument('--disk-pipeline', action='store_true')
    p.add_argument('--batched-runtime', action='store_true')
    p.add_argument('--fast-admission', action='store_true')
    p.add_argument('--batch-primitive-sha256')
    p.add_argument('--prior-parallel-sha256')
    a = p.parse_args()
    root = a.root.resolve()
    if a.fast_admission:
        from dfm12 import wave4_admission_fast
        module = Path(wave4_admission_fast.__file__).resolve()
    elif a.batched_runtime:
        from dfm12 import wave4_batched_runtime, wave4_ledger_batch
        module = Path(wave4_batched_runtime.__file__).resolve()
        batch_dependency = Path(wave4_ledger_batch.__file__).resolve()
        if not a.batch_primitive_sha256 or file_hash(batch_dependency) != a.batch_primitive_sha256:
            raise ValueError('Batch primitive not at coordinated frozen hash')
    elif a.disk_pipeline:
        from dfm12 import wave4_disk_pipeline
        module = Path(wave4_disk_pipeline.__file__).resolve()
    elif a.reservation_io:
        from dfm12 import wave4_reservation_io
        module = Path(wave4_reservation_io.__file__).resolve()
    else:
        module = Path(runtime.__file__).resolve()
    if file_hash(module) != a.expected_sha256:
        raise ValueError('Runtime not at coordinated frozen hash')
    with lock(root/'handoff.lock'), lock(root/'controller.lock'):
        if a.replaces_sha256 or a.prior_parallel_sha256:
            manifest = load(root/'manifest.json')
            old_sha = file_hash(root/'manifest.json')
            if old_sha != load(root/'seal.json')['manifest_sha256']:
                raise ValueError('Old manifest seal drift')
            replaced = Path(runtime.__file__).resolve() if a.prior_parallel_sha256 else module
            replaced_sha = a.prior_parallel_sha256 or a.replaces_sha256
            if manifest['implementation_pins'].get(str(replaced)) != replaced_sha:
                raise ValueError('Unexpected prior runtime pin')
            for field in ('implementation_pins', 'external_pins', 'input_pins'):
                for path, sha in manifest[field].items():
                    if field == 'implementation_pins' and path == str(replaced):
                        continue
                    if file_hash(root/path if field == 'input_pins' else path) != sha:
                        raise ValueError('Unrelated input drift: '+path)
        else:
            manifest = handoff.verify(root)
        prior = load(root/'launch.json')
        try:
            old = psutil.Process(prior['pid'])
            if old.create_time() == prior['create_time'] and old.status() != psutil.STATUS_ZOMBIE:
                raise ValueError('Previous W4 process still alive')
        except psutil.NoSuchProcess:
            pass
        if not (a.replaces_sha256 or a.prior_parallel_sha256):
            handoff.verify_independent_launch(root)
        with sqlite3.connect(root/'jobs.sqlite') as db:
            if (db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]
                    or db.execute('SELECT sum(active) FROM groups').fetchone()[0]):
                raise ValueError('W4 not drained')
            counts = dict(db.execute('SELECT status,count(*) FROM jobs GROUP BY status'))
            if (a.replaces_sha256 or a.prior_parallel_sha256) and db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()[0] != old_sha:
                raise ValueError('Old ledger seal drift')
            archive = root/('pre-fast-admission' if a.fast_admission else 'pre-ledger-batch16' if a.batched_runtime else 'pre-disk128-cpu16' if a.disk_pipeline else 'pre-reservation-io16' if a.reservation_io else
                'pre-parallel-io16-fix-'+a.expected_sha256[:12] if a.replaces_sha256 else 'pre-parallel-io16')
            archive.mkdir()
            for name in ('manifest.json', 'seal.json', 'handoff.json', 'launch.json',
                         'launch-intent.json', 'independent-launch-authorization.json', 'runtime.json'):
                write_json(archive/name, load(root/name))
            manifest.update(parallel_io_workers=16, parallel_io_runtime_module='dfm12.wave4_parallel_io')
            if a.fast_admission:
                manifest['admission_parser_runtime_module'] = 'dfm12.wave4_admission_fast'
            if a.batched_runtime:
                manifest.update(batched_runtime_module='dfm12.wave4_batched_runtime',
                    ledger_batch_max=16, ledger_batch_fairness='3completion:1reserve')
                manifest['implementation_pins'][str(batch_dependency)] = a.batch_primitive_sha256
            if a.disk_pipeline:
                manifest.update(disk_pipeline_runtime_module='dfm12.wave4_disk_pipeline',
                    pool_workers=dict(owner=1,cpu=16,disk=128),json_encoding='compact_single_write')
            if a.reservation_io:
                manifest['reservation_io_runtime_module'] = 'dfm12.wave4_reservation_io'
                from dfm12 import calibration_loop_guard_fast
                dependency = Path(calibration_loop_guard_fast.__file__).resolve()
                manifest['implementation_pins'][str(dependency)] = file_hash(dependency)
                if a.prior_parallel_sha256:
                    manifest['implementation_pins'][str(replaced)] = file_hash(replaced)
            manifest['implementation_pins'][str(module)] = a.expected_sha256
            write_json(root/'manifest.json', manifest)
            sha = file_hash(root/'manifest.json')
            write_json(root/'seal.json', dict(manifest_sha256=sha))
            db.execute("UPDATE metadata SET value=? WHERE key='manifest_sha256'", (sha,))
        for name in ('handoff.json', 'independent-launch-authorization.json'):
            value = load(root/name)
            value['wave4_manifest_sha256'] = sha
            write_json(root/name, value)
        handoff.verify_independent_launch(root)
        if file_hash(module) != a.expected_sha256:
            raise ValueError('Runtime changed during migration')
        if a.batched_runtime and file_hash(batch_dependency) != a.batch_primitive_sha256:
            raise ValueError('Batch primitive changed during migration')
        command = [sys.executable, '-u', '-m',
                   'dfm12.wave4_admission_fast' if a.fast_admission else
                   'dfm12.wave4_batched_runtime' if a.batched_runtime else
                   'dfm12.wave4_disk_pipeline' if a.disk_pipeline else
                   'dfm12.wave4_reservation_io' if a.reservation_io else 'dfm12.wave4_parallel_io',
                   '--root', str(root), '--launch-mode', 'independent']
        if not (a.reservation_io or a.disk_pipeline or a.batched_runtime or a.fast_admission):
            command += ['--workers', '16']
        label = 'fast-admission' if a.fast_admission else 'ledger-batch' if a.batched_runtime else 'disk-pipeline' if a.disk_pipeline else 'reservation-io' if a.reservation_io else 'parallel-io'
        write_json(root/'launch-intent.json', dict(command=command, time=time.time(),
            reason='User-authorized parallel I/O16 successor; retained independent-launch gate'))
        write_json(root/f'{label}-migration.json', dict(manifest_sha256=sha,
            preserved_job_counts=counts, jobs_reset=0, failed_replays=0,
            raw_baltic_proof_untouched=True, runtime_sha256=a.expected_sha256))
        with (root/f'runner-{label}16.log').open('ab', buffering=0) as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        receipt = dict(pid=child.pid, create_time=psutil.Process(child.pid).create_time(), command=command)
        write_json(root/'launch.json', receipt)
        write_json(root/f'{label}-launch.json', receipt)
        print(receipt, flush=True)


if __name__ == '__main__':
    main()
