"""Apply tested task capacities and resume the paused XL scheduler after GPU cleanup."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import time

from dfm12.io import load, write_json
from scripts.stop_training_at_complete_checkpoint import complete, alive

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'eval_scheduler'))
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import read_plan, write_plan, JobStatus


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--timeout',type=int,default=5400)
    args=parser.parse_args()
    root=ROOT/'data/dfm13/xl3143-all-task-calibration'
    run=root/'grouped-run'
    plan=ROOT/'logs/scheduler/dfm12_XL_epoch11_noidentity'
    deadline=time.monotonic()+args.timeout
    while alive(args.pid):
        if time.monotonic()>deadline:
            command=Path(f'/proc/{args.pid}/cmdline').read_bytes()
            if b'scripts.calibrate_all_eval_tasks' not in command:raise RuntimeError('PID reused')
            os.kill(args.pid,signal.SIGINT)
            print('Calibration time budget reached; preserving completed results',flush=True)
            deadline=time.monotonic()+300
        time.sleep(5)
    if not (run/'cleanup.json').exists():raise RuntimeError('Calibration cleanup not confirmed')
    owned=load(run/'owned-processes.json')
    if any(alive(x['pid']) for x in owned):raise RuntimeError('Calibration server still alive')
    report=load(run/'report.json') if (run/'report.json').exists() else {'tasks':load(run/'progress.json')['results']}
    manifest=load(root/'grouped-manifest.json')
    recommendations={};unmeasured=[]
    for group in manifest['tasks']:
        result=report['tasks'].get(group['key'],{})
        stages=result.get('stages',[])
        if not stages:
            folder=run/'tasks'/group['key'].replace(':','__')
            stages=[load(p)['summary'] for p in folder.glob('c*.json')]
        safe=[s for s in stages if s.get('safe') and s['requests']]
        if not safe:
            unmeasured.extend(group['members']);continue
        best=max(safe,key=lambda s:s['requests_per_second'])
        for key in group['members']:recommendations[key]=dict(group=group['key'],**best)
    checkpoint=ROOT/'checkpoints/dfm12/XL-from-dfm11-epoch10-noidentity'
    if not complete(checkpoint,'ephemeral_step_3143000'):raise RuntimeError('Resume checkpoint incomplete')
    changes=[]
    with PlanLock(plan):
        backup=plan/'plan.before-all-task-calibration-3143k.tsv'
        if backup.exists():raise RuntimeError('Finisher already applied or backup exists')
        shutil.copy2(plan/'plan.tsv',backup)
        jobs=read_plan(plan/'plan.tsv');updated=[]
        for job in jobs:
            if job.job_id=='dfm12-xl-e11-step_3150000-train':
                job=job.with_updates(status=JobStatus.PENDING,metadata={**job.metadata,
                    'resume_from_tag':'ephemeral_step_3143000','resume_ckpt_path':str(checkpoint)})
            key=str(job.action)+':'+job.name
            if job.status==JobStatus.PENDING and key in recommendations:
                best=recommendations[key];batch=best['concurrency'];meta=dict(job.metadata)
                meta.pop('max_connections',None)
                meta['fixed_retry_batch']=False
                if str(job.action).startswith('eval_euroeval'):meta['euroeval_max_concurrent_calls']=batch
                meta['eval_capacity_calibration']=str(root)
                meta['eval_capacity_group']=best['group']
                parts=shlex.split(meta.get('vllm_extra_args',''))
                parts=[p for p in parts if p!='--enforce-eager']
                for flag,value in [('--max-num-seqs','1024'),('--max-num-batched-tokens','16384'),
                                   ('--max-cudagraph-capture-size','512')]:
                    if flag in parts:parts[parts.index(flag)+1]=value
                    else:parts.extend([flag,value])
                meta['vllm_extra_args']=shlex.join(parts)
                changes.append(dict(job_id=job.job_id,old=job.initial_batch,new=batch,group=best['group']))
                job=job.with_updates(initial_batch=batch,metadata=meta)
            updated.append(job)
        write_plan(plan/'plan.tsv',updated)
    write_json(root/'applied.json',dict(recommendations=recommendations,unmeasured=unmeasured,changes=changes,
        resume_step=3143000,target_step=3150000,unmeasured_policy='unchanged; never claim untested settings as calibrated'))
    env=dict(os.environ,PATH=str(Path(sys.executable).parent)+':'+os.environ.get('PATH',''),
             PYTHONPATH=str(ROOT/'eval_scheduler'))
    with (plan/'runner-after-3143k-calibration.log').open('a') as log:
        proc=subprocess.Popen([sys.executable,'-u','-m','eval_scheduler','run','--plan-dir',str(plan),
            '--gpus','0,1,2,3,4,5,6,7','--persistent-vllm'],cwd=ROOT,env=env,
            stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
    write_json(root/'resumed.json',dict(pid=proc.pid,time=time.time(),applied_tasks=len(recommendations),unmeasured=unmeasured))
    print('Scheduler resumed',proc.pid,'calibrated tasks',len(recommendations),'unmeasured',unmeasured,flush=True)

if __name__=='__main__':main()
