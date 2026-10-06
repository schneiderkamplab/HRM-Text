"""Opt-in complete-input traditional headlines plus the expanded DFM suite."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dfm12.io import write_json
from scripts import log_dfm5_headline_averages as legacy
from scripts.headline_population_registry import Artifacts, definition_hash, load_registry, strict_json
from scripts.log_multilingual_headline_averages import PopulationItem

ROOT = Path(__file__).resolve().parents[1]
HEADLINE = 'headline_avg_dala_v2'
SUITE = 'suite_avg_dala_v2'
PREFIXES = frozenset((HEADLINE, SUITE))
OLD_TALEMAADER = 'dfm_eval/generative-talemaader/model_graded_fact/accuracy'
TALEMAADER = 'dfm_eval/generative-talemaader/model_graded_fact_v2/accuracy'
REGISTRIES = (
    ROOT/'config/dfm13_dala_heldout_registry_20261006.json',
    ROOT/'config/dfm13_dala_v2_existing21_registry_20261006.json',
)
POPULATIONS = ROOT/'config/multilingual_headline_populations_dfm13_dala_v2_20261006.json'


def definition():
    population = next(p for p in load_registry(POPULATIONS)['populations']
                      if p['id'] == 'dfm13_all_languages_v2')
    bindings = {b['key']: b for tasks in population['metrics'].values()
                for b in tasks.values() if b and b['suite'] == 'dfm'}
    added = []
    for path, expected in zip(REGISTRIES, (26, 42)):
        tasks = strict_json(path.read_text())
        if len(tasks) != expected or len({t['name'] for t in tasks}) != expected:
            raise ValueError('Wrong new DaLA task population: '+str(path))
        for task in tasks:
            metric = 'exact_match/mean' if task['name'].startswith('gec_dala_') else 'semantic_v1/macro_f1'
            key = f"dfm_eval/{task['name']}/{metric}"
            if key not in bindings or bindings[key]['scale'] != 'fraction':
                raise ValueError('Missing explicit v2 metric binding: '+key)
            added.append(key)
    if len(set(added)) != 68:
        raise ValueError('Duplicate expanded metric')
    replace = lambda keys: [TALEMAADER if k == OLD_TALEMAADER else k for k in keys]
    sections = {name: replace(keys) for name, keys in legacy.SECTION_KEYS.items()}
    for section, language in [('danish', 'da'), ('english', 'en')]:
        pair = [f'dfm_eval/dala_v2_{language}/semantic_v1/macro_f1',
                f'dfm_eval/gec_dala_v2_{language}/exact_match/mean']
        if not set(pair) <= set(added):
            raise ValueError('Missing Danish/English v2 pair')
        sections[section].extend(pair)
    suite = replace(legacy.SUITE_KEYS['dfm']) + added
    if len(set(suite)) != len(suite):
        raise ValueError('Double-counted DFM suite metric')
    return dict(sections=sections, dfm=suite, added=added,
                weighting='equal tasks within each of eight traditional sections; equal sections overall; no multilingual addition; equal unique DFM suite tasks',
                normalization='legacy normalize_metric_0_1 for historical tasks; new DaLA and Talemaader strict fraction',
                completeness='all required inputs across both namespaces before any scores',
                inputs={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in (*REGISTRIES, POPULATIONS)})


def compute(metrics, item, recipe=None):
    recipe = recipe or definition()
    required = set(recipe['dfm']).union(*(set(keys) for keys in recipe['sections'].values()))
    strict = set(recipe['added']) | {TALEMAADER}
    values, invalid = {}, []
    for key in sorted(required):
        raw = metrics.get(key)
        if (type(raw) not in (int, float) or not math.isfinite(raw)
                or raw < 0 or (key in strict and raw > 1)):
            invalid.append(key)
            continue
        value = legacy.normalize_metric_0_1(key, raw)
        if value is None or not 0 <= value <= 1:
            invalid.append(key)
        else:
            values[key] = value
    report = dict(complete=not invalid, missing_or_invalid=invalid, definition=recipe,
                  definition_sha256=definition_hash(recipe), required_count=len(required))
    if invalid:
        return {}, report
    averages = {name: math.fsum(values[k] for k in keys)/len(keys)
                for name, keys in recipe['sections'].items()}
    row = {f'{p}/{axis}': value for p in (HEADLINE, SUITE)
           for axis, value in [('epoch', item.epoch), ('train_step', item.step),
                               ('definition_sha256', report['definition_sha256'])]}
    for name in ('danish', 'english'):
        row.update({f'{HEADLINE}/{name}': averages[name],
                    f'{HEADLINE}/{name}/count': len(recipe['sections'][name])})
    row.update({f'{HEADLINE}/overall': math.fsum(averages.values())/len(averages),
                f'{HEADLINE}/overall/section_count': len(averages),
                f'{SUITE}/dfm': math.fsum(values[k] for k in recipe['dfm'])/len(recipe['dfm']),
                f'{SUITE}/dfm/count': len(recipe['dfm'])})
    report['section_means'] = averages
    return row, report


def collect(item, recipe):
    artifacts = Artifacts(item)
    required = set(recipe['dfm']).union(*(set(keys) for keys in recipe['sections'].values()))
    strict = set(recipe['added']) | {TALEMAADER}
    metrics, evidence = {}, {}
    for key in sorted(required):
        suite = 'standard' if key.startswith('eval/') else 'dfm' if key.startswith('dfm_eval/') else 'euroeval'
        _, detail = artifacts.resolve(dict(suite=suite, key=key,
            scale='fraction' if key in strict else 'percent'))
        if detail['status'] == 'valid':
            _, _, document = artifacts.read(Path(detail['path']))
            for axis, expected in [('step', item.step), ('epoch', item.epoch)]:
                if axis in document and (type(document[axis]) not in (int, float)
                                         or document[axis] != expected):
                    detail = {**detail, 'status': 'checkpoint_mismatch', 'axis': axis}
            if key == TALEMAADER:
                n = document.get('metrics', document).get(TALEMAADER.rsplit('/', 1)[0]+'/n')
                if (type(n) not in (int, float) or not math.isfinite(n) or n <= 0
                        or not float(n).is_integer() or n != document.get('num_samples')):
                    detail = {**detail, 'status': 'incomplete_talemaader_v2'}
        if detail['status'] == 'valid':
            metrics[key] = detail['raw_value']
            detail = {**detail, 'normalized': legacy.normalize_metric_0_1(key, detail['raw_value']),
                      'normalization': 'strict_fraction' if key in strict else 'legacy_metric_normalization'}
        evidence[key] = detail
    return metrics, evidence


def log_atomic(wandb, row, args):
    run = wandb.init(project=args.project, id=args.run_id, name=args.run_name,
                     entity=args.entity, resume='must')
    try:
        for prefix in sorted({k.split('/')[0] for k in row}):
            axis = prefix+'/epoch'
            wandb.define_metric(axis)
            for key in sorted(k for k in row if k.startswith(prefix+'/') and k != axis):
                wandb.define_metric(key, step_metric=axis, summary='last')
        wandb.log(row, commit=True)
    finally:
        run.finish()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metric-prefix', choices=sorted(PREFIXES), help='Omit to emit both new namespaces atomically')
    for suite in ('standard', 'dfm', 'euroeval'):
        parser.add_argument(f'--{suite}-root', f'--additional-{suite}-root', dest=suite+'_root',
                            type=Path, action='append', default=[])
    parser.add_argument('--step', type=int, required=True)
    parser.add_argument('--epoch', type=float, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--project')
    parser.add_argument('--run-id')
    parser.add_argument('--run-name')
    parser.add_argument('--entity', default='peter-sk-sdu')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    if args.step < 0 or not math.isfinite(args.epoch) or args.epoch < 0:
        parser.error('Finite nonnegative checkpoint axes required')
    if not args.dry_run and not all((args.project, args.run_id, args.run_name)):
        parser.error('W&B run identity required unless --dry-run')
    item = PopulationItem(args.step, args.epoch, args.standard_root, args.dfm_root, args.euroeval_root)
    recipe = definition()
    metrics, evidence = collect(item, recipe)
    row, report = compute(metrics, item, recipe)
    if args.metric_prefix:
        row = {k: v for k, v in row.items() if k.startswith(args.metric_prefix+'/')}
    report['artifacts'] = evidence
    write_json(args.report, dict(row=row, coverage=report))
    if not report['complete']:
        raise ValueError('Expanded averages incomplete; no metrics emitted. See '+str(args.report))
    print(json.dumps(row, sort_keys=True, allow_nan=False))
    if not args.dry_run:
        import wandb
        log_atomic(wandb, row, args)
    return row, report


if __name__ == '__main__':
    main()
