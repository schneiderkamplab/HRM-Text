"""Publish the reconciled corpora and resume XXL-wide in the existing campaign."""
import argparse
import copy
import math
import os
import re
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

import numpy as np

from dfm12.io import load, write_json, file_hash, lock
from dfm12.prepare_xl_epoch11 import count_steps
from dfm14.reconcile_inheritance import ROOT, validate, verify_imported_sources
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'eval_scheduler'))
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import Action, JobStatus, read_plan, write_plan
from scripts.stop_training_at_complete_checkpoint import complete, preserve
from scripts.schedule_dfm13_wave34_baseline import check_graph
from scripts.schedule_identity_final_ema_full import canonical_log_dir

PLAN = Path('logs/scheduler/dfm10_XL_epoch9_20260831')
OLD = Path('checkpoints/dfm13/XXL-wide-from-dfm11-epoch2')
CKPT = Path('checkpoints/dfm14/XXL-wide-from-dfm13-step870000')
CONTROL = ROOT/'training'
DATA = Path('data/sampled_dfm14')
PREFIX = 'xxlw-dfm14-'
TEMPLATE = 'xxlw-dfm13-900000-'
PY = '/home/ucloud/miniforge3/envs/hrm/bin/python'


def publish():
    result = load(ROOT/'rebuilt.json')
    if result['status'] != 'validated_not_promoted':
        raise ValueError('Unvalidated rebuild')
    verify_imported_sources()
    if subprocess.run(['pgrep','-f','^.*python.*-u pretrain.py'],stdout=subprocess.DEVNULL).returncode == 0:
        raise RuntimeError('Training must be stopped for publication')
    # The old build may still publish accepted additions. Do not race its registry.
    while subprocess.run(['pgrep','-f','^.*python.*-m dfm14.build'],
                         stdout=subprocess.DEVNULL).returncode == 0:
        print('Waiting for accepted-package publication to finish', flush=True)
        time.sleep(30)
    publication = load('exports_dfm14/upload-receipts.json')
    entries = result['source_inventory']
    for entry in entries:
        if entry['hf_repo_id'] in publication:
            entry['hf_revision'] = publication[entry['hf_repo_id']]['revision']
        if not entry.get('hf_revision'):
            raise ValueError('Unpublished addition: '+entry['name'])
    CONTROL.mkdir(parents=True, exist_ok=True)
    epoch_pin = CONTROL/'original-resume.json'
    if not epoch_pin.exists():
        saved = load(OLD/'checkpoint_state_step_870000.json')
        if not complete(OLD,'step_870000') or saved['step'] != 870000 or saved['carry_policy']!='none':
            raise ValueError('Unexpected or incomplete source checkpoint')
        n = len(np.load('data/sampled_dfm13/epoch_2/inst_len.npy', mmap_mode='r'))
        write_json(epoch_pin, dict(state=saved, source_sha256=file_hash(OLD/'checkpoint_state_step_870000.json'),
            historical_epoch=2+saved['global_row_cursor_in_epoch']/n))
    for name, value in result['datasets'].items():
        source = Path(value).resolve()
        target = Path('data')/('sampled_'+name)
        receipt = load(source/'validated.json')
        if receipt['metadata_sha256'] != file_hash(source/'metadata.json'):
            raise ValueError('Validated dataset changed')
        if target.is_symlink() and target.resolve()==source:
            continue
        backup = ROOT/('previous_sampled_'+name)
        if target.exists() or target.is_symlink():
            if backup.exists():
                raise ValueError('Unexpected existing backup: '+str(backup))
            target.rename(backup)
        temporary = target.with_suffix('.reconciled-link')
        temporary.symlink_to(source, target_is_directory=True)
        temporary.replace(target)
    inventory=load(ROOT/'component-inventory.json')
    for group, sources in (
        ('dfm12',load(ROOT/'remote/full_reference.json')['sources']),
        ('dfm13',load(ROOT/'dfm13-approved-sources.json')),
    ):
        components=[]
        for source in sources:
            parts=[p for p in inventory if p['prefix']==source['name']+'__']
            if not parts:raise ValueError('Missing source accounting: '+source['name'])
            repeats={p['repeat'] for p in parts}
            if len(repeats)!=1:raise ValueError('Inconsistent source repeat')
            components.append(dict(name=source['name'],hf_repo_id=source.get('hf_repo_id'),
                hf_revision=source.get('hf_revision'),repeat=repeats.pop(),
                rows=sum(p['rows'] for p in parts),tokens=sum(p['tokens'] for p in parts),
                tokenized_parts=[str(ROOT/'tokenized_remote'/p['part']) for p in parts]))
        write_json(Path(result['datasets'][group])/'source-registry.json',dict(
            inherits='dfm11' if group=='dfm12' else 'dfm12', additions=components,
            authoritative_snapshot=str(ROOT/'snapshot.json'),identity_repeat=0))
    write_json('config/dfm14_sources.json', dict(inherits='dfm13',base='data/sampled_dfm13',
        additions=entries, sampled=str(DATA), inheritance_receipt=str(ROOT/'inherited-ready.json'),
        selection_receipt=str(ROOT/'dfm14/selection.json'),
        inherited_overlap_policy='keep_all',
        total_tokens_per_epoch=result['total_tokens_per_epoch'], epochs=3))
    write_json(ROOT/'published.json', dict(datasets=result['datasets'], identity_repeat=0,
        metadata={k:file_hash(Path(v)/'metadata.json') for k,v in result['datasets'].items()},
        snapshot_sha256=file_hash(ROOT/'snapshot.json')))
    # Supersede the old release's readiness claim; preserve its other receipts.
    write_json('data/dfm14/release-v1/completion.json', dict(status='ready',
        inheritance_reconciled=True, authoritative_receipt=str(ROOT/'published.json'),
        total_tokens_per_epoch=result['total_tokens_per_epoch'],
        metadata_sha256=file_hash(DATA/'metadata.json')))


