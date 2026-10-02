"""Re-audit the old pilot, credit passing rows, then resume quarter production.

Requires an already drained quarter controller. Never signals GPU processes,
starts servers, or changes training. Failures are recorded before production
is resumed; invalid/incomplete audits cannot be imported.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import load, lock, write_json
from dfm12.multilingual_quarter import verify


def require_drained(root):
    with sqlite3.connect(f'file:{root / "jobs.sqlite"}?mode=ro', uri=True) as db:
        running = db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]
        active = db.execute('SELECT sum(active) FROM groups').fetchone()[0]
    if running or active:
        raise RuntimeError(f'Quarter controller not drained: running={running}, active={active}')


def handoff(quarter, audit):
    quarter, audit = quarter.resolve(), audit.resolve()
    os.chdir(ROOT)
    os.environ.update(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', TOKENIZERS_PARALLELISM='false')
    with lock(audit / 'handoff.lock'):
        if (audit / 'handoff-finished.json').exists():
            raise RuntimeError('Handoff already finished; inspect its receipt before restarting')
        verify(quarter)
        outcome = dict(started=time.time(), quarter_root=str(quarter), audit_root=str(audit),
                       audit_success=False, imported=False)
        # Holding the production lock prevents a competing generation client.
        with lock(quarter / 'controller.lock'):
            require_drained(quarter)
            try:
                write_json(audit / 'handoff-status.json', dict(phase='reauditing', **outcome))
                with (audit / 'client.log').open('ab', buffering=0) as log:
                    subprocess.run([sys.executable, '-B', '-u', '-m',
                        'dfm12.multilingual_first_pilot_reaudit', 'run', '--root', str(audit),
                        '--concurrency-per-server', '32', '--timeout', '600'],
                        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, check=True)
                outcome['audit_success'] = True
            except Exception as exc:
                outcome['error'] = repr(exc)
        try:
            if outcome['audit_success']:
                write_json(audit / 'handoff-status.json', dict(phase='importing', **outcome))
                with (audit / 'import.log').open('ab', buffering=0) as log:
                    subprocess.run([sys.executable, '-B', '-u', '-m',
                        'dfm12.multilingual_quarter_import', '--quarter-root', str(quarter),
                        '--audit-root', str(audit)], stdin=subprocess.DEVNULL,
                        stdout=log, stderr=subprocess.STDOUT, check=True)
                outcome['imported'] = True
        except Exception as exc:
            outcome['error'] = repr(exc)
        # The importer owns its own lock/transaction. Never edit its ledger here.
        with lock(quarter / 'controller.lock'):
            require_drained(quarter)
            verify(quarter)
        with (quarter / 'client.log').open('ab', buffering=0) as log:
            process = subprocess.Popen([sys.executable, '-B', '-u', '-m',
                'dfm12.multilingual_quarter', 'run', '--root', str(quarter),
                '--concurrency-per-server', '32', '--timeout', '600'],
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True)
        outcome['quarter_pid'] = process.pid
        outcome['resume_confirmed'] = False
        write_json(audit / 'handoff-status.json', dict(phase='resuming', **outcome))
        for _ in range(120):
            if process.poll() is not None:
                outcome['resume_error'] = f'Quarter exited with {process.returncode}'
                break
            try:
                progress = load(quarter / 'progress.json')
                if progress.get('pid') == process.pid and progress.get('phase') == 'running':
                    outcome['resume_confirmed'] = True
                    break
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            time.sleep(2)
        outcome['finished'] = time.time()
        write_json(audit / 'handoff-finished.json', outcome)
        write_json(audit / 'handoff-status.json', dict(
            phase='quarter_resumed' if outcome['resume_confirmed'] else 'resume_unconfirmed', **outcome))
        print(json.dumps(outcome), flush=True)
        return 0 if outcome['imported'] and outcome['resume_confirmed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--quarter-root', type=Path, required=True)
    parser.add_argument('--audit-root', type=Path, required=True)
    parser.add_argument('--arm', action='store_true', required=True)
    args = parser.parse_args()
    raise SystemExit(handoff(args.quarter_root, args.audit_root))
