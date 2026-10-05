"""Locked, readiness-gated original XL DFM12 -> DFM13 scheduler transition."""
import argparse
import copy
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
from dfm12.io import digest, file_hash, load, lock, write_json
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import Action, Job, JobStatus, read_plan, write_plan
from scripts import prepare_dfm13_xl_handoff as prep
from scripts import schedule_dfm12_xl_epoch11 as old
from scripts.stop_training_at_complete_checkpoint import complete, preserve

START = prep.START
CONTROL = prep.CONTROL
PLAN = old.PLAN
SOURCE = old.CHECKPOINT
OUTPUT = ROOT / 'checkpoints/dfm13/XL-from-dfm12-step3150000'
SCRIPT = Path(__file__).resolve()
PREFIX = 'dfm13-xl-'
GATE = 'dfm13-handoff-resume-ready'


def boundary(job):
    return int(job.metadata.get('xl_boundary', job.metadata.get('eval_step', 0)))


def retire_future(jobs):
    removed = [j for j in jobs if boundary(j) > START and not j.job_id.startswith(PREFIX)]
    if any(j.status not in (JobStatus.PENDING, JobStatus.SKIPPED) or j.attempt for j in removed):
        raise ValueError('Future DFM12 job already attempted; refuse live transition')
    kept = [j for j in jobs if j not in removed]
    ids = {j.job_id for j in kept}
    if any(not set(j.deps) <= ids for j in kept):
        raise ValueError('Retirement would leave dangling dependencies')
    if not any(boundary(j)==START and j.action==Action.TRAIN_UNTIL_STEP for j in kept):
        raise ValueError('Missing current3150 training boundary')
    return kept, removed


def arm(plan=PLAN, control=CONTROL):
    """Remove only unstarted obsolete future rows; current jobs remain identical."""
    control.mkdir(parents=True, exist_ok=True)
    with PlanLock(plan):
        path = plan/'plan.tsv'
        jobs = read_plan(path)
        kept, removed = retire_future(jobs)
        receipt = control/'scheduler-armed.json'
        if receipt.exists():
            if removed:
                raise ValueError('Retired DFM12 future rows reappeared')
            return load(receipt)
        backup = control/'plan-before-handoff.tsv'
        if backup.exists():
            raise ValueError('Uncommitted prior arm backup; inspect before recovery')
        shutil.copy2(path, backup)
        write_plan(path, kept)
        result = dict(backup=str(backup), backup_sha256=file_hash(backup),
                      removed_ids=[j.job_id for j in removed], preserved_jobs=len(kept),
                      preserved_3150_jobs=sum(boundary(j)==START for j in kept),
                      old_future_training_disabled=True, time=time.time())
        write_json(receipt, result)
        return result


def read_prepared(control=CONTROL):
    run=load(control/'prepared.json')
    end=run['end_step']
    if (run['start_step']!=START or type(end) is not int or end<=START+50000
            or run['dataset_epoch_index']!=0 or run['dataset_passes']!=1
            or run['gradient_accumulation_steps']!=2 or run['world_size']!=8
            or run['wandb_run_id']!=old.RUN or run['wandb_project']!='DFM5'
            or Path(run['dataset']).resolve()!=prep.SAMPLE.resolve()
            or run['packing']['optimizer_steps']!=end-START):
        raise ValueError('Unexpected DFM13 prepared budget/policy')
    expected=dict(lr=3e-4,lr_auto=True,rewarm_steps=0,decay_start_step=end-50000,
                  decay_end_step=end,final_lr=1e-5)
    if run['proposed_lr']!=expected:
        raise ValueError('Unexpected DFM13 LR policy')
    contract=prep.sample_contract(prep.COMPLETION,prep.SAMPLE)
    if contract!=run['sample_contract']:
        raise ValueError('Sample readiness/pins changed')
    prep.require_current_provenance(contract)
    return run


def readiness_gate(plan=PLAN,control=CONTROL):
    """Keep the existing scheduler alive waiting on the real isolated checkpoint."""
    with PlanLock(plan):
        jobs=read_plan(plan/'plan.tsv')
        if not (control/'scheduler-armed.json').exists():raise ValueError('Arm first')
        deps=tuple(j.job_id for j in jobs if boundary(j)==START and j.status!=JobStatus.SKIPPED)
        expected=Job(job_id=GATE,action=Action.WAIT_CHECKPOINT,family='handoff',name='DFM13 ready',
            deps=deps,max_retries=0,log_dir=str(control/'readiness'),metadata=dict(
                plan_dir=str(plan),ckpt_path=str(control/'resume'),ckpt_tag=f'step_{START}',
                checkpoint_carry_ranks=8,checkpoint_wait_seconds=30,checkpoint_wait_max_seconds=0))
        present=[j for j in jobs if j.job_id==GATE]
        if present:
            if present[0].metadata!=expected.metadata or present[0].deps!=expected.deps:
                raise ValueError('Existing readiness gate differs')
            return
        write_plan(plan/'plan.tsv',jobs+[expected])
        write_json(control/'scheduler-readiness-gate.json',dict(job_id=GATE,dependencies=list(deps),
                   checkpoint_path=str(control/'resume'),checkpoint_tag=f'step_{START}',time=time.time()))


