#!/usr/bin/env python3
"""CPU-only average preparation. Never initializes W&B or writes source artifacts."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import subprocess

from scripts import log_dfm5_headline_averages as legacy
from scripts.headline_population_registry import definition_hash, load_registry, normalize

RUN = 'peter-sk-sdu/DFM5/dfm8-xl-from-dfm6-dfm7-epoch5-clean-full'
OLD = 'dfm_eval/generative-talemaader/model_graded_fact/accuracy'
NEW = 'dfm_eval/generative-talemaader/model_graded_fact_v2/accuracy'
HP = 'headline_avg_semantic_v2'
SP = 'suite_avg_semantic_v2'
THP = 'headline_avg_talemaader_v2'
TSP = 'suite_avg_talemaader_v2'
NAMESPACES = ('eval', 'dfm_eval', 'euroeval', 'headline_avg_v3', 'suite_avg_v3',
              'headline_avg_semantic_v1', 'suite_avg_semantic_v1')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def definitions():
    def replace(keys):
        return [NEW if k == OLD else legacy.SEMANTIC_DALA_KEY
                if k == legacy.STRICT_DALA_KEY else k for k in keys]
    return dict(sections={k: replace(v) for k, v in legacy.SECTION_KEYS.items()},
                dfm=replace(legacy.SUITE_KEYS['dfm']),
                normalization='legacy normalize_metric_0_1',
                weighting='equal observed tasks per section; equal observed sections overall',
                required_replacements=[NEW, legacy.SEMANTIC_DALA_KEY],
                unchanged=['english', 'math_code', 'mc9', 'gen5', 'code4', 'math2', 'flexolmo_extras'])


def talemaader_only(metrics, point):
    """Uniform current membership, strict DaLA, old scorer replaced only."""
    sections = {name: [NEW if k == OLD else k for k in keys]
                for name, keys in legacy.SECTION_KEYS.items()}
    suite = [NEW if k == OLD else k for k in legacy.SUITE_KEYS['dfm']]
    definition = dict(sections=sections, dfm=suite, dala='strict_only',
                      weighting='equal available tasks per section; equal available current sections overall; no multilingual')
    row = {prefix+'/'+axis: point[field] for prefix in (THP,TSP)
           for axis,field in [('epoch','epoch'),('train_step','train_step')]}
    report = {'definition':definition, 'missing_inputs':{}, 'recipe':'fixed current membership, not historical recipe replay'}
    valid_new = normalize(metrics.get(NEW), 'fraction') is not None
    values = []
    for name, keys in sections.items():
        avg,count = legacy.section_average(metrics,keys)
        report['missing_inputs'][name] = [k for k in keys if k not in metrics or legacy.normalize_metric_0_1(k,metrics[k]) is None]
        if avg is not None:
            values.append(avg)
        # English/math/etc are used unchanged, not republished under new keys.
        if name == 'danish':
            row.update({THP+'/danish/count':count, THP+'/danish/expected_count':len(keys), THP+'/danish/complete':int(count==len(keys))})
            if valid_new and avg is not None:
                row[THP+'/danish']=avg
    avg,count = legacy.section_average(metrics,suite)
    report['missing_inputs']['dfm']=[k for k in suite if k not in metrics or legacy.normalize_metric_0_1(k,metrics[k]) is None]
    row.update({TSP+'/dfm/count':count,TSP+'/dfm/expected_count':len(suite),TSP+'/dfm/complete':int(count==len(suite)),
                THP+'/overall/section_count':len(values),THP+'/overall/expected_section_count':len(sections),
                THP+'/overall/complete':int(all(not report['missing_inputs'][s] for s in sections))})
    if valid_new and avg is not None:
        row[TSP+'/dfm']=avg
    if valid_new and values:
        row[THP+'/overall']=math.fsum(values)/len(values)
    for prefix in (THP,TSP):
        row[prefix+'/definition_sha256']=definition_hash(definition)
    return row,report


def compute(metrics, point, registry):
    """Reuse historical membership/normalization; never substitute missing v2."""
    defs = definitions()
    row = {f'{p}/{axis}': point[field] for p in (HP, SP, 'avg_population')
           for axis, field in [('epoch', 'epoch'), ('train_step', 'train_step')]}
    report = {'missing_replacements': [k for k in defs['required_replacements']
              if normalize(metrics.get(k), 'fraction') is None], 'populations': {}}
    averages = {name: legacy.section_average(metrics, keys)
                for name, keys in defs['sections'].items()}
    for prefix, label, keys in [(HP, 'danish', defs['sections']['danish']),
                                (SP, 'dfm', defs['dfm'])]:
        avg, count = legacy.section_average(metrics, keys)
        row[f'{prefix}/{label}/count'] = count
        row[f'{prefix}/{label}/expected_count'] = len(keys)
        if not report['missing_replacements'] and avg is not None:
            row[f'{prefix}/{label}'] = avg
    if not report['missing_replacements']:
        values = [v for v, n in averages.values() if v is not None]
        if values:
            row[f'{HP}/overall'] = math.fsum(values) / len(values)
    row[f'{HP}/overall/section_count'] = sum(v is not None for v, n in averages.values())
    row[f'{HP}/definition_sha256'] = definition_hash(defs)
    row[f'{SP}/definition_sha256'] = definition_hash(defs)
    report['section_counts'] = {k: n for k, (v, n) in averages.items()}
    for pop in registry['populations']:
        base = 'avg_population/' + pop['id']
        means, valid, missing = [], 0, {}
        expected = sum(len(pop['metrics'][lang]) for lang in pop['languages'])
        for lang in pop['languages']:
            vals, absent = [], []
            for task, binding in pop['metrics'][lang].items():
                val = normalize(metrics.get(binding['key']), binding['scale']) if binding else None
                if val is None:
                    absent.append(task)
                else:
                    vals.append(val)
            valid += len(vals)
            lb = f'{base}/languages/{lang}'
            row.update({lb+'/valid_tasks': len(vals), lb+'/expected_tasks': len(pop['metrics'][lang]),
                        lb+'/complete': int(not absent)})
            if absent:
                missing[lang] = absent
            else:
                means.append(math.fsum(vals)/len(vals))
                row[lb+'/score'] = means[-1]
        row.update({base+'/complete': int(not missing), base+'/coverage': valid/expected,
                    base+'/valid_metrics': valid, base+'/expected_metrics': expected,
                    base+'/expected_languages': len(pop['languages']), base+'/complete_languages': len(means),
                    base+'/definition_sha256': definition_hash(pop)})
        if not missing:
            row[base+'/score'] = math.fsum(means)/len(means)
        report['populations'][pop['id']] = {'missing': missing, 'complete': not missing}
    return row, report


def load_history(paths, points):
    """Read original sparse history per namespace, not W&B's internal _step."""
    result = {p['id']: {} for p in points}
    by_epoch = {p['epoch']: p for p in points}
    conflicts = []
    for path in paths:
        for line in Path(path).read_text().splitlines():
            entry = json.loads(line)
            row = entry.get('row', entry)
            for namespace in NAMESPACES:
                epoch = row.get(namespace+'/epoch')
                point = by_epoch.get(epoch)
                if point is None:
                    continue
                step = row.get(namespace+'/train_step')
                if step not in (None, point['train_step']) and not (step == 0 and epoch in (5, 10)):
                    raise ValueError('History checkpoint axes disagree')
                for key, value in row.items():
                    if not key.startswith(namespace+'/') or key.endswith(('/epoch', '/train_step')):
                        continue
                    if type(value) not in (int, float) or not math.isfinite(value):
                        continue
                    prior = result[point['id']].get(key)
                    if prior is not None and prior != value:
                        conflicts.append((point['id'], key))
                    result[point['id']][key] = value
    if conflicts:
        raise ValueError('Conflicting historical metrics; supply resolved source snapshot: '+str(conflicts[:5]))
    return result


