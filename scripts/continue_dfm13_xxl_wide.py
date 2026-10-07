"""Validate DFM13 readiness and continue XXL-wide with the existing eval campaign."""
import argparse
import copy
import fcntl
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eval_scheduler.eval_scheduler.locking import PlanLock
from eval_scheduler.eval_scheduler.model import JobStatus, read_plan, write_plan
from scripts.stop_training_at_complete_checkpoint import complete

PLAN = ROOT/'logs/scheduler/dfm10_XL_epoch9_20260831'
OLD = 'checkpoints/dfm11/XXL-wide-from-dfm10-epoch1'
CKPT = 'checkpoints/dfm13/XXL-wide-from-dfm11-epoch2'
DATA = ROOT/'data/sampled_dfm13'
PREFIX = 'xxlw-dfm13-'
TEMPLATE = 'xxlw-dfm11-650000-'
PY = '/home/ucloud/miniforge3/envs/hrm/bin/python'


def state(tag):
    return json.loads((ROOT/CKPT/f'checkpoint_state_{tag}.json').read_text())


def finalize(target):
    ready = complete(ROOT/CKPT, f'step_{target}')
    finished = complete(ROOT/CKPT, 'epoch_3')
    if not (ready or finished):
        raise RuntimeError('Training exited without a complete boundary/epoch checkpoint')
    epoch = None
    if ready:
        count = len(np.load(DATA/'epoch_2/inst_start.npy', mmap_mode='r'))
        epoch = 2 + state(f'step_{target}')['global_row_cursor_in_epoch']/count
    with PlanLock(PLAN):
        jobs = read_plan(PLAN/'plan.tsv')
        out = []
        for job in jobs:
            if job.job_id.startswith(PREFIX) and job.status == JobStatus.PENDING:
                meta = dict(job.metadata)
                boundary = meta.get('dfm13_boundary')
                if boundary == target and epoch is not None:
                    meta['eval_epoch'] = epoch
                if finished and boundary is not None and (boundary > target or (boundary == target and not ready)):
                    job = job.with_updates(status=JobStatus.SKIPPED)
                    meta['skip_reason'] = 'DFM13 epoch_3 finished before boundary'
                job = job.with_updates(metadata=meta)
            if finished and job.job_id == PREFIX+'epoch_3-wait-2484101':
                dep = (f'{PREFIX}{target}-xxlw-teardown-353465' if ready
                       else f'{PREFIX}train-{target}')
                job = job.with_updates(deps=(dep,))
            out.append(job)
        write_plan(PLAN/'plan.tsv', out)


def build(jobs, total):
    assert not any(j.job_id.startswith(PREFIX) for j in jobs)
    template = [j for j in jobs if j.job_id.startswith(TEMPLATE)]
    assert len(template) == 290
    train = next(j for j in jobs if j.job_id == 'xxlw-dfm11-train-800000')
    argv = shlex.split(train.metadata['command'])
    begin = argv.index('--') + 1
    argv = argv[:2] + [PY, str(Path(__file__).resolve()), 'segment', '--'] + argv[begin:]
    replacements = dict(data='dfm13', epochs='3', checkpoint_path=CKPT,
                        training_total_steps=str(total))
    argv = [a for a in argv if a.lstrip('+').split('=',1)[0] not in replacements]
    argv += [f'{k}={v}' for k,v in replacements.items()]
    # Apart from corpus, epoch count, checkpoint destination and progress total,
    # all optimizer, recurrence, precision and logging overrides are inherited.
    assert all(x in argv for x in ['lr=3e-4', 'lr_auto=true', 'arch.bp_max_steps=8',
                                  '+arch.bp_min_steps=8', 'gradient_accumulation_steps=4',
                                  'wandb_run_id=dfm10-xxl-wide', 'reset_ema_on_resume=false'])
    out = []

    def add_eval(tag, label, dep, boundary):
        mapping = {j.job_id: PREFIX+label+'-'+j.job_id[len(TEMPLATE):] for j in template}
        def convert(v):
            if isinstance(v,str):
                return v.replace('dfm11_XXL_wide','dfm13_XXL_wide').replace('step_650000',tag)
            if isinstance(v,dict): return {k:convert(x) for k,x in v.items()}
            if isinstance(v,list): return [convert(x) for x in v]
            return v
        for j in template:
            meta = convert(copy.deepcopy(j.metadata))
            meta.pop('dfm11_boundary',None)
            meta.update(ckpt_path=CKPT, ckpt_tag=tag, dfm13_boundary=boundary,
                        eval_epoch=3.0 if boundary is None else 2.0)
            deps = (dep,) if j.action.value=='wait_checkpoint' else tuple(mapping[d] for d in j.deps)
            out.append(j.with_updates(job_id=mapping[j.job_id], deps=deps,
                status=JobStatus.PENDING, attempt=0, metadata=meta,
                name=convert(j.name), log_dir=convert(j.log_dir)))
        return mapping[TEMPLATE+'xxlw-teardown-353465']

    previous = None
    previous_train = None
    resume = 'epoch_2'
    for target in range(800000, math.ceil(total/50000)*50000+100001, 50000):
        job_id = PREFIX+f'train-{target}'
        meta = dict(train.metadata, command=shlex.join(argv), ckpt_path=CKPT,
                    ckpt_tag=f'step_{target}', stop_after_step=target,
                    completion_checkpoint_tag='epoch_3', resume_from_tag=resume,
                    resume_ckpt_path=OLD if resume=='epoch_2' else CKPT,
                    dfm13_boundary=target)
        meta.pop('dfm11_boundary',None)
        deps = tuple(dict.fromkeys(x for x in (previous,previous_train) if x))
        out.append(train.with_updates(job_id=job_id, name=f'step_{target}',
            deps=deps, status=JobStatus.PENDING, attempt=0, metadata=meta,
            log_dir=f'logs/training/dfm13_XXL_wide/to_{target}'))
        previous = add_eval(f'step_{target}',str(target),job_id,target)
        previous_train = job_id
        resume = f'step_{target}'
    add_eval('epoch_3','epoch_3',previous,None)
    known = {j.job_id for j in jobs+out}
    assert len(known)==len(jobs+out)
    assert all(set(j.deps)<=known for j in out)
    return out


