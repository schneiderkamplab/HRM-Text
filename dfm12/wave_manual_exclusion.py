"""Prepublication exclusion of four explicitly authorized, frozen review rows."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .io import digest, file_hash, load, lock, write_json

REVIEW = Path('docs/reports/sl-sq-sr-transform-review-20261003')
RECEIPT_SHA = '0ec2a6afdaeb347eaedc0a3e64a22079c25ea76cb3ad0f975a4756b77e3c48e9'
REPORT_SHA = 'c9fa49b25597d755afa44a04099d4cd2360bdd01191e66f1e9f9abb0b62eba3c'
AUTHORIZED = {
    1: '00006a4aba1e1927de20182cf5a3ea7edaa680be036320a20df5e49604be4225',
    14: '000bffa8d3d55f61241e1b2d83ef0cc16dec7c5b55123a669020452239a25b4e',
    18: '0001e58b1ad0904d94a0468a5c70dfda299e547071cd187fb55932cc49867ba1',
    28: '000b5c85522b42285a4ccbc30d5d894500d29a73b4a348c7f181bd1c4799bb27',
}
STATUS = 'excluded_manual_review'


def reviewed_decisions():
    if file_hash(REVIEW / 'receipt.json') != RECEIPT_SHA or file_hash(REVIEW / 'report.md') != REPORT_SHA:
        raise ValueError('Frozen review receipt/report changed')
    pins = load(REVIEW / 'receipt.json')['pins']
    for name, sha in pins.items():
        if file_hash(REVIEW / name) != sha:
            raise ValueError('Frozen review artifact changed: ' + name)
    evidence = {x['id']: x for x in load(REVIEW / 'evidence.json')}
    result = []
    for row in load(REVIEW / 'review.json'):
        if row['case'] not in AUTHORIZED:
            continue
        if row['id'] != AUTHORIZED[row['case']] or row['observation_category'] != 'defect':
            raise ValueError('Authorized exact-ID review mismatch')
        item = evidence[row['id']]
        result.append(dict(id=row['id'], component='wikipedia-' + row['language'],
            record_sha256=row['record_sha256'], review_sha256=digest(item['acceptance_review']),
            reason=row['observation'], review_pins=dict(pins, **{'receipt.json': RECEIPT_SHA, 'report.md': REPORT_SHA})))
    if len(result) != 4:
        raise ValueError('Incomplete four-row authorization')
    return result


def require_unpublished(root, component, exports, registry):
    folder = root / 'release' / component
    if any(folder.rglob('publication.json')) or any(exports.glob('dfm13-wave4-' + component + '*')):
        raise ValueError(f'{component}: existing publication/export; use a safe successor')
    status = load(folder / 'status.json')
    if status.get('uploaded') or status.get('status') == 'accepted_uploaded' or status.get('export_in_progress'):
        raise ValueError(f'{component}: publication state blocks manual changes')
    name = 'dfm13_wave4_' + component.replace('-', '_')
    for entry in load(registry)['additions']:
        if entry.get('name', '').startswith(name) or component in entry.get('hf_repo_id', ''):
            raise ValueError(f'{component}: registered publication; use a safe successor')


def refresh_status(root, component, db):
    sealed = load(root / 'audit-ready' / component / 'receipt.json')
    counts = dict(db.execute('SELECT status,count(*) FROM rows GROUP BY status'))
    complete = sum(counts.values()) == sealed['counts']['ready'] and not any(
        counts.get(s) for s in ('repair_pending', 'reaudit_pending', 'audit_retry_pending'))
    result = dict(component=component, counts=counts, input_sha256=sealed['sha256'],
        input_rows=sealed['counts']['ready'], terminal=complete,
        export_ready=complete and not any(counts.get(s) for s in
            ('audit_failed', 'audit_retry_failed', 'repair_infrastructure_failed')))
    write_json(root / 'release' / component / 'status.json', result)
    return result


def apply(root, exports=Path('exports_dfm13'), registry=Path('config/dfm13_sources.json'), component=None,
          decision_loader=None):
    decisions = (decision_loader or reviewed_decisions)()
    if component is not None:
        if component not in {x['component'] for x in decisions}:
            raise ValueError('Component outside exact four-row authorization')
        decisions = [x for x in decisions if x['component'] == component]
    components = sorted({x['component'] for x in decisions})
    results = {}
    with ExitStack() as stack:
        # The same nonblocking locks protect process() and the full export/upload.
        for component in components:
            stack.enter_context(lock(root / 'release' / component / '.lock'))
        databases = {}
        for component in components:
            require_unpublished(root, component, exports, registry)
            folder = root / 'release' / component
            sealed = load(root / 'audit-ready' / component / 'receipt.json')
            if load(folder / 'status.json')['input_sha256'] != sealed['sha256']:
                raise ValueError('Input seal changed')
            db = sqlite3.connect((folder / 'ledger.sqlite').resolve().as_uri() + '?mode=rw', uri=True)
            stack.callback(db.close)
            databases[component] = db
        # Validate every record before making any component transaction durable.
        originals = {}
        for decision in decisions:
            db = databases[decision['component']]
            original = db.execute('SELECT record,status,review FROM rows WHERE id=?', (decision['id'],)).fetchone()
            if original is None or digest(json.loads(original[0])) != decision['record_sha256'] or digest(json.loads(original[2])) != decision['review_sha256']:
                raise ValueError('Candidate or original model review changed: ' + decision['id'])
            if original[1] not in ('accepted', STATUS):
                raise ValueError('Unexpected prior status: ' + original[1])
            existing = None
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='manual_review_decisions'").fetchone():
                existing = db.execute('SELECT decision FROM manual_review_decisions WHERE id=?', (decision['id'],)).fetchone()
            if original[1] == STATUS:
                if existing is None or json.loads(existing[0])['authorization'] != decision:
                    raise ValueError('Missing or conflicting manual decision')
            elif existing is not None:
                raise ValueError('Manual decision/status conflict')
            originals[decision['id']] = original
        for component, db in databases.items():
            with db:
                db.execute('CREATE TABLE IF NOT EXISTS manual_review_decisions (id TEXT PRIMARY KEY,decision TEXT NOT NULL)')
                db.execute("CREATE TRIGGER IF NOT EXISTS manual_review_no_update BEFORE UPDATE ON manual_review_decisions BEGIN SELECT RAISE(ABORT,'append-only manual decisions'); END")
                db.execute("CREATE TRIGGER IF NOT EXISTS manual_review_no_delete BEFORE DELETE ON manual_review_decisions BEGIN SELECT RAISE(ABORT,'append-only manual decisions'); END")
                for decision in decisions:
                    if decision['component'] != component:
                        continue
                    raw, prior, review = originals[decision['id']]
                    if prior == STATUS:
                        continue
                    event = dict(authorization=decision, prior_status=prior, status=STATUS,
                        original_record=raw, original_model_review=review,
                        authority='Main-agent exact-case quality judgment under the user broad quality-review task; not direct user per-case adjudication',
                        timestamp=datetime.now(timezone.utc).isoformat())
                    db.execute('INSERT INTO manual_review_decisions VALUES (?,?)', (decision['id'], json.dumps(event, ensure_ascii=False)))
                    db.execute('UPDATE rows SET status=? WHERE id=?', (STATUS, decision['id']))
            # If interrupted here, counts mismatch blocks export; rerun recovers.
            results[component] = refresh_status(root, component, db)
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/dfm13/wave4'))
    parser.add_argument('--component', choices=('wikipedia-sl', 'wikipedia-sq'))
    args = parser.parse_args()
    print(json.dumps(apply(args.root, component=args.component), indent=2))
