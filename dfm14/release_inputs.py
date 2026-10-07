"""Enumerate completed, hash-verified DFM14 audits and synthetic journals."""
from pathlib import Path

from dfm12.io import file_hash, load, rows

BASE = Path('data/dfm14')
AUDITS = (
    ('gpu-ready', 'audit-v1'),
    ('asian-additions-gpu-v1', 'asian-additions-audit-v1'),
    ('english-additions-gpu-v1', 'english-additions-audit-v1'),
    ('enrichment-gpu-v1', 'enrichment-audit-v1'),
    ('broad-translation-gpu-v1', 'broad-translation-audit-v1'),
)
PRIOR = ('persian-bridge-audit-v1', 'slovak-bridge-audit-v1',
         'institutional-parallel-v1/audit', 'sparse-parallel-v1/audit')


def checked(path, sha):
    if not sha or file_hash(path) != sha:
        raise ValueError(f'Changed or unpinned input: {path}')


def inventory():
    jobs, pins = [], {}
    for source, audit in AUDITS:
        root = BASE/source
        manifest = root/'manifest.json'
        pins[str(manifest)] = file_hash(manifest)
        for chunk in load(manifest)['chunks']:
            path = Path(chunk['input'])
            if not path.is_absolute():
                path = root/path
            directory = BASE/audit/chunk['job_id']
            jobs.append(dict(kind='audit', name=audit+'--'+chunk['job_id'],
                input=str(path), input_sha256=chunk['sha256'], rows=chunk['rows'],
                receipt=str(directory/'receipt.json'), journal=str(directory/'results.jsonl')))
    for audit in PRIOR:
        manifest = BASE/audit/'manifest.json'
        pins[str(manifest)] = file_hash(manifest)
        for chunk in load(manifest)['jobs']:
            directory = BASE/audit/chunk['pair']
            jobs.append(dict(kind='audit', name=audit.replace('/', '--')+'--'+chunk['pair'],
                input=chunk['input'], input_sha256=chunk['sha256'], rows=chunk['rows'],
                receipt=str(directory/'receipt.json'), journal=str(directory/'results.jsonl')))
    manifest = BASE/'production-v1/manifest.json'
    pins[str(manifest)] = file_hash(manifest)
    for job in load(manifest)['jobs']:
        directory = BASE/'production-v1/jobs'/job['job_id']
        jobs.append(dict(kind='synthetic', name='synthetic--'+job['job_id'], job=job,
            receipt=str(directory/'receipt.json'), journal=str(directory/'attempts.jsonl')))
    for job in jobs:
        receipt = Path(job['receipt'])
        if not receipt.is_file():
            raise ValueError('Unfinished audit/generation: '+job['name'])
        job['receipt_sha256'] = file_hash(receipt)
    return dict(jobs=jobs, manifests=pins)


def accepted(job):
    checked(job['receipt'], job['receipt_sha256'])
    receipt = load(job['receipt'])
    sha = receipt.get('results_sha256') or receipt.get('journal_sha256') or receipt.get('sha256')
    checked(job['journal'], sha)
    if job['kind'] == 'synthetic':
        spec = job['job']
        if receipt['job'] != spec:
            raise ValueError('Synthetic job identity mismatch')
        chosen = {}
        for record in rows(job['journal']):
            if record['status'] != 'accepted':
                continue
            slot = record['slot']
            if not spec['start'] <= slot < spec['end']:
                raise ValueError('Synthetic slot outside job')
            if slot in chosen and chosen[slot]['candidate'] != record['candidate']:
                raise ValueError('Conflicting accepted synthetic slot')
            review = record.get('review', {})
            legacy = (review.get('source_usable') == 'pass' and bool(review.get('turns'))
                      and all(turn.get(key) == 'pass' for turn in review['turns'].values()
                              for key in ('language','grounding','fulfillment','format','authorization')))
            checks_pass = all(isinstance(check, dict) and check.get('passed') is True
                              for check in record.get('checks', []))
            if (review.get('decision') != 'accept' and not legacy) or not checks_pass:
                raise ValueError('Accepted synthetic record failed its checks: '+job['name']+':'+str(slot))
            chosen[slot] = record
        if len(chosen) != receipt['counts'].get('accepted', 0):
            raise ValueError('Synthetic receipt count mismatch')
        for slot, record in sorted(chosen.items()):
            row = dict(record['candidate'])
            row.setdefault('id', 'dfm14-synthetic:'+spec['job_id']+':'+str(slot))
            row['task'] = 'synthetic-'+record['family']
            yield row, dict(decision='accept', kind='synthetic', slot=slot,
                attempt=record['attempt'], spec_sha256=record['spec_sha256'],
                journal=job['journal'], journal_sha256=sha, receipt_sha256=job['receipt_sha256'])
        return
    checked(job['input'], job['input_sha256'])
    if receipt['input_sha256'] != job['input_sha256']:
        raise ValueError('Audit/input identity mismatch')
    decisions = {}
    for record in rows(job['journal']):
        key = record['audit_id']
        decision = record.get('review', {}).get('decision')
        if record['status'] in ('accept', 'reject'):
            decision = record['status']
        if record['status'] not in ('reviewed', 'accept', 'reject'):
            decision = 'error'
        previous = decisions.get(key)
        if previous and previous[0] == 'accept' and decision != 'accept':
            raise ValueError('Conflicting accepted audit decision')
        decisions[key] = (decision, record)
    count = 0
    for row in rows(job['input']):
        count += 1
        key = row.get('audit_id', row['id'])
        if key not in decisions:
            raise ValueError('Missing audit decision: '+key)
        decision, record = decisions.pop(key)
        if decision == 'accept':
            yield row, dict(decision='accept', kind='source', audit_id=key,
                policy=record.get('policy', receipt.get('policy')),
                journal=job['journal'], journal_sha256=sha,
                input_sha256=job['input_sha256'], receipt_sha256=job['receipt_sha256'])
    if count != job['rows'] or decisions:
        raise ValueError('Audit population mismatch')
