#!/home/ucloud/miniforge3/envs/hrm/bin/python
"""Install/dispatch the scoped historical average sync; no training edits."""
import os
from pathlib import Path
import runpy
import sys
import subprocess

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.schedule_dfm13_wave34_baseline import (
    PLAN, MARK, SYNC_ID, Action, JobStatus, PlanLock, read_plan, write_plan,
    boundary, check_graph, file_hash, load, write_json)

ID='dfm13-xl-todo5-historical-average-sync'
CONTROL=ROOT/'data/dfm13/todo5-average-sync-20261006'
PAYLOAD=ROOT/'logs/rejudge_talemaader_v2/averages/prepared-future-compatible-v2.json'
SCRIPT=ROOT/'scripts/prepare_talemaader_v2_averages.py'
WORKSPACE=ROOT/'logs/wandb_workspace_specs/3fvncok3gjh-deferred-final-20261006'
HIST=ID+'-workspace-history'
POP=ID+'-workspace-populations'


def validate_payload():
    from scripts.prepare_talemaader_v2_averages import RUN, definition_hash
    p=load(PAYLOAD)
    if p['run_path']!=RUN or definition_hash(p['rows'])!=p['rows_sha256']:
        raise ValueError('Payload binding mismatch')
    if len(p['points'])!=67 or not all(x['rejudge_available'] for x in p['points']):
        raise ValueError('Expected67 completed rejudge points')
    for path,sha in p['inputs'].items():
        if file_hash(path)!=sha:raise ValueError('Input drift: '+path)
    return p


def build(jobs):
    if any(j.job_id==ID for j in jobs):raise ValueError('Already installed')
    sync=next(j for j in jobs if j.job_id==SYNC_ID)
    train=next(j for j in jobs if j.action==Action.TRAIN_UNTIL_STEP and boundary(j)==3200000)
    if train.status!=JobStatus.RUNNING or sync.status!=JobStatus.PENDING:
        raise ValueError('Unexpected training/sync state')
    row=sync.with_updates(job_id=ID,name='todo5-historical-average-sync',deps=(SYNC_ID,),
        log_dir=str(PLAN/'todo5-average-sync'),metadata={
            'python_bin':str(Path(__file__).resolve()),'todo5_average_sync':True,
            'payload':str(PAYLOAD),'payload_sha256':file_hash(PAYLOAD),
            'implementation_sha256':file_hash(SCRIPT),
            'source_pin_path':str(Path(__file__).resolve()),
            'source_pin_sha256':file_hash(__file__),
            'wandb_project':'DFM5','wandb_run_id':sync.metadata['wandb_run_id']})
    successors={}
    for job in jobs:
        if job.action==Action.AVERAGE and boundary(job)>=3200000 and job.metadata.get('average_prefix')=='headline_avg_v3':
            if job.status!=JobStatus.PENDING or job.attempt:raise ValueError('Future average already attempted')
            step=boundary(job)
            if step in successors:raise ValueError('Ambiguous future average template')
            successors[step]=job.with_updates(job_id=f'dfm13-xl-todo5-step_{step}-average',
                name='talemaader-v2-successor',log_dir=str(PLAN/'todo5'/f'step_{step}'/'average'),
                metadata={**job.metadata,'average_prefix':'headline_avg_talemaader_v2',
                    'extra_average_prefixes':['suite_avg_talemaader_v2'],
                    'atomic_v3_averages':False,'todo5_successor':True,
                    'python_bin':str(ROOT/'scripts/todo5_future_average'),
                    'source_pin_path':str(ROOT/'scripts/todo5_future_average'),
                    'source_pin_sha256':file_hash(ROOT/'scripts/todo5_future_average'),
                    'legacy_template_job_id':job.job_id})
    out=[]
    for j in jobs:
        if j.metadata.get(MARK) and boundary(j)==3150000 and SYNC_ID in j.deps:
            if j.status!=JobStatus.PENDING or j.attempt:raise ValueError('Baseline already started')
            j=j.with_updates(deps=tuple(dict.fromkeys((*j.deps,ID,HIST))))
        step=boundary(j)
        if j.metadata.get(MARK) and j.action==Action.AVERAGE and step in successors:
            j=j.with_updates(deps=tuple(dict.fromkeys((*j.deps,successors[step].job_id))))
        if j.action==Action.TRAIN_UNTIL_STEP and step>3200000:
            prior=[s for s in successors if s<step]
            if prior:
                if j.status!=JobStatus.PENDING or j.attempt:raise ValueError('Future training already attempted')
                j=j.with_updates(deps=tuple(dict.fromkeys((*j.deps,successors[max(prior)].job_id))))
        if j.action==Action.WAIT_CHECKPOINT and step==3200000:
            j=j.with_updates(deps=tuple(dict.fromkeys((*j.deps,POP))))
        out.append(j)
    baseline=next(j for j in jobs if j.metadata.get(MARK) and boundary(j)==3150000 and j.action==Action.AVERAGE)
    for phase,job_id,deps in [('historical',HIST,(ID,)),('populations',POP,(baseline.job_id,HIST))]:
        mapping=WORKSPACE/('historical-mapping.json' if phase=='historical' else 'population-mapping.json')
        bridge=ROOT/f'scripts/todo5_workspace_{phase}'
        pins={str(p):file_hash(p) for p in (mapping,bridge,Path(__file__).resolve(),ROOT/'scripts/patch_dfm13_workspace.py')}
        out.append(row.with_updates(job_id=job_id,name='todo5-workspace-'+phase,deps=deps,
            log_dir=str(PLAN/'todo5'/phase),metadata={**row.metadata,'python_bin':str(bridge),'workspace_pins':pins}))
    out.extend(successors.values());out.append(row);check_graph(out)
    return out