def fetch_history(manifest, populations, output):
    """Read-only sparse API snapshot; retain latest-per-key selection evidence."""
    import wandb
    inventory = json.loads(manifest.read_text())
    if inventory['run_path'] != RUN:
        raise ValueError('Wrong run')
    registry = load_registry(populations)
    keys = set(k for ks in definitions()['sections'].values() for k in ks)
    keys.update(definitions()['dfm'])
    keys.update((OLD, legacy.STRICT_DALA_KEY))
    for prefix in NAMESPACES[3:]:
        for name in (('dfm',) if prefix.startswith('suite') else ('danish', 'overall')):
            keys.update((prefix+'/'+name, prefix+'/'+name+'/count'))
    for pop in registry['populations']:
        keys.update(b['key'] for bs in pop['metrics'].values() for b in bs.values() if b)
    run = wandb.Api(timeout=90).run(RUN)
    available = run.history_keys['keys']
    keys = sorted(keys.intersection(available))
    by_epoch = {p['epoch']: p for p in inventory['points']}
    selected, evidence, rejected_axes, absent_axes = {}, {}, [], []
    query = '''query RunSampledHistory($project: String!, $entity: String!, $name: String!, $specs: [JSONString!]!) {
      project(name: $project, entityName: $entity) { run(name: $name) { sampledHistory(specs: $specs) } }
    }'''
    for offset in range(0, len(keys), 24):
        batch = keys[offset:offset+24]
        specs = []
        for key in batch:
            ns = key.split('/')[0]
            count = sum(c['count'] for c in available[key].get('typeCounts', []))
            for stamps in ([ns+'/epoch'], [ns+'/epoch', ns+'/train_step']):
                specs.append(json.dumps({'keys': ['_step', *stamps, key],
                                         'samples': max(10000, count+100)}))
        histories = run._exec(query, specs=specs)['project']['run']['sampledHistory']
        for i, key in enumerate(batch):
            history, stamped = histories[2*i:2*i+2]
            stamped = {r['_step']: r for r in stamped}
            ns = key.split('/')[0]
            for row in history:
                row = stamped.get(row['_step'], row)
                p = by_epoch.get(row.get(ns+'/epoch'))
                if not p or key not in row:
                    continue
                stamp = row.get(ns+'/train_step')
                if stamp is not None and stamp != p['train_step'] and not (stamp == 0 and p['epoch'] in (5, 10)):
                    rejected_axes.append({'id':p['id'], 'key':key, 'row':row, 'reason':'checkpoint_axis_mismatch'})
                    continue
                if stamp is None:
                    absent_axes.append({'id':p['id'], 'key':key, 'history_step':row['_step'], 'binding':'exact manifest epoch; train_step absent'})
                identity = (p['id'], key)
                event = {'history_step': row['_step'], 'value': row[key]}
                evidence.setdefault(p['id'], {}).setdefault(key, []).append(event)
                if identity not in selected or row['_step'] > selected[identity]['history_step']:
                    selected[identity] = event
        print('Read-only history keys', min(offset+24, len(keys)), '/', len(keys), flush=True)
    rows = []
    for p in inventory['points']:
        row = {key: event['value'] for (ident, key), event in selected.items() if ident == p['id']}
        for ns in NAMESPACES:
            row[ns+'/epoch'] = p['epoch']; row[ns+'/train_step'] = p['train_step']
        rows.append({'row': row})
    output.parent.mkdir(parents=True, exist_ok=True)
    # Immutable snapshots: a subsequent refresh must use a new filename.
    with output.open('x') as f:
        for row in rows:
            f.write(json.dumps(row, allow_nan=False)+'\n')
    receipt = output.with_suffix(output.suffix+'.receipt.json')
    with receipt.open('x') as f:
        json.dump({'run_path': RUN, 'sha256': digest(output), 'selection': 'latest _step per exact metric and checkpoint; no averages read',
                   'history': evidence, 'requested_available_keys': keys, 'rejected_axes':rejected_axes,
                   'absent_train_step_axes':absent_axes,
                   'point_metric_counts': {p['id']:sum(ident==p['id'] for ident,key in selected) for p in inventory['points']}}, f, indent=2)
    return output


