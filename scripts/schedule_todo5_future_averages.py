"""Install future Talemaader successor averages only; no historical writers."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.schedule_dfm13_wave34_baseline import (
    PLAN,Action,JobStatus,PlanLock,read_plan,write_plan,boundary,check_graph,
    write_json,file_hash)
CONTROL=ROOT/'data/dfm13/todo5-future-averages-20261006'


def build(jobs):
    if any(j.metadata.get('todo5_talemaader_future') for j in jobs):raise ValueError('Already installed')
    additions=[];gates={}
    for job in jobs:
        if job.action!=Action.AVERAGE or boundary(job)<3200000 or job.metadata.get('average_prefix')!='headline_avg_v3':continue
        if job.status!=JobStatus.PENDING or job.attempt:raise ValueError('Average already attempted')
        step=boundary(job)
        if step in gates:raise ValueError('Ambiguous checkpoint average')
        row=job.with_updates(job_id=f'dfm13-xl-todo5-step_{step}-average',name='talemaader-v2-successor',
            log_dir=str(PLAN/'todo5'/f'step_{step}'/'average'),metadata={**job.metadata,
                'average_prefix':'headline_avg_talemaader_v2',
                'extra_average_prefixes':['suite_avg_talemaader_v2'],
                'average_scope':'all','atomic_v3_averages':False,
                'python_bin':str(ROOT/'scripts/todo5_future_average'),
                'todo5_talemaader_future':True,'legacy_template_job_id':job.job_id,
                'source_pins':{str(p):file_hash(p) for p in (ROOT/'scripts/todo5_future_average',
                    ROOT/'scripts/log_dfm5_headline_averages.py',ROOT/'scripts/prepare_talemaader_v2_averages.py')}})
        additions.append(row);gates[step]=row.job_id
    if not additions:raise ValueError('No future averages found')
    out=[]
    for job in jobs:
        if job.action==Action.TRAIN_UNTIL_STEP and boundary(job)>3200000:
            prior=[s for s in gates if s<boundary(job)]
            if prior:
                if job.status!=JobStatus.PENDING or job.attempt:raise ValueError('Training already attempted')
                job=job.with_updates(deps=tuple(dict.fromkeys((*job.deps,gates[max(prior)]))))
        out.append(job)
    out+=additions;check_graph(out);return out


def install():
    CONTROL.mkdir(parents=True,exist_ok=True)
    with PlanLock(PLAN):
        if not (PLAN/'stop.request').exists():raise ValueError('Keep scheduler paused')
        before=read_plan(PLAN/'plan.tsv');after=build(before)
        backup=CONTROL/'plan-before.tsv'
        if backup.exists():raise ValueError('Prior backup exists')
        write_plan(backup,before);write_plan(PLAN/'plan.tsv',after)
        write_json(CONTROL/'installed.json',dict(new_rows=len(after)-len(before),historical_writers_added=0,
            training3200_unchanged=next(j for j in before if j.action==Action.TRAIN_UNTIL_STEP and boundary(j)==3200000)==next(j for j in after if j.action==Action.TRAIN_UNTIL_STEP and boundary(j)==3200000),
            plan_sha256=file_hash(PLAN/'plan.tsv'),no_launch=True))
        print('Installed',len(after)-len(before),'future-only averages')

if __name__=='__main__':install()
