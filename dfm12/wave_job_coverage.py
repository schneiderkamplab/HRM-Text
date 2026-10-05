"""Reconcile sealed registered components without resetting audit history."""
from pathlib import Path

from .io import digest, file_hash, load, rows, write_json
from .jobs import Queue, audit_payload


def ensure_batch(q, payloads):
    """Bounded primary-key reads; acquire the writer only for absent jobs."""
    keyed = {digest(['audit', payload]): payload for payload in payloads}
    if not keyed:
        return 0
    placeholders = ','.join('?' for _ in keyed)
    existing = {row[0] for row in q.db.execute(
        f'SELECT id FROM jobs WHERE id IN ({placeholders})', tuple(keyed))}
    missing = [payload for key, payload in keyed.items() if key not in existing]
    if not missing:
        return 0
    q.db.execute('BEGIN IMMEDIATE')
    try:
        before = q.db.total_changes
        for payload in missing:
            # Another writer may have inserted after the read; Queue.add's
            # INSERT OR IGNORE preserves its status, lease and full history.
            q.add('audit', payload)
        added = q.db.total_changes - before
        q.db.execute('COMMIT')
        return added
    except BaseException:
        q.db.execute('ROLLBACK')
        raise


def reconcile(root):
    from .wave4_cpu import MODEL, queue_lock
    root = Path(root)
    with queue_lock(root / 'audit/.enqueue.lock'):
        q = Queue(root / 'audit/jobs.sqlite')
        coverage = []
        try:
            components = q.db.execute('SELECT name,sha FROM components ORDER BY name').fetchall()
            for name, sha in components:
                if not name.startswith(('direct-', 'institutional-', 'pivot-')):
                    continue
                seal = load(root / 'audit-ready' / name / 'receipt.json')
                path = Path(seal['path'])
                if seal['sha256'] != sha or file_hash(path) != sha:
                    raise ValueError('Registered component changed: ' + name)
                count = added = 0
                batch = []
                for row in rows(path):
                    batch.append(audit_payload(row, MODEL))
                    count += 1
                    if len(batch) == 512:
                        added += ensure_batch(q, batch)
                        batch.clear()
                added += ensure_batch(q, batch)
                coverage.append(dict(component=name, sha256=sha,
                                     rows_checked=count, new_jobs=added))
                print('COVERAGE', name, count, added, flush=True)
            receipt = dict(components=coverage, exact_payload_coverage=True,
                           new_jobs=sum(x['new_jobs'] for x in coverage),
                           admission_authorized=False)
            write_json(root / 'audit/component-job-coverage.json', receipt)
            return receipt
        finally:
            q.close()
