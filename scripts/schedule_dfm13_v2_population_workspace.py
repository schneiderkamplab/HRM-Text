#!/home/ucloud/miniforge3/envs/hrm/bin/python
"""Schedule only the v2 population workspace update after real3150 averages."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.schedule_dfm13_wave34_baseline import (
    PLAN,SYNC_ID,Action,JobStatus,PlanLock,read_plan,write_plan,boundary,
    check_graph,load,write_json,file_hash)
ID='dfm13-xl-v2-population-workspace'
BASELINE='dfm13-xl-dala-v2-step_3150000-average'
WORK=ROOT/'logs/wandb_workspace_specs/3fvncok3gjh-deferred-final-20261006'
MAPPING=WORK/'population-additive-v2-all32-mapping.json'
POPULATION=ROOT/'config/multilingual_headline_populations_dfm13_dala_v2_20261006.json'
PATCH=ROOT/'scripts/patch_dfm13_workspace.py'
CONTROL=ROOT/'data/dfm13/v2-population-workspace-plan-20261006'


def commands():
    receipt=WORK/'populations-v2-remote-verified.json';fresh=WORK/'populations-v2-fresh-at-sync'
    base=['/home/ucloud/miniforge3/envs/hrm/bin/python',str(PATCH),'--population',str(POPULATION)]
    return [base+['--output',str(WORK),'--verify-remote-sync','--replacement-mapping',str(MAPPING),'--sync-receipt',str(receipt)],
        base+['--output',str(fresh),'--replacement-mapping',str(MAPPING)],
        base+['--output',str(fresh),'--apply-prepared','--sync-receipt',str(receipt)]]


def build(jobs):
    if any(j.job_id==ID for j in jobs):raise ValueError('Already installed')
    avg=next(j for j in jobs if j.job_id==BASELINE)
    if avg.status!=JobStatus.PENDING:raise ValueError('Baseline unexpectedly started')
    template=next(j for j in jobs if j.job_id==SYNC_ID)
    row=template.with_updates(job_id=ID,name='v2-population-workspace',deps=(BASELINE,),
        log_dir=str(PLAN/'todo5'/'population-v2-workspace'),metadata={
            'python_bin':str(Path(__file__).resolve()),'workspace_only':True,
            'source_pins':{str(p):file_hash(p) for p in (MAPPING,POPULATION,PATCH,Path(__file__).resolve())}})
    out=[]
    for j in jobs:
        if j.action==Action.WAIT_CHECKPOINT and boundary(j)==3200000:
            if j.status!=JobStatus.PENDING or j.attempt:raise ValueError('3200 wait already attempted')
            j=j.with_updates(deps=tuple(dict.fromkeys((*j.deps,ID))))
        out.append(j)
    out.append(row);check_graph(out);return out


def install():
    CONTROL.mkdir(parents=True,exist_ok=True)
    mapping=load(MAPPING)
    if mapping['replacements'] or len(mapping['append_panels'])!=34:raise ValueError('Unexpected workspace scope')
    if any('/dfm13_multilingual_v1/' in p['key'] or '/dfm13_all_languages_v1/' in p['key'] for p in mapping['append_panels']):
        raise ValueError('Old population mapping prohibited')
    with PlanLock(PLAN):
        if not (PLAN/'stop.request').exists():raise ValueError('Scheduler must remain paused')
        before=read_plan(PLAN/'plan.tsv');after=build(before);backup=CONTROL/'plan-before.tsv'
        if backup.exists():raise ValueError('Prior installation evidence exists')
        write_plan(backup,before);write_plan(PLAN/'plan.tsv',after)
        write_json(CONTROL/'installed.json',dict(job_id=ID,depends_on=BASELINE,commands=commands(),
            historical_reapplication=False,history_writer=False,no_launch=True,plan_sha256=file_hash(PLAN/'plan.tsv')))


def dispatch():
    with PlanLock(PLAN):
        jobs=read_plan(PLAN/'plan.tsv');by={j.job_id:j for j in jobs};row=by[ID]
        if any(by[d].status!=JobStatus.DONE for d in row.deps):raise ValueError('V2 baseline incomplete')
        if any(j.action==Action.TRAIN_UNTIL_STEP and j.status==JobStatus.RUNNING for j in jobs):raise ValueError('Training active')
        for p,h in row.metadata['source_pins'].items():
            if file_hash(p)!=h:raise ValueError('Workspace pin drift: '+p)
    for command in commands():subprocess.run(command,cwd=ROOT,check=True)

if __name__=='__main__':
    if sys.argv[1:]==['install']:install()
    elif sys.argv[1:]==['scripts/generate_dfm5_l_eval_comparison_report.py']:dispatch()
    else:raise SystemExit('Use install or scheduler REPORT dispatch')
