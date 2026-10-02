"""Add multilingual evaluations to the paused XL plan; never launch GPU work."""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
import sys
import shlex
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
from dfm12.io import file_hash, load, write_json
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import Action, Job, JobStatus, read_plan, write_plan
from scripts.schedule_dfm12_xl_epoch11 import PLAN, SOURCE, RUN, PYTHON, SOURCE_PLAN, TEMPLATE_PREFIX
from scripts.schedule_identity_final_ema_full import canonical_log_dir


def build_registry(output):
    dfm=load(ROOT/'config/dfm_dala_heldout_registry_20260930.json')
    receipt=load(ROOT/'config/dfm_dala_heldout_preflight_20260930.json')
    if receipt['status']!='passed' or len(dfm)!=40:
        raise ValueError('All forty heldout tasks must pass CPU preflight')
    for path,sha in receipt['pins'].items():
        if file_hash(path)!=sha:
            raise ValueError('Heldout preflight input drift: '+path)
    euro=yaml.safe_load((ROOT/'config/euroeval_dfm12_multilingual.yaml').read_text())
    entries={}
    for entry in euro['entries']:
        status=entry.get('catalog_status',entry['status'])
        if status=='coverage_gap':
            continue
        name=entry['dataset']
        if not name or not entry['installed_18_1_supported']:
            raise ValueError('Unsupported EuroEval task: '+str(name))
        task={**entry,'languages':entry['euroeval_result_languages']}
        if name in entries:
            if entries[name]['metric_key']!=task['metric_key']:
                raise ValueError('Ambiguous shared EuroEval task: '+name)
        else:
            entries[name]=task
    binary=shlex.join([euro['execution']['python'],str(ROOT/'scripts/euroeval_api_no_flash_attn_guard.py')])
    result=dict(dfm=dfm,euroeval=list(entries.values()),euroeval_bin=binary,
                headline_manifest=str(ROOT/'config/multilingual_headline_populations_20260930.json'))
    write_json(output,result)
    return result