def prepare(manifest, rejudge, history, populations, output):
    inventory = json.loads(manifest.read_text())
    if inventory['run_path'] != RUN:
        raise ValueError('This preparation is scoped to the current XL run only')
    registry = load_registry(populations)
    points = inventory['points']
    metrics = load_history(history, points)
    result = {'run_path': RUN, 'sync_policy': 'single writer at authorized 3154500 or 3200000 pause; never alongside training',
              'inputs': {str(p.resolve()): digest(p) for p in [manifest, populations, Path(__file__), Path(legacy.__file__), *history]},
              'definitions': definitions(), 'points': [], 'rows': []}
    for point in points:
        sidecar = rejudge / (point['id']+'.json')
        if sidecar.exists():
            d = json.loads(sidecar.read_text())
            if any(d['point'][k] != point[k] for k in ('id', 'epoch', 'train_step', 'inputs', 'expected_n')):
                raise ValueError('Rejudge point/input mismatch: '+point['id'])
            r = d['row']
            if r.get('dfm_eval/epoch') != point['epoch'] or r.get('dfm_eval/train_step') != point['train_step']:
                raise ValueError('Rejudge axes mismatch')
            if normalize(r.get(NEW), 'fraction') is None:
                raise ValueError('Invalid rejudge accuracy')
            if r.get(NEW.rsplit('/', 1)[0]+'/n') != point['expected_n']:
                raise ValueError('Incomplete rejudge sample count')
            metrics[point['id']][NEW] = r[NEW]
            result['inputs'][str(sidecar.resolve())] = digest(sidecar)
        row, report = compute(metrics[point['id']], point, registry)
        strict_row, strict_report = talemaader_only(metrics[point['id']],point)
        row.update(strict_row)
        report['talemaader_only'] = strict_report
        report['original_average_crosschecks'] = {}
        for prefix in NAMESPACES[3:]:
            for label in (('dfm',) if prefix.startswith('suite') else ('danish', 'overall')):
                key = prefix+'/'+label
                if key not in metrics[point['id']]:
                    report['original_average_crosschecks'][key] = {'status':'original_average_absent'}
                    continue
                def original_keys(keys):
                    return [legacy.SEMANTIC_DALA_KEY if 'semantic' in prefix and k==legacy.STRICT_DALA_KEY else k for k in keys]
                if label == 'overall':
                    vals = [legacy.section_average(metrics[point['id']],original_keys(ks))[0] for ks in legacy.SECTION_KEYS.values()]
                    vals = [v for v in vals if v is not None]
                    value = sum(vals)/len(vals) if vals else None
                else:
                    ks = legacy.SUITE_KEYS['dfm'] if label=='dfm' else legacy.DANISH_KEYS
                    value, _ = legacy.section_average(metrics[point['id']], original_keys(ks))
                original = metrics[point['id']][key]
                report['original_average_crosschecks'][key] = dict(status='matches' if value is not None and math.isclose(value, original, abs_tol=1e-9) else 'mismatch', original=original, reconstructed=value)
        report['source_metric_count'] = len(metrics[point['id']])
        report['blocked_reasons'] = ['missing_or_invalid_required_metric:'+k for k in report['missing_replacements']]
        if any(x['status']=='mismatch' for x in report['original_average_crosschecks'].values()):
            report['blocked_reasons'].append('original_average_reconstruction_mismatch')
            for key in (HP+'/danish', HP+'/overall', SP+'/dfm'):
                row.pop(key, None)
        report['talemaader_only']['original_average_mismatch_is_warning'] = True
        result['points'].append(dict(id=point['id'], epoch=point['epoch'], train_step=point['train_step'],
                                     rejudge_available=sidecar.exists(), coverage=report))
        result['rows'].append(row)
    result['rows_sha256'] = definition_hash(result['rows'])
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=output.parent)
    with os.fdopen(fd, 'w') as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(temporary, output)
    return result


