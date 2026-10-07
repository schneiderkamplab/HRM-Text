"""Independent, restartable preparation/readiness/audit chains on shared servers."""
import concurrent.futures
import os
from pathlib import Path
import subprocess
import sys
import time

from dfm12.io import load, lock, write_json

BASE = Path('logs/dfm14/shared-gemma-20261007/additions')


def chain(name, roots, concurrency, wait=False):
    output = Path('data/dfm14') / (name + '-gpu-v1')
    audit = Path('data/dfm14') / (name + '-audit-v1')
    with lock(BASE / (name + '.lock')):
        if wait:
            while not all((p / 'progress.json').exists() and
                          load(p / 'progress.json')['phase'].startswith('cpu_pass_finished') for p in roots):
                write_json(BASE / (name + '-state.json'), dict(phase='waiting_for_cpu', roots=list(map(str, roots))))
                time.sleep(30)
        prepare = [sys.executable, '-u', '-m', 'dfm14.prepare_gpu', '--output', str(output), '--workers', '16']
        for root in roots:
            prepare += ['--root', str(root), '--source-manifest', str(root / 'sources.json')]
        commands = [prepare, [sys.executable, '-u', '-m', 'dfm14.readiness', '--root', str(output), '--audit-only']]
        command = [sys.executable, '-u', '-m', 'audit_pipeline', 'audit', '--root', str(output), '--output', str(audit),
                   '--concurrency', str(concurrency)]
        commands.append(command)
        for phase, command in zip(('preparation', 'readiness', 'audit'), commands):
            write_json(BASE / (name + '-state.json'), dict(phase=phase, command=command, pid=os.getpid()))
            with (BASE / (name + '-' + phase + '.log')).open('a') as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        write_json(BASE / (name + '-state.json'), dict(phase='audit_complete', training_ready=False))


def main():
    with lock(BASE / '.controller.lock'):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = {
                pool.submit(chain, 'asian-additions', [Path('data/dfm14/baai-expansion-v1'),
                    Path('data/dfm14/ja-ar-ru-additions-v1')], 32): 'asian-additions',
                pool.submit(chain, 'english-additions', [Path('data/dfm14/english-additions-v1')], 32, True): 'english-additions',
            }
            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    write_json(BASE / (name + '-state.json'), dict(phase='failed', error=str(exc)))
                    print(name, repr(exc), flush=True)


if __name__ == '__main__':
    main()
