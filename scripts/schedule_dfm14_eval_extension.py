"""Append new-language baseline/future evals under the live plan lock."""
import argparse
import copy
from pathlib import Path

from scripts.schedule_dfm13_wave34_baseline import (
    PLAN, ROOT, Action, JobStatus, PlanLock, read_plan, write_plan,
    boundary, check_graph, canonical_log_dir, file_hash, load, write_json)
from scripts.prepare_dfm14_eval_extension import REGISTRY, POPULATION, OUT

FLAG = 'dfm14_eval_50_languages'
CONTROL = ROOT/'data/dfm14/eval-plan-extension'


def build(jobs, registry):
    if any(j.metadata.get(FLAG) for j in jobs):
        raise ValueError('DFM14 eval extension already installed')
    additions, gates, gpu_jobs = [], {}, {}
    steps = sorted({boundary(j) for j in jobs if j.action == Action.EXPORT_HF and boundary(j) >= 3250000})
    assert steps and steps[0] == 3250000
    for step in steps:
        block = [j for j in jobs if boundary(j) == step and j.action != Action.TRAIN_UNTIL_STEP]
        lifecycle = {Action.TERMINAL_BARRIER, Action.TEARDOWN_EVAL}
        if any(j.attempt or (j.status not in (JobStatus.PENDING, JobStatus.SKIPPED)
                            and not (j.action in lifecycle and j.status == JobStatus.DONE)) for j in block):
            raise ValueError('Eval boundary already attempted: '+str(step))
        export = next(j for j in block if j.action == Action.EXPORT_HF)
        tag = export.metadata['ckpt_tag']
        prefix = f'dfm14-eval-{step}-'
        root = ROOT/'logs/dfm_evals/dfm14_extension'/tag
        ids, merges = [], []
        for task in registry:
            family = 'gec_dala_' if task['name'].startswith('gec_') else 'dala_'
            template = next(j for j in block if j.action == Action.EVAL_DFM and j.name.startswith(family))
            merge_template = next(j for j in block if j.action == Action.MERGE_DFM and j.name == template.name)
            meta = {**copy.deepcopy(template.metadata), FLAG: True,
                    'dfm_suite': task['suite'], 'dfm_single_tasks_config': task['config'],
                    'language': task['language'], 'dfm_max_gen_toks': task['max_tokens'],
                    'dfm_log_root': str(root), 'template_job_id': template.job_id,
                    'capacity_inheritance': 'calibrated LA/GEC family; four paired shards'}
            assert meta['fix_mistral_regex'] is False
            assert meta['wandb_run_id'] == 'dfm8-xl-from-dfm6-dfm7-epoch5-clean-full'
            shards = []
            for shard in range(task['shards']):
                job = template.with_updates(job_id=prefix+task['name']+f'-{shard}', name=task['name'],
                    deps=(export.job_id,), metadata=meta, shard=shard, shards=task['shards'],
                    status=JobStatus.PENDING, attempt=0)
                job = job.with_updates(log_dir=str(canonical_log_dir(job)))
                additions.append(job); shards.append(job.job_id)
            merge = merge_template.with_updates(job_id=prefix+task['name']+'-merge', name=task['name'],
                deps=tuple(shards), metadata={**meta, 'shards':task['shards']},
                status=JobStatus.PENDING, attempt=0)
            additions.append(merge.with_updates(log_dir=str(canonical_log_dir(merge))))
            ids.extend(shards); merges.append(merge.job_id)
        template = next(j for j in block if j.action == Action.AVERAGE and j.metadata.get('multilingual_manifest'))
        meta = {**copy.deepcopy(template.metadata), FLAG: True,
                'python_bin': '/home/ucloud/miniforge3/envs/hrm/bin/python',
                'multilingual_manifest': str(POPULATION), 'population_require_complete': False,
                'dfm_log_root': str(root)}
        for suite, key in [('dfm','dfm_log_root'),('standard','log_root'),('euroeval','euroeval_log_root')]:
            roots = set()
            for job in block:
                if key in job.metadata:
                    path = str(job.metadata[key])
                    roots.add(path+'/'+tag if suite == 'euroeval' else path)
                roots.update(job.metadata.get('additional_'+suite+'_roots', []))
            roots.discard(str(root))
            meta['additional_'+suite+'_roots'] = sorted(roots)
        avg = template.with_updates(job_id=prefix+'average', name='50-language-populations',
            deps=tuple(merges+[j.job_id for j in block if j.action == Action.AVERAGE]),
            metadata=meta, status=JobStatus.PENDING, attempt=0,
            log_dir=str(PLAN/'dfm14-averages'/tag))
        additions.append(avg); gates[step] = avg.job_id; gpu_jobs[step] = ids
    updated = []
    for job in jobs:
        extra = []
        step = boundary(job)
        if job.action == Action.TERMINAL_BARRIER and step in gpu_jobs and job.status == JobStatus.PENDING:
            extra.extend(gpu_jobs[step])
        if job.action == Action.TRAIN_UNTIL_STEP and step > 3250000:
            extra.append(gates[max(s for s in gates if s < step)])
        if extra:
            assert job.status == JobStatus.PENDING and not job.attempt
            job = job.with_updates(deps=tuple(dict.fromkeys((*job.deps,*extra))))
        updated.append(job)
    result = updated+additions
    check_graph(result)
    return result


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    from scripts.headline_population_registry import load_registry
    load_registry(POPULATION)
    proof = load(OUT/'preflight.json')
    assert proof['passed'] and proof['tasks'] == 32
    for path, sha in proof['files'].items():
        assert file_hash(path) == sha, path
    CONTROL.mkdir(parents=True, exist_ok=True)
    with PlanLock(PLAN):
        before = read_plan(PLAN/'plan.tsv')
        after = build(before, load(REGISTRY))
        running = [j for j in before if j.status == JobStatus.RUNNING]
        assert all(j in after for j in running)
        report = dict(new_jobs=len(after)-len(before), running_unchanged=[j.job_id for j in running],
            languages=50, new_languages=16, tasks_per_checkpoint=32,
            checkpoints=sorted({boundary(j) for j in after if j.metadata.get(FLAG)}),
            pins=proof['files'], installed=args.install)
        if args.install:
            backup = CONTROL/'plan-before.tsv'
            if backup.exists():
                raise ValueError('Prior install receipt exists')
            write_plan(backup,before)
            write_plan(PLAN/'plan.tsv',after)
        else:
            write_plan(CONTROL/'preview.tsv',after)
        write_json(CONTROL/('installed.json' if args.install else 'preview.json'),report)
        print(report)


if __name__ == '__main__':
    main()