def replace_tree(value, replacements):
    if isinstance(value,str):
        for before,after in replacements:
            value=value.replace(before,after)
        return value
    if isinstance(value,list):return [replace_tree(v,replacements) for v in value]
    if isinstance(value,dict):return {k:replace_tree(v,replacements) for k,v in value.items()}
    return value


def build(jobs, run, plan=PLAN, control=CONTROL):
    block=[j for j in jobs if boundary(j)==START]
    template=[j for j in block if j.action!=Action.TRAIN_UNTIL_STEP]
    for action in (Action.WAIT_CHECKPOINT,Action.EXPORT_HF,Action.TEARDOWN_EVAL):
        if sum(j.action==action for j in template)!=1:
            raise ValueError('Incomplete3150 evaluation lifecycle')
    if not any(j.action==Action.AVERAGE for j in template):
        raise ValueError('Missing3150 averages')
    previous=tuple(j.job_id for j in block if j.status!=JobStatus.SKIPPED)
    if any(j.job_id==GATE for j in jobs):previous=(*previous,GATE)
    result=[]
    resume=f'step_{START}'
    for target in [*range(START+50000,run['end_step'],50000),run['end_step']]:
        final=target==run['end_step']
        tag='epoch_1' if final else f'step_{target}'
        prefix=f'{PREFIX}{tag}-'
        train_id=prefix+'train'
        stop=target+1 if final else target
        result.append(Job(job_id=train_id,action=Action.TRAIN_UNTIL_STEP,family='training',name=tag,
            deps=previous,deps_mode='success',max_retries=0,gpu_policy='all',gpu_count=8,
            log_dir=str(ROOT/'logs/training/dfm13_XL'/tag),metadata=dict(
                command=shlex.join([old.PYTHON,str(SCRIPT),'segment','--plan-dir',str(plan),
                                   '--control',str(control)]),workdir=str(ROOT),
                ckpt_path=str(OUTPUT),ckpt_tag=f'step_{stop}',stop_after_step=stop,
                completion_checkpoint_tag='epoch_1',checkpoint_carry_ranks=8,
                resume_ckpt_path=str(SOURCE if resume==f'step_{START}' else OUTPUT),
                resume_from_tag=resume,min_gpu_free_mib=178000,xl_boundary=target,eval_step=target)))
        mapping={j.job_id:prefix+j.job_id for j in template}
        batch=[]
        for old_job in template:
            replacements=[(str(SOURCE),str(OUTPUT)),
                ('dfm12_XL_epoch11','dfm13_XL'),('dfm12_multilingual','dfm13_multilingual'),
                (f'step_{START}',tag)]
            meta=replace_tree(copy.deepcopy(old_job.metadata),replacements)
            meta.update(ckpt_path=str(OUTPUT),ckpt_tag=tag,checkpoint_tag=tag,
                xl_boundary=target,eval_step=target,plan_dir=str(plan),
                model_prefix='hrm-dfm13-XL',dfm13_cursor_epoch_pending=True)
            for key in ('hf_export_dir','hrm_hf_export_dir','standard_hf_export_dir'):
                if key in meta:meta[key]=str(ROOT/f'exports/dfm13_XL_{tag}_ema_hf')
            deps=(train_id,) if old_job.action==Action.WAIT_CHECKPOINT else tuple(mapping[d] for d in old_job.deps)
            job=old_job.with_updates(job_id=mapping[old_job.job_id],deps=deps,metadata=meta,attempt=0,
                status=JobStatus.SKIPPED if old_job.status==JobStatus.SKIPPED else JobStatus.PENDING,
                name=tag if old_job.action in (Action.WAIT_CHECKPOINT,Action.EXPORT_HF) else old_job.name,
                log_dir=replace_tree(old_job.log_dir,replacements))
            batch.append(job)
        result.extend(batch)
        previous=tuple(j.job_id for j in batch if j.status!=JobStatus.SKIPPED)
        resume=tag
    ids={j.job_id for j in jobs+result}
    if len(ids)!=len(jobs+result) or any(not set(j.deps)<=ids for j in result):
        raise ValueError('Invalid successor graph')
    return result