def prepare_resume():
    resume = CONTROL/'resume'
    tag = 'step_870000'
    if not resume.exists():
        preserve(OLD, resume, tag)
    state = copy.deepcopy(load(CONTROL/'original-resume.json')['state'])
    state.update(epoch=3, batch_in_epoch=0, batch_in_epoch_exact=True,
        global_row_cursor_in_epoch=0, global_row_start_in_epoch=0, data_path=str(DATA))
    write_json(resume/f'checkpoint_state_{tag}.json',state)
    if not complete(resume, tag):
        raise ValueError('Incomplete private resume copy')
    budget = CONTROL/'packed-steps.json'
    if not budget.exists():
        write_json(budget, count_steps(DATA/'epoch_2',batch_tokens=8192,world_size=8,gas=4))
    packed = load(budget)
    result = dict(start_step=870000, end_step=870000+packed['optimizer_steps'],
        resume=str(resume.resolve()), checkpoint_path=str(CKPT), data=str(DATA),
        epoch_rows=len(np.load(DATA/'epoch_2/inst_len.npy',mmap_mode='r')),
        historical_epoch=load(CONTROL/'original-resume.json')['historical_epoch'],
        metadata_sha256=file_hash(DATA/'metadata.json'), packing=packed)
    write_json(CONTROL/'run.json', result)
    return result