def validate():
    receipt = json.loads((ROOT/'data/dfm13_build/complete.json').read_text())
    metadata = json.loads((DATA/'metadata.json').read_text())
    assert receipt['status']=='ready' and receipt['epochs']==3
    assert receipt['metadata']==metadata
    assert complete(ROOT/OLD,'epoch_2')
    saved = json.loads((ROOT/OLD/'checkpoint_state_epoch_2.json').read_text())
    assert saved['step']==754208 and saved['epoch']==2
    tokens = np.load(DATA/'tokens.npy',mmap_mode='r')
    reports=json.loads((DATA/'build-receipt.json').read_text())['epochs']
    for e in range(3):
        arrays={f:np.load(DATA/f'epoch_{e}'/(f+'.npy'),mmap_mode='r')
                for f in ('inst_start','resp_start','inst_len','resp_len')}
        assert all(len(v)==reports[e]['rows'] for v in arrays.values())
        total=0
        for start in range(0,reports[e]['rows'],1_000_000):
            s=slice(start,start+1_000_000)
            length=arrays['inst_len'][s]+arrays['resp_len'][s]
            assert np.all(length<=4097)
            total+=int(length.sum())
            for p in ('inst','resp'):
                assert np.all(arrays[p+'_start'][s]+arrays[p+'_len'][s]<=len(tokens))
        assert total==reports[e]['tokens']
    return saved['step']+math.ceil(reports[2]['tokens']/262144*1.05)


def watch():
    env=os.environ.copy()
    env['PATH']=str(Path(PY).parent)+':'+env['PATH']
    retries=0
    while not (ROOT/'data/dfm13_build/complete.json').exists():
        if (ROOT/'data/dfm13_build/cancel-continuation').exists():
            raise RuntimeError('Continuation cancelled by request file')
        if subprocess.run(['pgrep','-f','python.*scripts/build_dfm13_remote.py'],
                          stdout=subprocess.DEVNULL).returncode:
            transfer=subprocess.run(['pgrep','-f','rsync.*sampled_dfm12'],
                                    stdout=subprocess.DEVNULL).returncode==0
            if not transfer:
                if retries>=3:
                    raise RuntimeError('DFM13 build failed after three retries; training not launched')
                retries+=1
                with (ROOT/'logs/dfm13_build/build.log').open('a') as f:
                    subprocess.Popen([PY,'-u','scripts/build_dfm13_remote.py'],env=env,
                        stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
                print('Restarted resumable build, retry',retries,flush=True)
        print(time.strftime('%FT%T'), 'Waiting for complete DFM13 build',flush=True)
        time.sleep(60)
    if (ROOT/'data/dfm13_build/cancel-continuation').exists():
        raise RuntimeError('Continuation cancelled by request file')
    total=validate()
    with PlanLock(PLAN):
        jobs=read_plan(PLAN/'plan.tsv')
        if not any(j.job_id.startswith(PREFIX) for j in jobs):
            additions=build(jobs,total)
            backup=PLAN/'plan.before-dfm13.tsv'
            if backup.exists(): raise RuntimeError('Unexpected existing plan backup')
            shutil.copy2(PLAN/'plan.tsv',backup)
            write_plan(PLAN/'plan.tsv',jobs+additions)
            print('Appended',len(additions),'jobs; estimated total',total,flush=True)
    subprocess.run([PY,'-m','eval_scheduler','clear-stop','--plan-dir',str(PLAN)],check=True)
    with (PLAN/'runner.log').open('a') as f:
        proc=subprocess.Popen([PY,'-u','-m','eval_scheduler','run','--plan-dir',str(PLAN),
            '--gpus','0,1,2,3,4,5,6,7','--persistent-vllm'],env=env,
            stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    print('Scheduler started',proc.pid,flush=True)
    log=ROOT/'logs/training/dfm13_XXL_wide/to_800000/train_until_step_800000.log'
    while True:
        if log.exists():
            with log.open('rb') as f:
                f.seek(max(0,log.stat().st_size-32768))
                tail=f.read().decode(errors='replace')
            if any(f'{step}/{total}' in tail for step in range(754210,754501,5)):
                print('Verified training advancing past restored step 754208',flush=True)
                return
        if proc.poll() is not None:
            raise RuntimeError('Scheduler exited before training progress verified')
        print(time.strftime('%FT%T'), 'Waiting for GPU headroom/startup/training progress',flush=True)
        time.sleep(30)


def main():
    os.chdir(ROOT)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['watch','segment','preview'])
    args,command=parser.parse_known_args()
    if args.mode=='segment':
        if command and command[0]=='--':command.pop(0)
        target = int(next(a.split('=',1)[1] for a in command if a.startswith('stop_after_step=')))
        if target > 900000:
            raise RuntimeError('DFM13 continuation past 900K is superseded: prepare and validate the DFM14 handoff first')
        subprocess.run(command,check=True)
        finalize(target)
    elif args.mode=='preview':
        with PlanLock(PLAN):
            jobs=build(read_plan(PLAN/'plan.tsv'),1200000)
        print('Preview:',len(jobs),'jobs')
        print(jobs[0].metadata['command'])
    else:
        with (ROOT/'data/dfm13_build/continuation.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            watch()


if __name__=='__main__':
    main()