def extended_jobs(jobs, registry, plan=PLAN):
    if any(j.metadata.get('multilingual_extension') for j in jobs):
        raise ValueError('Multilingual extension already installed')
    first = [j for j in jobs if j.metadata.get('ckpt_tag') == 'step_2900000']
    export_template = next(j for j in first if j.action == Action.EXPORT_HF)
    wait_template = next(j for j in first if j.action == Action.WAIT_CHECKPOINT)
    dfm_template = next(j for j in first if j.action == Action.EVAL_DFM and j.name == 'dala')
    merge_template = next(j for j in first if j.action == Action.MERGE_DFM and j.name == 'dala')
    euro_template = next(j for j in first if j.action == Action.EVAL_EUROEVAL)
    average_template = next(j for j in first if j.action == Action.AVERAGE)
    barrier_template = next(j for j in first if j.action == Action.TERMINAL_BARRIER)
    teardown_template = next(j for j in first if j.action == Action.TEARDOWN_EVAL)
    tags = list(dict.fromkeys(j.metadata['ckpt_tag'] for j in jobs if j.action == Action.EXPORT_HF))
    result = [j.with_updates(metadata={**j.metadata,'eval_step':j.metadata['xl_boundary']})
              if 'xl_boundary' in j.metadata else j for j in jobs]
    for tag in ['epoch_10', *tags]:
        baseline = tag == 'epoch_10'
        prefix = f'dfm12-multilingual-{tag}-'
        existing = [j for j in result if j.metadata.get('ckpt_tag') == tag]
        export = export_template if baseline else next(j for j in existing if j.action == Action.EXPORT_HF)
        meta = copy.deepcopy(export.metadata)
        meta.update(multilingual_extension=True, python_bin=PYTHON,
                    multilingual_manifest=registry['headline_manifest'])
        if baseline:
            meta.update(ckpt_path=str(SOURCE), ckpt_tag=tag, checkpoint_tag=tag,
                        eval_epoch=10.0, eval_step=2877261, xl_boundary=2877261,
                        model_prefix='hrm-dfm11-XL-epoch10',
                        hf_export_dir=str(ROOT/'exports/dfm11_XL_epoch10_multilingual_ema_hf'),
                        hrm_hf_export_dir=str(ROOT/'exports/dfm11_XL_epoch10_multilingual_ema_hf'),
                        standard_hf_export_dir=str(ROOT/'exports/dfm11_XL_epoch10_multilingual_ema_hf'))
            wait = wait_template.with_updates(job_id=prefix+'wait',name=tag,deps=(),
                status=JobStatus.PENDING,attempt=0,metadata=meta,log_dir=str(plan/'multilingual'/tag/'wait'))
            export = export_template.with_updates(job_id=prefix+'export',name=tag,deps=(wait.job_id,),
                status=JobStatus.PENDING,attempt=0,
                metadata={**meta,'python_bin':export_template.metadata['python_bin']},
                log_dir=str(plan/'multilingual'/tag/'export'))
            result = [wait,export,*result]
        meta.update(dfm_log_root=str(ROOT/'logs/dfm_evals/dfm12_multilingual'/tag),
                    euroeval_log_root=str(ROOT/'logs/euroeval/dfm12_multilingual'/tag))
        # All newly added tasks are unjudged, and inherit the full-free-GPU policy.
        for key in list(meta):
            if key.startswith('judge_') or key.startswith('managed_judge'):
                meta.pop(key)
        gpu_ids, writer_ids, additions = [], [], []
        for task in registry['dfm']:
            task_meta = {**meta,'dfm_suite':task['suite'],
                         'dfm_single_tasks_config':task['config'],
                         'language':task['language'],'dfm_max_gen_toks':task.get('max_tokens',512)}
            shards = int(task.get('shards',4))
            shard_ids = []
            for shard in range(shards):
                job = dfm_template.with_updates(job_id=prefix+task['name']+f'-{shard}',
                    name=task['name'],shard=shard,shards=shards,deps=(export.job_id,),
                    status=JobStatus.PENDING,attempt=0,initial_batch=32,max_retries=5,
                    metadata=task_meta)
                job = job.with_updates(log_dir=str(canonical_log_dir(job)))
                additions.append(job)
                shard_ids.append(job.job_id)
            merge = merge_template.with_updates(job_id=prefix+task['name']+'-merge',
                name=task['name'],shard=None,shards=None,deps=tuple(shard_ids),
                status=JobStatus.PENDING,attempt=0,metadata={**task_meta,'shards':shards})
            merge = merge.with_updates(log_dir=str(canonical_log_dir(merge)))
            additions.append(merge)
            gpu_ids.extend(shard_ids)
            writer_ids.append(merge.job_id)
        for task in registry['euroeval']:
            exclusions = load(ROOT/'config/euroeval_optional_exclusions.json')
            if task['dataset'] in exclusions:
                continue
            job = euro_template.with_updates(job_id=prefix+'euro-'+task['dataset'],
                name=task['dataset'],shard=None,shards=None,deps=(export.job_id,),
                status=JobStatus.PENDING,attempt=0,initial_batch=32,max_retries=5,
                metadata={**meta,'euroeval_languages':task.get('languages',[task['language']]),
                          'euroeval_context_policy':'native_head_tail_v1',
                          'euroeval_category':task.get('category','')})
            if registry.get('euroeval_bin'):
                job=job.with_updates(metadata={**job.metadata,'euroeval_bin':registry['euroeval_bin']})
            job = job.with_updates(log_dir=str(canonical_log_dir(job)))
            additions.append(job)
            gpu_ids.append(job.job_id)
            if task.get('include_in_average',True):
                writer_ids.append(job.job_id)
        legacy_meta = next(j.metadata for j in read_plan(SOURCE_PLAN/'plan.tsv')
                           if j.job_id.startswith(TEMPLATE_PREFIX) and j.action==Action.EXPORT_HF) if baseline else export.metadata
        average_meta = {**meta,
                        'additional_standard_roots':[legacy_meta['log_root']],
                        'additional_dfm_roots':[legacy_meta['dfm_log_root']],
                        'additional_euroeval_roots':[f"{legacy_meta['euroeval_log_root']}/{legacy_meta['ckpt_tag']}"]}
        if baseline:
            average_meta['additional_euroeval_roots'] = [str(
                ROOT/'data/eval/dfm11-xl-epoch10-english-euroeval-20260930')]
        if not baseline:
            writer_ids.extend(j.job_id for j in existing if j.action==Action.AVERAGE)
        average = average_template.with_updates(job_id=prefix+'average',name='multilingual_headline',
            deps=tuple(writer_ids),status=JobStatus.PENDING,attempt=0,
            metadata=average_meta,log_dir=str(plan/'multilingual'/tag/'average'))
        additions.append(average)
        if baseline:
            barrier = barrier_template.with_updates(job_id=prefix+'barrier',deps=tuple(gpu_ids),
                status=JobStatus.PENDING,attempt=0,metadata=meta,log_dir=str(plan/'multilingual'/tag/'barrier'))
            teardown = teardown_template.with_updates(job_id=prefix+'teardown',deps=(barrier.job_id,),
                status=JobStatus.PENDING,attempt=0,metadata=meta,log_dir=str(plan/'multilingual'/tag/'teardown'))
            additions.extend([barrier,teardown])
            result = [j.with_updates(deps=(*j.deps,teardown.job_id))
                      if j.metadata.get('ckpt_tag')=='step_2900000' and j.action==Action.WAIT_CHECKPOINT
                      else j for j in result]
        else:
            updated = []
            for job in result:
                if job.metadata.get('ckpt_tag') == tag and job.action in (
                        Action.TERMINAL_BARRIER, Action.TEARDOWN_EVAL):
                    if job.status == JobStatus.RUNNING:
                        raise ValueError('Cannot extend an actively releasing checkpoint')
                    job = job.with_updates(status=JobStatus.PENDING, attempt=0)
                    if job.action == Action.TERMINAL_BARRIER:
                        job = job.with_updates(deps=(*job.deps, *gpu_ids))
                updated.append(job)
            result = updated
        def order(job):
            if job.action==Action.EVAL_EUROEVAL:
                return {'instruction-following':0,'summarization':1}.get(job.metadata.get('euroeval_category'),2)
            return 3 if job.action==Action.EVAL_DFM else 4
        result.extend(sorted(additions,key=order))
    ids = {j.job_id for j in result}
    if len(ids)!=len(result) or any(not set(j.deps)<=ids for j in result):
        raise ValueError('Invalid expanded plan dependencies')
    return result


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--registry',type=Path,default=ROOT/'config/dfm12_multilingual_eval_campaign.json')
    parser.add_argument('--build-registry',action='store_true')
    parser.add_argument('--plan-dir',type=Path,default=PLAN)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    registry=build_registry(args.registry) if args.build_registry else load(args.registry)
    with PlanLock(args.plan_dir):
        jobs=read_plan(args.plan_dir/'plan.tsv')
        if args.apply and not (args.plan_dir/'stop.request').exists():
            raise ValueError('Pause scheduler dispatch before modifying plan')
        result=extended_jobs(jobs,registry,args.plan_dir)
        dest=args.plan_dir/('plan.tsv' if args.apply else 'plan.multilingual-preview.tsv')
        if args.apply:
            backup=args.plan_dir/'plan.before-multilingual.tsv'
            if backup.exists():
                raise ValueError('Backup already exists; inspect prior application')
            write_plan(backup,jobs)
        write_plan(dest,result)
        write_json(args.plan_dir/'multilingual-extension.json',dict(
            applied=args.apply,registry=str(args.registry.resolve()),registry_sha256=file_hash(args.registry),
            old_rows=len(jobs),new_rows=len(result),plan_sha256=file_hash(dest)))
    print(dest, len(result))


if __name__=='__main__':
    main()