def build_plan(jobs, run):
    template = [j for j in jobs if j.job_id.startswith(TEMPLATE)]
    if len(template)!=290:
        raise ValueError('Unexpected evaluation template')
    train = next(j for j in jobs if j.job_id=='xxlw-dfm13-train-900000')
    argv = shlex.split(train.metadata['command'])
    argv = argv[:2]+[PY,'-m','dfm14.continue_training','segment','--']+argv[argv.index('--')+1:]
    changes = dict(data='dfm14',epochs=3,checkpoint_path=str(CKPT),training_total_steps=run['end_step'])
    argv = [a for a in argv if a.lstrip('+').split('=',1)[0] not in changes]
    argv += [f'{k}={v}' for k,v in changes.items()]
    required = ['lr=3e-4','lr_auto=true','gradient_accumulation_steps=4',
                'global_batch_size=262144','arch.bp_max_steps=8','wandb_run_id=dfm10-xxl-wide']
    if not all(s in argv for s in required):
        raise ValueError('Training settings drifted')
    old_ids = {j.job_id for j in jobs if (j.job_id.startswith('xxlw-dfm13-') and
        j.status==JobStatus.PENDING) or j.job_id=='xxlw-dfm14-ready-at-900000'}
    retained = [j for j in jobs if j.job_id not in old_ids]
    if any(set(j.deps)&old_ids for j in retained):
        raise ValueError('External dependencies on replaced campaign')
    registry = load('data/dfm14/evaluation/registry.json')
    preflight=load('data/dfm14/evaluation/preflight.json')
    if not preflight.get('valid') or len(preflight['tasks'])!=32:
        raise ValueError('New task preflight incomplete')
    for path,digest in registry['pins'].items():
        if file_hash(path)!=digest:
            raise ValueError('Eval input changed: '+path)
    additions=[]
    previous=None
    resume='step_870000'
    targets=list(range(900000,run['end_step']+1,50000))
    if not targets or targets[-1]!=run['end_step']:
        targets.append(run['end_step'])
    for target in targets:
        final=target==run['end_step']
        tag='epoch_3' if final else f'step_{target}'
        train_id=PREFIX+f'train-{target}'
        metadata=dict(train.metadata,command=shlex.join(argv),ckpt_path=str(CKPT),ckpt_tag=tag,
            stop_after_step=target+10 if final else target, completion_checkpoint_tag='epoch_3',
            resume_from_tag=resume,resume_ckpt_path=run['resume'] if previous is None else str(CKPT),
            dfm14_boundary=target)
        metadata.pop('dfm13_boundary',None)
        additions.append(train.with_updates(job_id=train_id,name=tag,metadata=metadata,
            deps=(previous,) if previous else (),status=JobStatus.PENDING,attempt=0,
            log_dir=f'logs/training/dfm14_XXL_wide/to_{target}'))
        ids={j.job_id:PREFIX+str(target)+'-'+j.job_id[len(TEMPLATE):] for j in template}
        def replace(value):
            if isinstance(value,str):
                return value.replace('dfm13_XXL_wide','dfm14_XXL_wide').replace('step_900000',tag)
            if isinstance(value,dict):return {k:replace(v) for k,v in value.items()}
            if isinstance(value,list):return [replace(v) for v in value]
            return value
        block=[]
        for original in template:
            meta=replace(copy.deepcopy(original.metadata))
            meta.pop('dfm13_boundary',None)
            meta.update(ckpt_path=str(CKPT),ckpt_tag=tag,dfm14_boundary=target,
                eval_epoch=run['historical_epoch']+(target-run['start_step'])/(run['end_step']-run['start_step']))
            deps=(train_id,) if original.action==Action.WAIT_CHECKPOINT else tuple(ids[d] for d in original.deps)
            block.append(original.with_updates(job_id=ids[original.job_id],metadata=meta,deps=deps,
                name=replace(original.name),log_dir=replace(original.log_dir),status=JobStatus.PENDING,attempt=0))
        export=next(j for j in block if j.action==Action.EXPORT_HF)
        new_gpu=[];new_merge=[]
        for task in registry['tasks']:
            family='gec_dala' if task['name'].startswith('gec_') else 'dala'
            seed=next(j for j in block if j.action==Action.EVAL_DFM and j.name==family)
            merge=next(j for j in block if j.action==Action.MERGE_DFM and j.name==family)
            meta={k:v for k,v in seed.metadata.items() if not k.startswith(('judge_','managed_judge'))}
            meta.update(dfm_suite=task['name'],dfm_single_tasks_config=task['config'],
                        dfm_max_gen_toks=task['max_tokens'],language=task['language'],
                        fixed_retry_batch=False)
            shard_ids=[]
            for shard in range(task['shards']):
                job=seed.with_updates(job_id=PREFIX+f'{target}-{task["name"]}-{shard}',name=task['name'],
                    shard=shard,shards=task['shards'],
                    initial_batch=min(task['batch_size'],seed.initial_batch or task['batch_size']),metadata=meta,
                    deps=(export.job_id,))
                job=job.with_updates(log_dir=str(canonical_log_dir(job)))
                block.append(job);shard_ids.append(job.job_id);new_gpu.append(job.job_id)
            job=merge.with_updates(job_id=PREFIX+f'{target}-{task["name"]}-merge',name=task['name'],
                metadata={**meta,'shards':task['shards']},deps=tuple(shard_ids))
            job=job.with_updates(log_dir=str(canonical_log_dir(job)))
            block.append(job);new_merge.append(job.job_id)
        for i,job in enumerate(block):
            if job.action==Action.TERMINAL_BARRIER:
                block[i]=job.with_updates(deps=tuple((*job.deps,*new_gpu)))
        average=next(j for j in block if j.action==Action.AVERAGE)
        # The multilingual logger is a distinct action; retain legacy suite/headline averages.
        block.append(average.with_updates(job_id=PREFIX+f'{target}-multilingual-average',
            name='dfm14-multilingual',deps=tuple([average.job_id,*new_merge]),
            log_dir=f'logs/dfm_evals/dfm14_XXL_wide/{tag}/multilingual-average',
            metadata={**average.metadata,'multilingual_manifest':registry['multilingual_manifest']}))
        additions.extend(block)
        previous=next(j.job_id for j in block if j.action==Action.TEARDOWN_EVAL)
        resume=tag
    result=retained+additions
    check_graph(result)
    return result


