"""Version acceptability-dependent populations and queue CPU-only recalculation."""
import argparse
import copy
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
from eval_scheduler.model import Action, JobStatus, read_plan, write_plan
from eval_scheduler.locking import PlanLock
from scripts.headline_population_registry import validate_registry

VERSIONS = {'multilingual_v1': 'multilingual_v2', 'english_dfm_v1': 'english_dfm_v2',
            'english_v2': 'english_v3', 'cross_language_v1': 'cross_language_v2'}
MANIFESTS = {
    'multilingual_headline_populations_20260930.json': 'multilingual_headline_populations_semantic_v1.json',
    'cross_language_average_v1.json': 'cross_language_average_v2.json',
}


def semantic_registry(original):
    result = copy.deepcopy(original)
    for population in result['populations']:
        population['id'] = VERSIONS[population['id']]
        changed = 0
        for bindings in population['metrics'].values():
            for binding in bindings.values():
                if binding and binding['key'].endswith('/linguistic-acceptability/dfm_evals_macro_f1'):
                    binding['key'] = binding['key'].replace(
                        '/linguistic-acceptability/dfm_evals_macro_f1', '/semantic_v1/macro_f1')
                    changed += 1
        if not changed:
            raise ValueError('No acceptability binding in population')
    return validate_registry(result)


def extend(jobs):
    result = list(jobs)
    ids = {job.job_id for job in jobs}
    for job in jobs:
        if job.action != Action.AVERAGE or job.metadata.get('semantic_acceptability_version'):
            continue
        manifest = Path(job.metadata.get('multilingual_manifest', '')).name
        if manifest not in MANIFESTS:
            continue
        identifier = job.job_id + '-semantic-v1'
        if identifier in ids:
            continue
        meta = {**job.metadata, 'semantic_acceptability_version': 1,
                'multilingual_manifest': str(ROOT / 'config' / MANIFESTS[manifest])}
        result.append(job.with_updates(job_id=identifier, name=job.name + '-semantic-v1',
            status=JobStatus.PENDING, attempt=0, metadata=meta,
            log_dir=str(Path(job.log_dir) / 'semantic-v1')))
        ids.add(identifier)
    return result


def extend_legacy(jobs):
    """Keep legacy history intact; append semantic headline/suite counterparts."""
    result = list(jobs)
    ids = {job.job_id for job in jobs}
    templates = [j for j in jobs if j.action == Action.AVERAGE
                 and j.metadata.get('average_prefix') == 'headline_avg_v3'
                 and not j.metadata.get('multilingual_manifest')]
    if not templates:
        raise ValueError('Missing legacy average template')
    for job in templates:
        identifier = job.job_id + '-semantic-v1'
        if identifier in ids:
            continue
        meta = {**job.metadata, 'average_prefix': 'headline_avg_semantic_v1',
                'extra_average_prefixes': ['suite_avg_semantic_v1'],
                'atomic_v3_averages': False, 'semantic_acceptability_version': 1}
        result.append(job.with_updates(job_id=identifier, name='semantic-checkpoint-averages',
            metadata=meta, status=JobStatus.PENDING, attempt=0,
            log_dir=str(Path(job.log_dir) / 'semantic-v1')))
    identifier = 'epoch_10-legacy-averages-semantic-v1'
    if identifier not in ids:
        baseline = next(j for j in jobs if j.job_id == 'dfm12-multilingual-epoch_10-average')
        template = templates[0]
        meta = {**template.metadata, **{k: baseline.metadata[k] for k in
                ('eval_epoch', 'eval_step', 'ckpt_tag', 'checkpoint_tag', 'ckpt_path')},
                'log_root': 'logs/eval/dfm11_XL_epoch10/epoch_10',
                'dfm_log_root': 'logs/dfm_evals/dfm11_XL_epoch10/epoch_10',
                # Copies bind historical zero-step metrics to the verified
                # completed epoch-10 export, without modifying their scores.
                'euroeval_log_root': 'data/eval/dfm11-xl-epoch10-semantic-headlines',
                'average_prefix': 'headline_avg_semantic_v1',
                'extra_average_prefixes': ['suite_avg_semantic_v1'],
                'atomic_v3_averages': False, 'semantic_acceptability_version': 1}
        result.append(template.with_updates(job_id=identifier, name='semantic-checkpoint-averages',
            deps=(baseline.job_id,), metadata=meta, status=JobStatus.PENDING, attempt=0,
            log_dir=str(Path(baseline.log_dir) / 'legacy-semantic-v1')))
    return result


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--include-legacy', action='store_true')
    parser.add_argument('--plan-dir', type=Path,
        default=ROOT / 'logs/scheduler/dfm12_XL_epoch11_noidentity')
    args = parser.parse_args()
    for source, destination in MANIFESTS.items():
        data = semantic_registry(json.loads((ROOT / 'config' / source).read_text()))
        path = ROOT / 'config' / destination
        if path.exists() and json.loads(path.read_text()) != data:
            raise ValueError('Refusing changed versioned definition: ' + str(path))
        path.write_text(json.dumps(data, indent=2) + '\n')
    with PlanLock(args.plan_dir):
        jobs = read_plan(args.plan_dir / 'plan.tsv')
        result = extend(jobs)
        if args.include_legacy:
            result = extend_legacy(result)
        added = [job.job_id for job in result[len(jobs):]]
        if args.apply and added:
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            write_plan(args.plan_dir / f'plan.before-semantic-averages-{stamp}.tsv', jobs)
            write_plan(args.plan_dir / 'plan.tsv', result)
        print(json.dumps({'apply': args.apply, 'new_cpu_rows': added}, indent=2))


if __name__ == '__main__':
    main()