def install(plan=PLAN,control=CONTROL):
    run=read_prepared(control)
    with PlanLock(plan):
        jobs=read_plan(plan/'plan.tsv')
        if (not (control/'scheduler-armed.json').exists() or retire_future(jobs)[1]
                or not any(j.job_id==GATE for j in jobs)):
            raise ValueError('Old future must be retired first')
        if any(j.job_id.startswith(PREFIX) for j in jobs):
            receipt=load(control/'scheduler-installed.json')
            if receipt['prepared_sha256']!=file_hash(control/'prepared.json'):
                raise ValueError('Installed budget drift')
            return receipt
        successor=build(jobs,run,plan,control)
        pins={str(p):file_hash(p) for p in (SCRIPT,Path(prep.__file__),Path(old.__file__),
              ROOT/'scripts/resume_xl_dfm12_epoch11.sh',ROOT/'pretrain.py',ROOT/'config/data/dfm13.yaml')}
        receipt=dict(prepared_sha256=file_hash(control/'prepared.json'),pins=pins,
                     job_ids=[j.job_id for j in successor],start_step=START,end_step=run['end_step'],
                     first_training_dependencies=list(successor[0].deps),time=time.time())
        write_json(control/'scheduler-install-intent.json',receipt)
        write_plan(plan/'plan.tsv',jobs+successor)
        write_json(control/'scheduler-installed.json',receipt)
        return receipt


def reset_state(original,dataset):
    if (original.get('step')!=START or original.get('carry_policy')!='none'
            or original.get('world_size')!=8 or original.get('gradient_accumulation_steps')!=2):
        raise ValueError('Source3150 checkpoint step/carry/world/GAS mismatch')
    state=dict(original,epoch=1,batch_in_epoch=0,batch_in_epoch_exact=True,
        global_row_cursor_in_epoch=0,global_row_start_in_epoch=0,data_path=str(dataset))
    state.pop('lr_rewarm',None)
    return state


def fresh_resume(control=CONTROL):
    tag=f'step_{START}'
    target=control/'resume'
    original=load(SOURCE/f'checkpoint_state_{tag}.json')
    state=reset_state(original,prep.SAMPLE)
    if target.exists():
        proof=load(target/'handoff.json')
        if (proof['source_sidecar_sha256']!=file_hash(SOURCE/f'checkpoint_state_{tag}.json')
                or load(target/f'checkpoint_state_{tag}.json')!=state or not complete(target,tag)):
            raise ValueError('Existing resume view changed/incomplete')
        return target
    temporary=control/'resume.preparing'
    if temporary.exists():raise ValueError('Incomplete prior resume preparation; inspect before recovery')
    preserve(SOURCE,temporary,tag)
    write_json(temporary/f'checkpoint_state_{tag}.json',state)
    write_json(temporary/'handoff.json',dict(source=str(SOURCE),
        source_sidecar_sha256=file_hash(SOURCE/f'checkpoint_state_{tag}.json'),original_state=original,
        resume_state=state,dataset_epoch_index=0,global_step=START,optimizer_ema='unchanged hardlinks'))
    os.rename(temporary,target)
    return target


def training_arguments(run, overrides):
    # Retain the tested XL performance/optimizer settings, replacing only dataset/LR/cursor policy.
    args=old.training_arguments(dict(start_step=2877261,end_step=run['end_step']),[])
    changes={'data':'dfm13','data.path':str(prep.SAMPLE),'epochs':'1','lr_rewarm_steps':'0','arch.bp_warmup_ratio':'0',
             'lr_rewarm_start_step':'null','lr_decay_start_step':str(run['end_step']-50000),
             'checkpoint_path':str(OUTPUT)}
    allowed={'stop_after_step','resume_checkpoint_path','resume_checkpoint_tag'}
    if any('=' not in x or x.split('=',1)[0] not in allowed for x in overrides):
        raise ValueError('Unexpected training override')
    changes.update(dict(x.split('=',1) for x in overrides))
    present={x.split('=',1)[0] for x in args if '=' in x}
    return ([f'{x.split("=",1)[0]}={changes.get(x.split("=",1)[0],x.split("=",1)[1])}'
             if '=' in x else x for x in args]
            + [f'{k}={v}' for k,v in changes.items() if k not in present])


def display_epoch(parent_state,parent_rows,state,rows,final=False):
    base=10+parent_state['global_row_cursor_in_epoch']/parent_rows
    return base+(1 if final else state['global_row_cursor_in_epoch']/rows)


