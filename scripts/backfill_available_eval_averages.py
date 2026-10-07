"""Prepare checkpoint-aligned available-input averages; explicitly gated sync."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

from dfm12.io import write_json
from scripts import log_expanded_dala_v2_averages as expanded
from scripts import prepare_talemaader_v2_averages as tal
from scripts.headline_population_registry import (
    build_population_row_from_metrics, enable_available_dfm13, load_registry,
)

RUNS = {'xl': tal.RUN, 'xxl': 'peter-sk-sdu/DFM5/dfm10-xxl-wide'}
CONFIGS = [Path('config/multilingual_headline_populations_dfm13_20261006.json'), expanded.POPULATIONS]
QUERY = '''query RunSampledHistory($project: String!, $entity: String!, $name: String!, $specs: [JSONString!]!) {
 project(name: $project, entityName: $entity) { run(name: $name) { sampledHistory(specs: $specs) } }
}'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def registries():
    populations = {}
    for path in CONFIGS:
        registry = enable_available_dfm13(load_registry(path))
        for p in registry['populations']:
            if p['id'].startswith('dfm13_'):
                populations[p['id']] = p
    registry['populations'] = list(populations.values())
    return registry


def compute(metrics, point, registry=None):
    item = SimpleNamespace(step=point['train_step'], epoch=point['epoch'])
    row, report = expanded.compute(metrics, item)
    population, coverage = build_population_row_from_metrics(metrics, item, registry or registries())
    row.update(population)
    report['populations'] = coverage
    # Available policy omits missing v2, not the other valid tasks. Never alias OLD.
    recipe = expanded.definition()
    recipe['sections'] = {name: [tal.NEW if k == tal.OLD else k for k in keys]
                          for name, keys in tal.legacy.SECTION_KEYS.items()}
    recipe['dfm'] = [tal.NEW if k == tal.OLD else k for k in tal.legacy.SUITE_KEYS['dfm']]
    recipe['added'] = []
    recipe['purpose'] = 'Talemaader-only replacement, strict DaLA retained; available inputs even if raw v2 absent'
    replacement, detail = expanded.compute(metrics, item, recipe)
    for key, value in replacement.items():
        if key.startswith(expanded.HEADLINE+'/english'):
            continue
        key = key.replace(expanded.HEADLINE+'/', tal.THP+'/').replace(expanded.SUITE+'/', tal.TSP+'/')
        row[key] = value
        if key.endswith('/expected'):
            row[key+'_count'] = value
    report['talemaader_only'] = detail
    return row, report


def select(points, events):
    """Bind axes before selecting latest metric; never carry values forward."""
    by_step = {p['train_step']: p for p in points}
    by_epoch = {}
    for p in points:
        by_epoch.setdefault(p['epoch'], []).append(p)
    selected, rejected = {p['id']: {} for p in points}, []
    for event in events:
        step, epoch = event.get('train_step'), event.get('epoch')
        p = by_step.get(step)
        if p is None and (step is None or step == 0):
            matches = by_epoch.get(epoch, [])
            p = matches[0] if len(matches) == 1 else None
        if p is None or epoch is None or not math.isclose(epoch, p['epoch'], abs_tol=1e-9, rel_tol=0):
            rejected.append(event)
            continue
        old = selected[p['id']].get(event['key'])
        if old is None or event['history_step'] > old['history_step']:
            selected[p['id']][event['key']] = event
        elif event['history_step'] == old['history_step'] and event['value'] != old['value']:
            raise ValueError('Conflicting same-event values')
    return selected, rejected


def discover_points(label, events, seed_points=()):
    """Union all raw-suite checkpoint axes; conflicting new axes are not guessed."""
    known = {p['train_step']: dict(p) for p in seed_points}
    candidates, unresolved = {}, []
    for e in events:
        step, epoch = e.get('train_step'), e.get('epoch')
        if label == 'xxl' and step == 0 and epoch == 2:
            step = 754208
        if type(step) not in (int, float) or step <= 0 or not float(step).is_integer():
            continue
        if type(epoch) not in (int, float) or not math.isfinite(epoch):
            continue
        candidates.setdefault(int(step), set()).add(epoch)
    for step, epochs in sorted(candidates.items()):
        if step in known:
            conflicts = [e for e in epochs if not math.isclose(e, known[step]['epoch'], abs_tol=1e-9, rel_tol=0)]
            if conflicts:
                unresolved.append(dict(train_step=step, epochs=sorted(epochs),
                                       resolution='retained authoritative manifest epoch; conflicting events excluded'))
            continue
        if max(epochs)-min(epochs) > 1e-9:
            unresolved.append(dict(train_step=step, epochs=sorted(epochs), resolution='point omitted: conflicting epochs'))
            continue
        known[step] = dict(id=f'step_{step}', train_step=step, epoch=min(epochs))
    return sorted(known.values(), key=lambda p: p['train_step']), unresolved


def check_history_count(key, advertised, rows, requested):
    actual = len({r['_step'] for r in rows})
    if actual < advertised or actual >= requested:
        raise ValueError(f'Incomplete or capped raw history for {key}: {actual} returned, {advertised} advertised, {requested} cap')
    return dict(advertised=advertised, returned=actual, requested=requested,
                complete_against_advertised=True)


def prepare(label, output):
    import wandb
    if output.exists():
        raise ValueError('Use a fresh immutable output path')
    run = wandb.Api(timeout=90).run(RUNS[label])
    registry, recipe = registries(), expanded.definition()
    keys = set(recipe['dfm']).union(*map(set, recipe['sections'].values()))
    for p in registry['populations']:
        keys.update(b['key'] for bs in p['metrics'].values() for b in bs.values() if b)
    keys.add(tal.OLD)  # Inventory only; never aliased into the new scorer.
    available = run.history_keys['keys']
    keys = sorted(keys & available.keys())
    events, history_counts = [], {}
    for start in range(0, len(keys), 20):
        batch, specs = keys[start:start+20], []
        for key in batch:
            ns = key.split('/')[0]
            count = sum(c['count'] for c in available[key].get('typeCounts', []))
            for axes in ([ns+'/epoch'], [ns+'/epoch', ns+'/train_step'], []):
                specs.append(json.dumps(dict(keys=['_step', *axes, key], samples=max(10000, count+100))))
        histories = run._exec(QUERY, specs=specs)['project']['run']['sampledHistory']
        for i, key in enumerate(batch):
            plain, stamped, raw = histories[3*i:3*i+3]
            count = sum(c['count'] for c in available[key].get('typeCounts', []))
            try:
                history_counts[key] = check_history_count(key, count, raw, max(10000, count+100))
            except ValueError:
                # Metadata counters can exceed even exhaustive history results.
                # Preserve the discrepancy, but use actual rows, never fake a value.
                print('Verifying count discrepancy with full sparse scan:', key, flush=True)
                scanned = list(run.scan_history(keys=['_step', key], page_size=100000))
                if {r['_step'] for r in scanned} != {r['_step'] for r in raw}:
                    ns = key.split('/')[0]
                    plain = list(run.scan_history(keys=['_step', key, ns+'/epoch'], page_size=100000))
                    stamped = list(run.scan_history(keys=['_step', key, ns+'/epoch', ns+'/train_step'], page_size=100000))
                raw = scanned
                history_counts[key] = dict(advertised=count, returned=len(raw),
                    complete_against_advertised=len(raw) >= count,
                    exhaustive_sparse_scan=True, metadata_count_discrepancy=count-len(raw))
            history_counts[key]['with_epoch'] = len(plain)
            history_counts[key]['with_epoch_and_train_step'] = len(stamped)
            combined = {r['_step']: r for r in plain}
            combined.update({r['_step']: r for r in stamped})
            ns = key.split('/')[0]
            for history_step, r in combined.items():
                value = r.get(key)
                if type(value) in (int, float) and math.isfinite(value):
                    events.append(dict(key=key, value=value, history_step=history_step,
                                       epoch=r.get(ns+'/epoch'), train_step=r.get(ns+'/train_step')))
        print(label, 'raw keys', min(start+20, len(keys)), '/', len(keys), flush=True)
    if label == 'xl':
        points = json.loads(Path('logs/rejudge_talemaader_v2/manifest.json').read_text())['points']
        points = [{k: p[k] for k in ('id', 'epoch', 'train_step')} for p in points]
    else:
        points = []
    points, discovery_conflicts = discover_points(label, events, points)
    selected, rejected = select(points, events)
    prepared = []
    for p in sorted(points, key=lambda x: x['train_step']):
        metrics = {k: e['value'] for k, e in selected[p['id']].items()}
        row, coverage = compute(metrics, p, registry)
        prepared.append(dict(point=p, row=row, coverage=coverage, raw_metrics=metrics,
                             evidence=selected[p['id']]))
    pins = [Path(__file__), Path(expanded.__file__), Path(tal.__file__),
            Path('scripts/headline_population_registry.py'), Path('scripts/log_dfm5_headline_averages.py'),
            *CONFIGS, *expanded.REGISTRIES]
    result = dict(schema='available-historical-averages-v1', run_path=RUNS[label],
                  points=prepared, rejected_axes=rejected, raw_events=events,
                  history_counts=history_counts, discovery_conflicts=discovery_conflicts,
                  pins={str(p.resolve()): sha(p) for p in pins},
                  policy='available raw metrics only, no old-scorer alias or zero imputation')
    result['payload_sha256'] = canonical_hash(result)
    write_json(output, result)
    print('Prepared', len(points), 'points:', output, flush=True)


def sync(path, permit):
    """Permit is supplied by the scheduler owner after serializing run writers."""
    import wandb
    payload = json.loads(path.read_text())
    expected = payload.pop('payload_sha256')
    if canonical_hash(payload) != expected:
        raise ValueError('Payload changed')
    for source, digest in payload['pins'].items():
        if sha(source) != digest:
            raise ValueError('Implementation/definition changed: '+source)
    authorization = json.loads(permit.read_text())
    if (authorization.get('run_path') != payload['run_path'] or
            authorization.get('payload_sha256') != expected or
            authorization.get('exclusive_writer_confirmed') is not True):
        raise ValueError('Missing exact serialized writer authorization')
    receipt = path.with_suffix('.synced.json')
    started = path.with_suffix('.sync-started.json')
    with Path('/tmp/dfm-average-'+payload['run_path'].split('/')[-1]+'.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if receipt.exists():
            if json.loads(receipt.read_text())['payload_sha256'] != expected:
                raise ValueError('Receipt mismatch')
            return
        if started.exists():
            raise ValueError('Uncertain prior append: inspect remote before retry')
        entity, project, run_id = payload['run_path'].split('/')
        write_json(started, dict(payload_sha256=expected, permit=authorization))
        run = wandb.init(entity=entity, project=project, id=run_id, resume='must')
        registered = set()
        for point in payload['points']:
            row = point['row']
            for key in row:
                if key not in registered:
                    axis = key.split('/')[0]+'/epoch'
                    run.define_metric(key, **({} if key == axis else {'step_metric': axis}))
                    registered.add(key)
            run.log(row, commit=True)
        run.finish()
        write_json(receipt, dict(payload_sha256=expected, run_path=payload['run_path'],
                                 points=len(payload['points']), status='synced'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--run', choices=RUNS, required=True)
    prep.add_argument('--output', type=Path, required=True)
    push = sub.add_parser('sync')
    push.add_argument('--payload', type=Path, required=True)
    push.add_argument('--permit', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.run, args.output)
    else:
        sync(args.payload, args.permit)


if __name__ == '__main__':
    main()
