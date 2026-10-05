"""Bounded metadata-only completion snapshot; no candidate reads or DB writes."""
import collections
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
from datetime import datetime, timezone

OUT = Path(__file__).parent
pins = {}


def read(path):
    path = Path(path)
    raw = path.read_bytes()
    pins[str(path)] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


registry = read('config/dfm13_sources.json')['additions']
result = dict(time=datetime.now(timezone.utc).isoformat(),
              scope='rolling metadata snapshot; no payload rehash or live writes', waves={})
for number, name in ((3, 'baltic'), (4, 'wave4')):
    root = Path('data/dfm13') / name
    entries = [r for r in registry if r['name'].startswith(f'dfm13_wave{number}_')]
    info = dict(registry=[{k: r.get(k) for k in
        ('name', 'rows', 'status', 'revision', 'output_sha256', 'tokenization_performed',
         'tokenized_rows', 'tokenized_tokens', 'quality_hold')} for r in entries])
    info['registry_counts'] = dict(collections.Counter(r['status'] for r in entries))
    cfg = read(root / 'translations/config.json')
    pairs = {'-'.join(p) for p in cfg['requested_pairs']}
    manifest = read(root / ('audit/translation-manifest.json' if number == 4
                            else 'audit-ready/translations-manifest.json'))
    components = manifest['components'] if isinstance(manifest, dict) else manifest
    supply = collections.Counter()
    for c in components:
        component = c['component']
        receipt_path = root / 'audit-ready' / component / 'receipt.json'
        receipt = read(receipt_path) if receipt_path.exists() else c
        pair = component.split('-', 1)[1].split('-part')[0]
        supply[pair] += receipt['counts']['ready']
    info['pair_audit_ready'] = {p: supply[p] for p in sorted(pairs)}
    info['zero_supply_pairs'] = sorted(p for p in pairs if not supply[p])
    if number == 3:
        info['source_preflight'] = [dict(component=c['component'], counts=c['counts'])
            for kind in ('instructions', 'transforms')
            for c in read(root / f'audit-ready/{kind}-manifest.json')]
        info['initial_queue_receipt'] = {k: v for k, v in read(root / 'audit/manifest.json').items()
                                         if k in ('total_unique_jobs', 'queued')}
    else:
        info['source_preflight'] = []
        for path in sorted((root / 'audit-ready').glob('*/receipt.json')):
            if path.parent.name.startswith(('direct-', 'institutional-', 'pivot-', 'sk-additive-')):
                continue
            c = read(path)
            info['source_preflight'].append(dict(component=path.parent.name, counts=c['counts']))
        with sqlite3.connect((root / 'audit/jobs.sqlite').resolve().as_uri() + '?mode=ro',
                             uri=True, timeout=1) as db:
            db.execute('PRAGMA query_only=ON')
            registered = dict(db.execute('SELECT name,sha FROM components'))
        info['manifest_components_unregistered'] = [c['component'] for c in components
                                                    if c['component'] not in registered]
        coverage = read(root / 'audit/component-job-coverage.json')
        info['existing_exact_coverage_receipt'] = dict(
            exact=coverage['exact_payload_coverage'], components=len(coverage['components']),
            rows=sum(c['rows_checked'] for c in coverage['components']), new_jobs=coverage['new_jobs'])
        additive = read(root / 'slovak-additive-20261003-v1/integration.json')
        adds = {c['component'].removeprefix('sk-additive-v1-direct-').removeprefix(
            'sk-additive-v1-pivot-'): c['rows'] for c in additive['components']}
        info['additive_candidate_pairs'] = adds
        info['zero_supply_after_additive'] = sorted(p for p in pairs if not supply[p] and not adds.get(p))
        info['additive_watch'] = read(root / 'slovak-additive-20261003-v1/cpu-completion-watch.json')
        info['persian'] = {s: read(root / f'persian-local-v1/{s}/status.json') for s in ('matina', 'tlpc')}
    result['waves'][str(number)] = info
result['observed_processes'] = subprocess.run(
    ['pgrep', '-af', 'advance_wave|advance_baltic|watch_wave4|tokenize_wave|european_stage|qa31|fars.*consumer|balanced.*execute'],
    capture_output=True, text=True, check=False).stdout.splitlines()
result['metadata_sha256'] = pins
(OUT / 'snapshot.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({n: dict(registry=w['registry_counts'], zero=w['zero_supply_pairs'])
                  for n, w in result['waves'].items()}, indent=2))
