"""Stop a pinned set of audit server process trees after the identity queue drains."""
import argparse
import json
from pathlib import Path
import sqlite3
import time

import psutil


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--servers', type=Path, required=True)
    args = parser.parse_args()
    servers = json.loads(args.servers.read_text())
    while True:
        prepared = args.root / 'preparation.json'
        if prepared.exists():
            expected = json.loads(prepared.read_text())['prepared']
            with sqlite3.connect(f'file:{args.root.resolve()}/jobs.sqlite?mode=ro', uri=True) as db:
                counts = dict(db.execute('SELECT status,COUNT(*) FROM jobs GROUP BY status'))
            print(time.strftime('%FT%T'), counts, flush=True)
            if expected > 0 and sum(counts.values()) == expected and not (set(counts) - {'done', 'failed'}):
                break
        time.sleep(15)
    targets = {}
    for saved in servers:
        try:
            parent = psutil.Process(saved['pid'])
            if parent.create_time() != saved['create_time'] or parent.cmdline() != saved['cmdline']:
                raise RuntimeError('Server identity changed; refusing to signal reused PID')
            for proc in [parent, *parent.children(recursive=True)]:
                targets[proc.pid] = proc
        except psutil.NoSuchProcess:
            pass
    for proc in targets.values():
        try:
            proc.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(list(targets.values()), timeout=60)
    for proc in alive:
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(alive, timeout=30)
    receipt = dict(completed=time.time(), audit_status=counts,
                   targeted_pids=list(targets), surviving_pids=[p.pid for p in alive])
    (args.root / 'servers-stopped.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt), flush=True)
    if alive:
        raise RuntimeError('Audit processes survived shutdown')


if __name__ == '__main__':
    main()
