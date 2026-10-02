"""Verify finished local multilingual packages without consulting live ledgers."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
from itertools import zip_longest
import json
from pathlib import Path
import time

from .export_multilingual_completed import LANGUAGES, ALL_LANGUAGES, FAMILIES, cohort, language_target
from .io import digest, file_hash, load, write_json


def verify_package(folder):
    folder = Path(folder)
    manifest = load(folder / 'metadata/manifest.json')
    for relative, pin in manifest['files'].items():
        path = folder / relative
        if path.stat().st_size != pin['bytes'] or file_hash(path) != pin['sha256']:
            raise ValueError(f'File drift: {path}')
    counts = Counter()
    origins = Counter()
    ids, fingerprints = set(), set()
    for family in sorted(FAMILIES):
        with gzip.open(folder / 'data' / f'train-{family}.jsonl.gz', 'rt') as rows, \
             gzip.open(folder / 'metadata' / f'audits-{family}.jsonl.gz', 'rt') as audits:
            for raw_row, raw_audit in zip_longest(rows, audits):
                if raw_row is None or raw_audit is None:
                    raise ValueError('Training/audit length mismatch')
                row, audit = json.loads(raw_row), json.loads(raw_audit)
                fingerprint = digest({key: row[key] for key in ('messages', 'tools')})
                if row['id'] != audit['id'] or digest(row) != audit['training_row_sha256']:
                    raise ValueError('Training/audit binding mismatch')
                if fingerprint != audit['fingerprint']:
                    raise ValueError('Native messages/tools fingerprint mismatch')
                if row['family'] != family or row['language'] != manifest['language']:
                    raise ValueError('Package group mismatch')
                if row['id'] in ids or fingerprint in fingerprints:
                    raise ValueError('Duplicate training conversation')
                ids.add(row['id'])
                fingerprints.add(fingerprint)
                counts[family] += 1
                origins[audit['origin']] += 1
    if dict(counts) != manifest['families'] or dict(origins) != manifest['origins']:
        raise ValueError('Package counters mismatch')
    expected = language_target(manifest['language'])
    if len(ids) != manifest['rows'] or len(ids) != expected:
        raise ValueError('Package row count mismatch')
    return dict(language=manifest['language'], rows=len(ids), families=dict(counts),
                origins=dict(origins), manifest_sha256=file_hash(folder / 'metadata/manifest.json'))


def run(root, languages=LANGUAGES):
    languages, total = cohort(languages)
    root = Path(root)
    completion, manifest = load(root / 'completion.json'), load(root / 'manifest.json')
    if completion['rows'] != total or completion['packages'] != len(languages):
        raise ValueError('Incomplete export')
    packages = manifest['packages']
    if len(packages) != len(languages) or {p['language'] for p in packages} != set(languages):
        raise ValueError('Wrong language scope')
    with ProcessPoolExecutor(max_workers=8) as pool:
        checked = list(pool.map(verify_package, [root / p['name'] for p in packages]))
    if sum(p['rows'] for p in checked) != total:
        raise ValueError('Wrong total')
    receipt = dict(verified_at=time.time(), rows=total, packages=checked,
                   manifest_sha256=file_hash(root / 'manifest.json'),
                   completion_sha256=file_hash(root / 'completion.json'),
                   all_package_hashes_verified=True, all_training_audit_pairs_verified=True,
                   local_only=True, upload_performed=False)
    write_json(root / 'verification.json', receipt)
    print(json.dumps(dict(rows=total, packages=len(languages), verified=True)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--languages', nargs='+', choices=ALL_LANGUAGES, default=LANGUAGES)
    args = parser.parse_args()
    run(args.root, args.languages)
