#!/home/ucloud/miniforge3/envs/hrm/bin/python
"""Append four expanded baseline panels, serialized after population panels."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import schedule_dfm13_v2_population_workspace as pop
from scripts.schedule_dfm13_wave34_baseline import (
    PLAN,Action,JobStatus,PlanLock,read_plan,write_plan,load,write_json,file_hash,boundary,check_graph)
ID='dfm13-xl-expanded-baseline-workspace'
BASELINE='dfm13-xl-expanded-dala-v2-step_3150000'
MAPPING=pop.WORK/'expanded-traditional-v2-mapping.json'
CONTROL=ROOT/'data/dfm13/expanded-workspace-plan-20261006'
OUT=ROOT/'logs/wandb_workspace_specs/3fvncok3gjh-expanded-traditional-at-baseline'
RECEIPT=ROOT/'logs/wandb_workspace_specs/3fvncok3gjh-expanded-traditional-baseline-verified.json'


def commands():
    base=['/home/ucloud/miniforge3/envs/hrm/bin/python',str(pop.PATCH),'--output',str(OUT)]
    return [base+['--verify-remote-sync','--replacement-mapping',str(MAPPING),'--sync-receipt',str(RECEIPT)],
        base+['--population',str(pop.POPULATION),'--replacement-mapping',str(MAPPING)],
        base+['--population',str(pop.POPULATION),'--apply-prepared','--sync-receipt',str(RECEIPT)]]


def build(jobs):
    if any(j.job_id==ID for j in jobs):raise ValueError('Already installed')
    template=next(j for j in jobs if j.job_id==pop.ID)
    if template.status!=JobStatus.PENDING:raise ValueError('Population patch already started')
    out=[]
    for j in jobs:
        if j.job_id==pop.ID:
            j=j.with_updates(metadata={**j.metadata,'source_pins':{str(p):file_hash(p) for p in
                (pop.MAPPING,pop.POPULATION,pop.PATCH,Path(pop.__file__).resolve())}})
        if j.action==Action.WAIT_CHECKPOINT and boundary(j)==3200000:
            j=j.with_updates(deps=tuple(dict.fromkeys((*j.deps,ID))))
        out.append(j)
    row=template.with_updates(job_id=ID,name='expanded-baseline-workspace',deps=(BASELINE,pop.ID),
        log_dir=str(PLAN/'todo5'/'expanded-baseline-workspace'),metadata={
            'python_bin':str(Path(__file__).resolve()),'workspace_only':True,
            'source_pins':{str(p):file_hash(p) for p in (MAPPING,pop.POPULATION,pop.PATCH,Path(__file__).resolve(),Path(pop.__file__).resolve())}})
    out.append(row);check_graph(out);return out


def install():
    CONTROL.mkdir(parents=True,exist_ok=True)
    with PlanLock(PLAN):
        if not (PLAN/'stop.request').exists():raise ValueError('Must remain paused')
        before=read_plan(PLAN/'plan.tsv');after=build(before);backup=CONTROL/'plan-before.tsv'
        if backup.exists():raise ValueError('Prior installation')
        write_plan(backup,before);write_plan(PLAN/'plan.tsv',after)
        write_json(CONTROL/'installed.json',dict(job_id=ID,deps=[BASELINE,pop.ID],
            commands=commands(),population_mapping=str(pop.MAPPING),population_panels=34,
            expanded_panels=4,no_history_write=True,no_launch=True))


def dispatch():
    with PlanLock(PLAN):
        jobs=read_plan(PLAN/'plan.tsv');by={j.job_id:j for j in jobs};row=by[ID]
        if any(by[d].status!=JobStatus.DONE for d in row.deps):raise ValueError('Baseline/workspace incomplete')
        for p,h in row.metadata['source_pins'].items():
            if file_hash(p)!=h:raise ValueError('Workspace pin drift: '+p)
    for argv in commands():subprocess.run(argv,cwd=ROOT,check=True)

if __name__=='__main__':
    if sys.argv[1:]==['install']:install()
    elif sys.argv[1:]==['scripts/generate_dfm5_l_eval_comparison_report.py']:dispatch()
    else:raise SystemExit('Use install or scheduler dispatch')