def install(run):
    with PlanLock(PLAN):
        jobs=read_plan(PLAN/'plan.tsv')
        if any(j.status==JobStatus.RUNNING for j in jobs):
            raise ValueError('Scheduler still has running jobs')
        if (CONTROL/'installed.json').exists():
            return
        revised=build_plan(jobs,run)
        write_plan(CONTROL/'plan-before-dfm14.tsv',jobs)
        write_plan(PLAN/'plan.tsv',revised)
        write_json(CONTROL/'installed.json',dict(plan_sha256=file_hash(PLAN/'plan.tsv'),run=run))


def training_gpus_free():
    """Fail closed unless all eight GPUs have headroom and no compute clients."""
    try:
        devices=subprocess.run(['nvidia-smi','--query-gpu=index,uuid,memory.free',
            '--format=csv,noheader,nounits'],check=True,capture_output=True,text=True,timeout=15)
        selected={}
        for line in devices.stdout.splitlines():
            index,uuid,free=(part.strip() for part in line.split(','))
            if int(index) in range(8):selected[uuid]=int(free)
        clients=subprocess.run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid',
            '--format=csv,noheader,nounits'],check=True,capture_output=True,text=True,timeout=15)
        if len(selected)!=8 or any(free<178000 for free in selected.values()):
            return False
        return not any(line.split(',')[0].strip() in selected for line in clients.stdout.splitlines())
    except (subprocess.SubprocessError,ValueError):
        return False