def sync_prepared(path, paused_step, wandb_module=None):
    """Explicit scheduler-only action. Refuse active training and uncertain replay."""
    if paused_step not in (3154500, 3200000):
        raise ValueError('Only the authorized 3154500 or 3200K pause is supported')
    processes = subprocess.check_output(['ps', '-eo', 'args='], text=True)
    if any('pretrain.py' in line and any(x in line for x in ('python', 'torchrun'))
           for line in processes.splitlines()):
        raise RuntimeError('Training process present; no concurrent W&B writer permitted')
    d = json.loads(path.read_text())
    if d['run_path'] != RUN or definition_hash(d['rows']) != d['rows_sha256']:
        raise ValueError('Prepared payload binding mismatch')
    for name, sha in d['inputs'].items():
        if digest(name) != sha:
            raise ValueError('Prepared input changed: '+name)
    if not all(p['rejudge_available'] for p in d['points']):
        raise ValueError('Rejudge incomplete; refresh preparation after all sidecars finish')
    prefixes = (HP+'/', SP+'/', THP+'/', TSP+'/', 'avg_population/')
    if any(not k.startswith(prefixes) for row in d['rows'] for k in row):
        raise ValueError('Forbidden legacy/raw metric in prepared rows')
    receipt = path.with_suffix('.synced.json')
    intent = path.with_suffix('.sync-started.json')
    with path.with_suffix('.sync.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if receipt.exists():
            existing = json.loads(receipt.read_text())
            if existing['rows_sha256'] != d['rows_sha256']:
                raise ValueError('Existing sync receipt differs')
            return existing
        if intent.exists():
            raise RuntimeError('Prior sync has uncertain outcome; inspect remote before any retry')
        if wandb_module is None:
            import wandb as wandb_module
        with intent.open('x') as f:
            json.dump({'run_path':RUN, 'rows_sha256':d['rows_sha256'], 'paused_step':paused_step}, f)
        run = wandb_module.init(entity='peter-sk-sdu', project='DFM5',
            id=RUN.rsplit('/',1)[1], resume='must',
            settings=wandb_module.Settings(x_update_finish_state=False))
        try:
            for prefix in (HP, SP, THP, TSP, 'avg_population'):
                wandb_module.define_metric(prefix+'/epoch')
            for key in sorted({k for row in d['rows'] for k in row}):
                prefix = key.split('/')[0]
                if key != prefix+'/epoch':
                    wandb_module.define_metric(key, step_metric=prefix+'/epoch', summary='last')
            for row in d['rows']:
                wandb_module.log(row, commit=True)
            result = dict(run_path=RUN, rows_sha256=d['rows_sha256'], rows=len(d['rows']),
                          next_internal_step=run.step, paused_step=paused_step,
                          resume_warning='Use independent-cursor TrainingWandbLogger on resume; legacy explicit-step callers can drop logs below this high-water mark')
        finally:
            run.finish()
        with receipt.open('x') as f:
            json.dump(result, f, indent=2)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sync-prepared', type=Path, help='Explicit sync ONLY at the authorized scheduler-owned 3154500 or 3200K pause')
    parser.add_argument('--paused-step', type=int)
    parser.add_argument('--manifest', type=Path, default=Path('logs/rejudge_talemaader_v2/manifest.json'))
    parser.add_argument('--rejudge-root', type=Path, default=Path('logs/rejudge_talemaader_v2'))
    parser.add_argument('--history-jsonl', type=Path, action='append', default=[])
    parser.add_argument('--fetch-history', type=Path, help='Create immutable read-only W&B source snapshot before preparing')
    parser.add_argument('--populations', type=Path, default=Path('config/multilingual_headline_populations_dfm13_20261006.json'))
    parser.add_argument('--output', type=Path)
    a = parser.parse_args()
    if a.sync_prepared:
        print(json.dumps(sync_prepared(a.sync_prepared, a.paused_step)))
        return
    if a.output is None:
        parser.error('--output required for preparation')
    if a.fetch_history:
        a.history_jsonl.append(fetch_history(a.manifest, a.populations, a.fetch_history))
    if not a.history_jsonl:
        parser.error('--history-jsonl or --fetch-history required')
    r = prepare(a.manifest, a.rejudge_root, a.history_jsonl, a.populations, a.output)
    print(json.dumps({'points': len(r['points']), 'rejudge_available': sum(p['rejudge_available'] for p in r['points']),
                      'danish_ready': sum(HP+'/danish' in row for row in r['rows'])}))


if __name__ == '__main__':
    main()