def segment(plan,control,overrides):
    receipt=load(control/'scheduler-installed.json')
    if receipt['prepared_sha256']!=file_hash(control/'prepared.json') or any(file_hash(p)!=sha for p,sha in receipt['pins'].items()):
        raise ValueError('Handoff implementation/budget pins changed')
    run=read_prepared(control)
    values=dict(x.split('=',1) for x in overrides)
    target=int(values['stop_after_step'])
    with PlanLock(plan):
        jobs=read_plan(plan/'plan.tsv')
        current=next(j for j in jobs if j.job_id.startswith(PREFIX) and j.action==Action.TRAIN_UNTIL_STEP
                     and j.metadata['stop_after_step']==target)
        by_id={j.job_id:j for j in jobs}
        if any(by_id[d].status!=JobStatus.DONE for d in current.deps):
            raise ValueError('Preceding evaluation/averages not complete')
    if values['resume_checkpoint_tag']==f'step_{START}':
        if Path(values['resume_checkpoint_path']).resolve()!=SOURCE.resolve():raise ValueError('Wrong parent')
        values['resume_checkpoint_path']=str(fresh_resume(control))
    elif Path(values['resume_checkpoint_path']).resolve()!=OUTPUT.resolve():raise ValueError('Wrong continuation')
    command=training_arguments(run,[f'{k}={v}' for k,v in values.items()])
    old.gpu_gate(subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.free','--format=csv,noheader,nounits'],text=True))
    subprocess.run(command,cwd=ROOT,check=True)
    tag='epoch_1' if target>run['end_step'] else f'step_{target}'
    if not complete(OUTPUT,tag):raise ValueError('Segment checkpoint incomplete')
    import numpy as np
    parent_state=load(SOURCE/f'checkpoint_state_step_{START}.json')
    parent_rows=len(np.load(old.DATA/'epoch_10/inst_start.npy',mmap_mode='r'))
    state=load(OUTPUT/f'checkpoint_state_{tag}.json')
    epoch=display_epoch(parent_state,parent_rows,state,run['packing']['packed_rows'],tag=='epoch_1')
    with PlanLock(plan):
        jobs=read_plan(plan/'plan.tsv')
        jobs=[j.with_updates(metadata={**j.metadata,'eval_epoch':epoch,
                   'dfm13_cursor_epoch_pending':False}) if j.job_id.startswith(PREFIX)
                   and j.metadata.get('ckpt_tag')==tag and j.action!=Action.TRAIN_UNTIL_STEP else j for j in jobs]
        write_plan(plan/'plan.tsv',jobs)


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('mode',choices=['arm','gate','install','watch','segment'])
    parser.add_argument('--plan-dir',type=Path,default=PLAN)
    parser.add_argument('--control',type=Path,default=CONTROL)
    args,rest=parser.parse_known_args()
    os.chdir(ROOT)
    os.environ['PATH']='/home/ucloud/miniforge3/envs/hrm/bin:/usr/local/cuda/bin:'+os.environ.get('PATH','')
    os.environ['OMP_NUM_THREADS']=os.environ['MKL_NUM_THREADS']='1'
    if args.mode=='segment':return segment(args.plan_dir,args.control,rest)
    if rest:parser.error('Unexpected arguments')
    if args.mode=='gate':return readiness_gate(args.plan_dir,args.control)
    with lock(args.control/'.scheduler.lock'):
        if args.mode=='arm':
            result=arm(args.plan_dir,args.control)
            print('Armed; retired',len(result['removed_ids']),'future rows',flush=True)
        else:
            while not (args.control/'prepared.json').exists():
                if args.mode!='watch':raise FileNotFoundError('Existing packing watcher has not published prepared.json')
                write_json(args.control/'scheduler-progress.json',dict(phase='waiting_existing_packing_watcher',time=time.time()))
                time.sleep(30)
            try:
                result=install(args.plan_dir,args.control)
            except Exception as exc:
                write_json(args.control/'scheduler-failure.json',dict(error=repr(exc),time=time.time(),
                           old_future_training_disabled=True))
                raise
            write_json(args.control/'scheduler-progress.json',dict(phase='installed_waiting_3150_evaluations',jobs=len(result['job_ids']),time=time.time()))
            print('Installed',len(result['job_ids']),'jobs; end step',result['end_step'],flush=True)
            if args.mode=='watch':
                while not complete(SOURCE,f'step_{START}'):
                    write_json(args.control/'scheduler-progress.json',dict(phase='installed_waiting_3150_checkpoint',time=time.time()))
                    time.sleep(30)
                read_prepared(args.control)
                fresh_resume(args.control)
                write_json(args.control/'scheduler-progress.json',dict(phase='resume_ready_waiting_eval_success',time=time.time()))


if __name__=='__main__':main()
