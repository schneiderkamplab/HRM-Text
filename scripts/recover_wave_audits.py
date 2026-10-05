"""Queue fresh schema-constrained reviews without resetting failed source jobs."""
import argparse
import json
from pathlib import Path
import sqlite3

from dfm12.io import atomic, lock, write_json
from dfm12.jobs import Queue
from dfm12.wave_repair import recovery_audit


def recover(root):
    with lock(root / 'repair/recover-audits.lock'):
        source = sqlite3.connect((root / 'audit/jobs.sqlite').resolve().as_uri() + '?mode=ro', uri=True)
        target = Queue(root / 'repair/jobs.sqlite')
        counts = dict(failed_source_jobs=0, newly_queued=0, reused=0)
        try:
            with atomic(root / 'repair/source-audit-retries.jsonl') as out:
                target.db.execute('BEGIN IMMEDIATE')
                for key, encoded, attempts, error in source.execute(
                        "SELECT id,payload,attempts,error FROM jobs WHERE stage='audit' AND status='failed'"):
                    payload = json.loads(encoded)
                    before = target.db.total_changes
                    retry = target.add('audit', recovery_audit(payload['record']))
                    added = target.db.total_changes > before
                    counts['failed_source_jobs'] += 1
                    counts['newly_queued' if added else 'reused'] += 1
                    out.write(json.dumps(dict(source_job=key, retry_job=retry,
                        original_attempts=attempts, original_error=error)) + '\n')
                    if counts['failed_source_jobs'] % 128 == 0:
                        target.db.execute('COMMIT')
                        target.db.execute('BEGIN IMMEDIATE')
                target.db.execute('COMMIT')
            write_json(root / 'repair/source-audit-retries.json', counts)
            print(json.dumps(counts), flush=True)
        finally:
            target.close();source.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    recover(parser.parse_args().root)
