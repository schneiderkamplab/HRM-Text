"""Publish a verified additions reference only after the fenced build completes."""
import argparse
from pathlib import Path
import time

from dfm12.io import file_hash, load, lock, write_json


def identity(pid):
    try:
        stat = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return None if stat[0] == 'Z' else stat[19]
    except FileNotFoundError:
        return None


def run(root, pid):
    control = root.with_name(root.name+'-control')
    with lock(control/'completion-watch.lock'):
        start = identity(pid)
        write_json(control/'watcher.json', dict(build_pid=pid, start_ticks=start, phase='waiting'))
        while start is not None and identity(pid) == start:
            time.sleep(15)
        verified = control/'verified.json'
        if not verified.exists():
            write_json(control/'completion-report.json', dict(status='failed_or_incomplete',
                authoritative=False, log='logs/finished-wave-assembly-20261004.log', time=time.time()))
            raise RuntimeError('Build exited without verified completion; no promotion')
        receipt = load(verified)
        assembly = root/'assembly.json'
        manifest = load(assembly)
        if receipt['totals'] != manifest['totals'] or receipt['missing'] != manifest['unready_additions']:
            raise ValueError('Completion receipt mismatch')
        if any(row['reason'] != 'quality_hold_source_fidelity' for row in receipt['missing']):
            write_json(control/'completion-report.json', dict(status='verification_gaps',
                authoritative=False, totals=receipt['totals'], missing=receipt['missing']))
            raise ValueError('Unexpected verification gaps; no promotion')
        report = dict(status='verified', root=str(root.resolve()), totals=receipt['totals'],
            missing=receipt['missing'], assembly_sha256=file_hash(assembly),
            completion_receipt=str(verified.resolve()), completion_receipt_sha256=file_hash(verified),
            outstanding_unregistered=['DaLA audits still in progress', 'Synthetic production pending',
                'Fars summary fidelity-held sources'],
            local_publication_pending=sum(s.get('publication_pending') is True for s in manifest['ready_additions']),
            sampling_performed=False, time=time.time())
        write_json(control/'completion-report.json', report)
        with lock(Path('data/dfm13/authoritative-additions.lock')):
            write_json('data/dfm13/authoritative-additions.json', dict(report,
                policy='Verified additions reference only; reverify_assembly before use; no epoch sampling or training switch'))
        write_json(control/'watcher.json', dict(build_pid=pid, start_ticks=start, phase='verified_reference_published'))
        print(report, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--pid', type=int, required=True)
    a = p.parse_args()
    run(a.root, a.pid)
