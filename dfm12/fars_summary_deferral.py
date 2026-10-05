"""Conditional, receipt-bound deferral of never-claimed Fars repair jobs."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import time

from .io import digest, file_hash, load, lock, write_json
from .fars_summary_packets import COMPONENTS

STATUS = 'deferred31B'


def payload_hash(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def eligible(row, now):
    payload = json.loads(row['payload'])
    return (row['stage'] == 'generate' and row['status'] == 'pending'
        and row['attempts'] == 0 and row['owner'] is None
        and (row['lease'] is None or row['lease'] <= now)
        and payload['record'].get('component') in COMPONENTS
        and row['id'] == digest(['generate', payload]))


def propose(queue, root):
    root.mkdir(parents=True, exist_ok=True)
    with lock(root / '.lock'):
        if (root / 'proposal.json').exists():
            raise ValueError('Existing proposal; use apply, do not overwrite')
        with closing(sqlite3.connect(queue.resolve().as_uri() + '?mode=ro', uri=True)) as db:
            db.row_factory = sqlite3.Row
            rows = []
            now = time.time()
            for row in db.execute("SELECT * FROM jobs WHERE stage='generate' AND status='pending' AND attempts=0 AND owner IS NULL"):
                row = dict(row)
                if eligible(row, now):
                    rows.append(dict(row, payload_sha256=payload_hash(row['payload'])))
        value = dict(queue=str(queue.resolve()), created=now, jobs=rows,
            authorization='User explicitly authorized conditional never-claimed held Fars generation deferral',
            policy='unfinished31B; not reviewed, not admitted; running/unrelated jobs excluded')
        write_json(root / 'proposal.json', value)
        write_json(root / 'proposal-seal.json', dict(sha256=file_hash(root / 'proposal.json')))
        return len(rows)


def load_proposal(root):
    sha = file_hash(root / 'proposal.json')
    if sha != load(root / 'proposal-seal.json')['sha256']:
        raise ValueError('Proposal drift')
    return load(root / 'proposal.json'), sha


def event_detail(proposal_sha, raw_sha):
    return json.dumps(dict(authorization_sha256=proposal_sha, payload_sha256=raw_sha,
        disposition='unfinished31B'), sort_keys=True)


def apply(root):
    with lock(root / '.lock'):
        proposal, sha = load_proposal(root)
        results = []
        with closing(sqlite3.connect(proposal['queue'], timeout=60, isolation_level=None)) as db:
            db.row_factory = sqlite3.Row
            db.execute('BEGIN IMMEDIATE')
            try:
                events = {tuple(r) for r in db.execute('SELECT job_id,detail FROM events WHERE attempt=0 AND status=?', (STATUS,))}
                for expected in proposal['jobs']:
                    if not eligible(expected, proposal['created']) or payload_hash(expected['payload']) != expected['payload_sha256']:
                        raise ValueError('Invalid authorized proposal row')
                    current = db.execute('SELECT * FROM jobs WHERE id=?', (expected['id'],)).fetchone()
                    detail = event_detail(sha, expected['payload_sha256'])
                    outcome = 'skipped_changed_or_claimed'
                    if current is not None:
                        current = dict(current)
                        existing = (expected['id'], detail) in events
                        if (current['payload'] == expected['payload'] and current['status'] == STATUS
                                and current['attempts'] == 0 and current['owner'] is None
                                and current['lease'] == expected['lease'] and existing):
                            outcome = 'authorized_deferred'
                        elif (current['payload'] == expected['payload']
                                and current['lease'] == expected['lease'] and eligible(current, time.time())):
                            count = db.execute("UPDATE jobs SET status=? WHERE id=? AND payload=? AND status='pending' "
                                'AND stage=\'generate\' AND attempts=0 AND owner IS NULL AND (lease IS NULL OR lease<=?)',
                                (STATUS,expected['id'],expected['payload'],time.time())).rowcount
                            if count != 1:
                                raise ValueError('Unexpected conditional-update race')
                            db.execute('INSERT INTO events VALUES(?,?,?,?,?)',
                                (time.time(),expected['id'],0,STATUS,detail))
                            outcome = 'authorized_deferred'
                    results.append(dict(id=expected['id'], payload_sha256=expected['payload_sha256'], outcome=outcome))
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise
        receipt = dict(proposal_sha256=sha, queue=proposal['queue'], time=time.time(), jobs=results,
            unfinished31B=sum(r['outcome']=='authorized_deferred' for r in results),
            reviewed=0, admission_authorized=False)
        # Events commit with the mutation; rerunning recovers a missing external receipt.
        write_json(root / 'receipt.json', receipt)
        write_json(root / 'receipt-seal.json', dict(sha256=file_hash(root / 'receipt.json')))
        return receipt


def authorized_jobs(root, db):
    proposal, sha = load_proposal(root)
    receipt = load(root / 'receipt.json')
    if (file_hash(root / 'receipt.json') != load(root / 'receipt-seal.json')['sha256']
            or receipt['proposal_sha256'] != sha or receipt['queue'] != proposal['queue']):
        raise ValueError('Deferral receipt drift')
    authorized = {r['id']:r for r in receipt['jobs'] if r['outcome']=='authorized_deferred'}
    result = {}
    events = set(db.execute('SELECT job_id,detail FROM events WHERE attempt=0 AND status=?', (STATUS,)))
    for expected in proposal['jobs']:
        if expected['id'] not in authorized:
            continue
        row = db.execute('SELECT stage,status,attempts,owner,lease,payload FROM jobs WHERE id=?', (expected['id'],)).fetchone()
        detail = event_detail(sha, expected['payload_sha256'])
        event = (expected['id'],detail) in events
        if (not row or row[0:4] != ('generate',STATUS,0,None)
                or row[4] != expected['lease'] or payload_hash(row[5]) != expected['payload_sha256']
                or authorized[expected['id']]['payload_sha256'] != expected['payload_sha256'] or not event):
            raise ValueError('Authorized deferred job changed: ' + expected['id'])
        result[expected['id']] = expected['payload_sha256']
    return result


def handoff_state(job_id, status, raw, authorized):
    if status == STATUS and authorized.get(job_id) == payload_hash(raw):
        return 'unfinished31B_authorized'
    if status in ('done','failed'):
        return 'terminal26B_not31B_reviewed'
    return 'blocked_nonterminal_not_authorized'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['propose','apply'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--queue', type=Path, default=Path('data/dfm13/wave4/repair/jobs.sqlite'))
    args = parser.parse_args()
    value = propose(args.queue,args.root) if args.command=='propose' else apply(args.root)
    print(json.dumps(value if isinstance(value,int) else {k:v for k,v in value.items() if k!='jobs'}))


if __name__ == '__main__':
    main()