def segment(command):
    if command and command[0]=='--':command=command[1:]
    # The scheduler reserves its own eight slots; this also checks unrelated jobs.
    while not training_gpus_free():
        if (PLAN/'stop.request').exists() or (CONTROL/'cancel').exists():
            raise RuntimeError('Training cancelled while waiting for free GPUs')
        print(time.strftime('%FT%T'),'Waiting for GPUs 0-7: no compute clients and >=178000 MiB free each',flush=True)
        time.sleep(120)
    subprocess.run(command,check=True)
    target=int(next(x.split('=',1)[1] for x in command if x.startswith('stop_after_step=')))
    run=load(CONTROL/'run.json')
    final=complete(CKPT,'epoch_3')
    tag='epoch_3' if final else f'step_{target}'
    if not complete(CKPT,tag):
        raise RuntimeError('Missing complete boundary checkpoint')
    state=load(CKPT/f'checkpoint_state_{tag}.json')
    fraction=1 if final else state['global_row_cursor_in_epoch']/run['epoch_rows']
    boundary=run['end_step'] if final else target
    with PlanLock(PLAN):
        jobs=read_plan(PLAN/'plan.tsv')
        jobs=[j.with_updates(metadata={**j.metadata,'eval_epoch':run['historical_epoch']+fraction,
                                       'eval_step':state['step']})
              if j.job_id.startswith(PREFIX) and j.metadata.get('dfm14_boundary')==boundary
              and j.status==JobStatus.PENDING else j for j in jobs]
        write_plan(PLAN/'plan.tsv',jobs)


def watch():
    CONTROL.mkdir(parents=True,exist_ok=True)
    with lock(CONTROL/'.lock'):
        while not (ROOT/'rebuilt.json').exists():
            if (CONTROL/'cancel').exists():raise RuntimeError('Continuation cancelled')
            if subprocess.run(['pgrep','-f','^.*python.*-m dfm14.reconcile_inheritance'],
                              stdout=subprocess.DEVNULL).returncode != 0:
                raise RuntimeError('Rebuild exited without validation; training remains stopped')
            print(time.strftime('%FT%T'),'Waiting for validated DFM12/13/14 rebuild',flush=True)
            time.sleep(30)
        publish()
        run=prepare_resume()
        install(run)
        if (CONTROL/'cancel').exists():raise RuntimeError('Continuation cancelled')
        subprocess.run([PY,'-m','eval_scheduler','clear-stop','--plan-dir',str(PLAN)],check=True)
        env=dict(os.environ,PATH=str(Path(PY).parent)+':'+os.environ['PATH'])
        with (PLAN/'runner.log').open('a') as log:
            process=subprocess.Popen([PY,'-u','-m','eval_scheduler','run','--plan-dir',str(PLAN),
                '--gpus','0,1,2,3,4,5,6,7','--persistent-vllm'],env=env,
                stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        write_json(CONTROL/'launched.json',dict(pid=process.pid,run=run))
        print('Scheduler resumed:',process.pid,flush=True)
        log_path=Path('logs/training/dfm14_XXL_wide/to_900000/train_until_step_900000.log')
        deadline=time.monotonic()+3600
        while time.monotonic()<deadline:
            if process.poll() is not None:
                raise RuntimeError('Scheduler exited before resumed progress was verified')
            with PlanLock(PLAN):
                jobs=read_plan(PLAN/'plan.tsv')
            training=next(j for j in jobs if j.job_id==PREFIX+'train-900000')
            if training.status==JobStatus.FAILED:
                raise RuntimeError('Resumed training failed; inspect '+str(log_path))
            if log_path.exists():
                with log_path.open('rb') as handle:
                    handle.seek(max(0,log_path.stat().st_size-262144))
                    tail=handle.read().decode(errors='replace')
                steps=[int(x) for x in re.findall(r'(\d+)/'+str(run['end_step']),tail)]
                if steps and max(steps)>=run['start_step']+25:
                    write_json(CONTROL/'progress-verified.json',dict(step=max(steps),
                        log=str(log_path.resolve()),scheduler_pid=process.pid))
                    print('Resumed training progressing:',max(steps),flush=True)
                    return
            print(time.strftime('%FT%T'),'Waiting for resumed training progress',flush=True)
            time.sleep(30)
        raise RuntimeError('Timed out verifying resumed training; inspect scheduler and training logs')


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('mode',choices=['watch','segment'])
    args,command=parser.parse_known_args()
    if args.mode=='segment':segment(command)
    else:watch()


if __name__=='__main__':main()
