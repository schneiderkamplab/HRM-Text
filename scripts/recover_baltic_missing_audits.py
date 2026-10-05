"""Restore four missing component-specific Baltic audit jobs, never reset failures."""
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3

from dfm12.baltic_audit import MODEL
from dfm12.io import digest, file_hash, load, lock, rows, write_json
from dfm12.jobs import Queue, audit_payload

MISSING = {
    'institutional-en-lv-part00101': 'd80768fa3198d11f73d5c4d1a83847959fd250072cfbd64c8ec6835d2e19bc6a',
    'institutional-en-lt-part00116': 'c83c50eb1fea7838ac486f44d31b40ac13a1aaa75fa59586ac1399215190fe36',
    'institutional-en-lt-part00098': 'c8c59f57de4eb4b99400a775a83345e28de9173449c1ee829e7acda77a6b880f',
    'institutional-en-lt-part00154': '73cf1e224b830fbd0c0514c156727b396538173aecd0837c988c9a4fe2bb0b72',
}


def restore(root, receipt, apply=False):
    root, receipt = Path(root), Path(receipt)
    with lock(root / 'audit/.prepare.lock'):
        manifest_path = root / 'audit/manifest.json'
        manifest = load(manifest_path)
        registered = {x['component']: x for x in manifest['components']}
        planned, payloads = [], []
        with closing(sqlite3.connect((root / 'audit/jobs.sqlite').resolve().as_uri() + '?mode=ro', uri=True)) as db:
            for component, identifier in MISSING.items():
                seal = load(root / 'audit-ready' / component / 'receipt.json')
                if registered[component]['sha256'] != seal['sha256'] or file_hash(seal['path']) != seal['sha256']:
                    raise ValueError('Changed sealed component')
                matches = [r for r in rows(seal['path']) if r['id'] == identifier]
                if len(matches) != 1 or matches[0]['component'] != component or matches[0]['task'] != 'translation':
                    raise ValueError('Wrong missing translation identity')
                record = matches[0]
                fingerprint = digest([record['messages'], record.get('reverse_messages')])
                indexed = db.execute('SELECT content_sha256 FROM candidate_ids WHERE id=?', (identifier,)).fetchone()
                if indexed != (fingerprint,):
                    raise ValueError('Original candidate index mismatch')
                payload = audit_payload(record, MODEL)
                key = digest(['audit', payload])
                state = db.execute('SELECT status,attempts,error FROM jobs WHERE id=?', (key,)).fetchone()
                if state is not None and state[0] == 'failed':
                    raise ValueError('Existing failed job is not a missing-job recovery')
                planned.append(dict(component=component, candidate_id=identifier, content_sha256=fingerprint,
                    sealed_sha256=seal['sha256'], job_id=key, prior_state=state))
                payloads.append(payload)
        report = dict(schema='baltic-missing-audit-jobs-v1', applied=apply,
            manifest_sha256=file_hash(manifest_path), jobs=planned, newly_added=0,
            policy='Only four missing component-specific jobs; no failed attempts/results reset; held sources excluded')
        if apply:
            if receipt.exists():
                raise ValueError('Use a fresh recovery receipt')
            # Persist the pre-mutation evidence, including interruption recovery information.
            write_json(receipt, dict(report, phase='prepared'))
            queue = Queue(root / 'audit/jobs.sqlite')
            try:
                queue.db.execute('BEGIN IMMEDIATE')
                for item, payload in zip(planned, payloads):
                    before = queue.db.total_changes
                    assert queue.add('audit', payload) == item['job_id']
                    report['newly_added'] += int(queue.db.total_changes > before)
                queue.db.execute('COMMIT')
            except BaseException:
                if queue.db.in_transaction:
                    queue.db.execute('ROLLBACK')
                raise
            finally:
                queue.close()
        write_json(receipt, dict(report, phase='complete'))
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/dfm13/baltic'))
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(restore(args.root, args.receipt, args.apply))