def install():
    validate_payload()
    CONTROL.mkdir(parents=True,exist_ok=True)
    with PlanLock(PLAN):
        before=read_plan(PLAN/'plan.tsv');after=build(before)
        backup=CONTROL/'plan-before.tsv'
        if backup.exists():raise ValueError('Existing backup; inspect before retry')
        write_plan(backup,before)
        write_plan(PLAN/'plan.tsv',after)
        write_json(CONTROL/'installed.json',dict(job_id=ID,payload=str(PAYLOAD),
            payload_sha256=file_hash(PAYLOAD),plan_sha256=file_hash(PLAN/'plan.tsv'),
            training_unchanged=True,high_water_fix_pending=True,
            changed_rows=[j.job_id for old,j in zip(before,after) if old!=j],
            new_rows=[j.job_id for j in after if j.job_id not in {x.job_id for x in before}]))


def dispatch():
    validate=runpy.run_path(str(ROOT/'scripts/talemaader_v2_scheduler_sync'))['validate']
    with PlanLock(PLAN):
        jobs=read_plan(PLAN/'plan.tsv');validate(jobs,sys.argv[1:])
        if next(j for j in jobs if j.job_id==SYNC_ID).status!=JobStatus.DONE:
            raise ValueError('Talemaader sync not complete')
        row=next(j for j in jobs if j.job_id==ID)
        for path,key in ((PAYLOAD,'payload_sha256'),(SCRIPT,'implementation_sha256'),
                         (Path(__file__),'source_pin_sha256')):
            if file_hash(path)!=row.metadata[key]:raise ValueError('Sync source/payload drift')
    validate_payload()
    os.chdir(ROOT)
    python='/home/ucloud/miniforge3/envs/hrm/bin/python'
    os.execv(python,[python,'-m','scripts.prepare_talemaader_v2_averages',
        '--sync-prepared',str(PAYLOAD),'--paused-step','3200000'])


def workspace_dispatch(phase):
    validate=runpy.run_path(str(ROOT/'scripts/talemaader_v2_scheduler_sync'))['validate']
    with PlanLock(PLAN):
        jobs=read_plan(PLAN/'plan.tsv');validate(jobs,sys.argv[1:])
        row=next(j for j in jobs if j.job_id==(HIST if phase=='historical' else POP))
        by={j.job_id:j for j in jobs}
        if any(by[d].status!=JobStatus.DONE for d in row.deps):raise ValueError('Workspace prerequisite incomplete')
        for path,sha in row.metadata['workspace_pins'].items():
            if file_hash(path)!=sha:raise ValueError('Workspace source drift: '+path)
    mapping=WORKSPACE/('historical-mapping.json' if phase=='historical' else 'population-mapping.json')
    receipt=WORKSPACE/(phase+'-remote-verified.json')
    fresh=WORKSPACE/(phase+'-fresh-at-sync')
    command=['/home/ucloud/miniforge3/envs/hrm/bin/python',str(ROOT/'scripts/patch_dfm13_workspace.py')]
    verify=['--output',str(WORKSPACE),'--verify-remote-sync','--replacement-mapping',str(mapping),'--sync-receipt',str(receipt)]
    if phase=='historical':verify+=['--prepared-history',str(PAYLOAD)]
    for args in (verify,['--output',str(fresh),'--replacement-mapping',str(mapping)],
                 ['--output',str(fresh),'--apply-prepared','--sync-receipt',str(receipt)]):
        subprocess.run(command+args,cwd=ROOT,check=True)


if __name__=='__main__':
    if sys.argv[1:]==['install']:install()
    elif sys.argv[1:]==['scripts/generate_dfm5_l_eval_comparison_report.py']:dispatch()
    else:raise SystemExit('Use install; other entry is scheduler-only')
