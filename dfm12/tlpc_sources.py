"""Bounded authenticated TLPC acquisition; disjoint immutable source inventories."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
import unicodedata

from .io import digest, file_hash, load, lock, write_json

REVISION = 'e2fea1d2c4c0828a218c79d6806fe98f821ad8ce'
REPO = 'Targoman/TLPC'
SITES = ('isna', 'irna', 'mehrnews', 'zoomit', 'zoomg', 'digikala', 'kojaro', 'hamshahrionline')
INVENTORY = Path('data/dfm13/wave4/persian-access-recheck-20261003/Targoman--TLPC-inventory.json')
BOILERPLATE = {'کپی لینک', '#', 'انتهای پیام', 'انتهای پیام/', 'اشتراک گذاری', 'اشتراک‌گذاری'}
# Conservative initial slice: no advice, political conflict, exams or answer keys.
EXCLUDE = re.compile('پزشکی|درمان|بیماری|سلامت|روانشناسی|روان‌شناسی|کنکور|آزمون|پاسخنامه|انتخابات|اسرائیل|صهیونی|جنگ|فلسطین')


def normalize(text):
    return ' '.join(unicodedata.normalize('NFKC', text).replace('ي', 'ی').replace('ك', 'ک').split())


def clean(row):
    category = row.get('category', {})
    if category.get('textType') != 'Formal' or row.get('qa'):
        return None, 'not_formal_article'
    elements = row.get('content')
    if not isinstance(elements, list) or not elements:
        return None, 'missing_content'
    kept, removed = [], []
    for index, element in enumerate(elements):
        text = element.get('text') if isinstance(element, dict) else None
        if not isinstance(text, str):
            return None, 'malformed_content'
        text = text.strip()
        if not text or text in BOILERPLATE:
            removed.append(index)
            continue
        if element.get('type') not in ('p', 'ilink', 'li', 'h1', 'h2', 'h3', 'h4'):
            return None, 'unsupported_structure'
        kept.append(dict(index=index, type=element['type'], text=text, ref=element.get('ref')))
    body = '\n\n'.join(e['text'] for e in kept)
    if not 900 <= len(body) <= 12000:
        return None, 'length'
    if EXCLUDE.search(str(row.get('title', '')) + ' ' + str(category) + ' ' + body):
        return None, 'excluded_topic'
    letters = [c for c in body if c.isalpha()]
    if not letters or sum('\u0600' <= c <= '\u06ff' for c in letters) / len(letters) < .8:
        return None, 'language_ratio'
    if '\ufffd' in body or not isinstance(row.get('url'), str) or not row['url'].startswith(('https://', 'http://')):
        return None, 'encoding_or_url'
    fingerprint = hashlib.sha256(normalize(body).encode()).hexdigest()
    return dict(id=fingerprint, shard=int(fingerprint[:16], 16) % 8,
                text=body, title=row.get('title'), date=row.get('date'), url=row['url'],
                category=category, elements=kept, removed_element_indices=removed,
                original_record_sha256=digest(row)), None


def plan(inventory, byte_limit, per_site=24):
    selected, used = [], 0
    choices = {site: sorted((r for r in inventory if r['path'].startswith(site + '/')
                and r['path'].endswith('.jsonl.gz') and 100000 <= r['bytes'] <= 16000000
                and r.get('lfs_sha256')), key=lambda r: digest(r['path']))[:per_site] for site in SITES}
    for i in range(per_site):
        for site in SITES:
            if i < len(choices[site]):
                row = choices[site][i]
                if used + row['bytes'] <= byte_limit:
                    selected.append(row)
                    used += row['bytes']
    return selected


def prepare(root, byte_limit=768*1024**2, per_site=24):
    from huggingface_hub import hf_hub_download
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with lock(root / 'prepare.lock'):
        if (root / 'receipt.json').exists():
            return load(root / 'receipt.json')
        policy = dict(version='tlpc-source-v1', repo=REPO, revision=REVISION,
            byte_limit=byte_limit, per_site=per_site, sites=SITES,
            inventory_sha256=file_hash(INVENTORY), code_sha256=file_hash(__file__),
            source_overlap_complete=False, evaluation_overlap_complete=False,
            source_permission='owner-approved TLPC', license='CC-BY-NC-SA-4.0',
            training_ready=False, transformations=False)
        policy = json.loads(json.dumps(policy))
        if (root / 'plan.json').exists():
            frozen = load(root / 'plan.json')
            if frozen['policy'] != policy:
                raise ValueError('Preparation policy drift; use a successor root')
            selected = frozen['files']
        else:
            selected = plan(load(INVENTORY), byte_limit, per_site)
            write_json(root / 'plan.json', dict(policy=policy, files=selected))
        databases = []
        for shard in range(8):
            directory = root / f'shard-{shard}'
            directory.mkdir(exist_ok=True)
            db = sqlite3.connect(directory / 'sources.sqlite')
            db.execute('CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, site TEXT, record_json TEXT)')
            databases.append(db)
        state = load(root / 'checkpoint.json') if (root / 'checkpoint.json').exists() else {'done': [], 'counts': {}}
        counts = Counter(state['counts'])
        try:
            for item in selected:
                if item['path'] in state['done']:
                    continue
                write_json(root / 'progress.json', dict(pid=__import__('os').getpid(), phase='downloading',
                    file=item['path'], completed_files=len(state['done']), total_files=len(selected), counts=dict(counts), time=time.time()))
                cached = Path(hf_hub_download(REPO, item['path'], repo_type='dataset', revision=REVISION, token=True))
                if cached.stat().st_size != item['bytes'] or file_hash(cached) != item['lfs_sha256']:
                    raise ValueError('Upstream bytes/hash drift: ' + item['path'])
                expanded = 0
                with gzip.open(cached, 'rt', encoding='utf-8') as handle:
                    for line_number, line in enumerate(handle, 1):
                        expanded += len(line.encode())
                        if expanded > 512*1024**2 or len(line) > 2*1024**2:
                            raise ValueError('Expanded source bound exceeded')
                        raw = json.loads(line)
                        record, reason = clean(raw)
                        counts['scanned'] += 1
                        if reason:
                            counts[reason] += 1
                            continue
                        record.update(repo=REPO, revision=REVISION, path=item['path'],
                            line=line_number, compressed_sha256=item['lfs_sha256'],
                            license='CC-BY-NC-SA-4.0', original_cache_path=str(cached))
                        db = databases[record['shard']]
                        inserted = db.execute('INSERT OR IGNORE INTO sources VALUES(?,?,?)',
                            (record['id'], item['path'].split('/')[0], json.dumps(record, ensure_ascii=False))).rowcount
                        counts['selected' if inserted else 'duplicate'] += 1
                for db in databases:
                    db.commit()
                state['done'].append(item['path'])
                state['counts'] = dict(counts)
                write_json(root / 'checkpoint.json', state)
        finally:
            for db in databases:
                db.close()
        shards = []
        for shard in range(8):
            path = root / f'shard-{shard}' / 'sources.sqlite'
            with sqlite3.connect(path) as db:
                sites = dict(db.execute('SELECT site,count(*) FROM sources GROUP BY site'))
            shards.append(dict(shard=shard, path=str(path), sha256=file_hash(path), rows=sum(sites.values()), sites=sites))
        receipt = dict(policy, plan_sha256=file_hash(root / 'plan.json'), shards=shards,
            counts=dict(counts), compressed_bytes=sum(r['bytes'] for r in selected),
            complete=True, generation_ready=all(s['rows'] for s in shards), time=time.time())
        write_json(root / 'receipt.json', receipt)
        write_json(root / 'progress.json', dict(phase='prepared', **receipt))
        return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--max-bytes', type=int, default=768*1024**2)
    p.add_argument('--shards-per-site', type=int, default=24)
    a = p.parse_args()
    if not 0 < a.max_bytes <= 1024**3 or not 1 <= a.shards_per_site <= 64:
        p.error('At most1GiB compressed and64 shards/site')
    print(json.dumps(prepare(a.root, a.max_bytes, a.shards_per_site)))
