#!/home/ucloud/miniforge3/envs/hrm/bin/python
"""One atomic expanded traditional AVERAGE per checkpoint, after other averages."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.schedule_dfm13_wave34_baseline import (
    PLAN,Action,JobStatus,PlanLock,read_plan,write_plan,load,write_json,file_hash,
    boundary,check_graph,SYNC_ID,MARK,EVALS)
FLAG='expanded_dala_v2_average'
CONTROL=ROOT/'data/dfm13/expanded-dala-v2-average-plan-20261006'
LOGGER=ROOT/'scripts/log_expanded_dala_v2_averages.py'


def build(jobs):
    if any(j.metadata.get(FLAG) for j in jobs):raise ValueError('Already installed')
    template=next(j for j in jobs if j.job_id==SYNC_ID)
    averages=[j for j in jobs if j.metadata.get('dala_v2_existing21_addition') and j.action==Action.AVERAGE]
    additions=[];gates={}
    for avg in averages:
        step=boundary(avg);block=[j for j in jobs if boundary(j)==step]
        roots={suite:set(avg.metadata.get('additional_'+suite+'_roots',[])) for suite in ('standard','dfm','euroeval')}
        deps=[]
        for j in block:
            if j.status==JobStatus.SKIPPED or 'valeu' in j.name.lower():continue
            if j.action in EVALS or j.action in (Action.MERGE_STANDARD,Action.MERGE_DFM,Action.MERGE_IFEVAL,Action.AVERAGE):
                deps.append(j.job_id)
                for suite,key in [('standard','log_root'),('dfm','dfm_log_root'),('euroeval','euroeval_log_root')]:
                    if key in j.metadata:
                        root=str(j.metadata[key])
                        if suite=='euroeval':root+='/'+j.metadata['ckpt_tag']
                        roots[suite].add(root)
                    roots[suite].update(j.metadata.get('additional_'+suite+'_roots',[]))
        paths=[LOGGER,Path(__file__).resolve(),ROOT/'scripts/log_dfm5_headline_averages.py',
            ROOT/'scripts/headline_population_registry.py',ROOT/'scripts/log_multilingual_headline_averages.py',
            ROOT/'config/dfm13_dala_heldout_registry_20261006.json',
            ROOT/'config/dfm13_dala_v2_existing21_registry_20261006.json',
            ROOT/'config/multilingual_headline_populations_dfm13_dala_v2_20261006.json']
        row=avg.with_updates(job_id=f'dfm13-xl-expanded-dala-v2-step_{step}',name='expanded-dala-v2',
            deps=tuple(dict.fromkeys(deps)),log_dir=str(PLAN/'expanded-dala-v2'/f'step_{step}'),
            metadata={**avg.metadata,FLAG:True,'python_bin':'/home/ucloud/miniforge3/envs/hrm/bin/python',
                'average_prefix':'headline_avg_dala_v2','extra_average_prefixes':['suite_avg_dala_v2'],
                'atomic_v3_averages':False,
                **{'additional_'+k+'_roots':sorted(v) for k,v in roots.items()},
                'expanded_roots':{k:sorted(v) for k,v in roots.items()},
                'source_pins':{str(p):file_hash(p) for p in paths}})
        additions.append(row);gates[step]=row.job_id
    out=[]
    for j in jobs:
        extra=[];step=boundary(j)
        if j.action==Action.WAIT_CHECKPOINT and step==3200000:extra=[gates[3150000]]
        if j.action==Action.TRAIN_UNTIL_STEP and step>3200000:extra=[gates[max(s for s in gates if s<step)]]
        if extra:
            if j.status!=JobStatus.PENDING or j.attempt:raise ValueError('Attempted downstream row')
            j=j.with_updates(deps=tuple(dict.fromkeys((*j.deps,*extra))))
        out.append(j)
    out+=additions;check_graph(out);return out


def command(row):
    m=row.metadata
    args=['/home/ucloud/miniforge3/envs/hrm/bin/python',str(LOGGER),
        '--step',str(m['eval_step']),'--epoch',str(m['eval_epoch']),
        '--report',str(Path(row.log_dir)/'expanded-metrics.json'),
        '--project',m['wandb_project'],'--run-id',m['wandb_run_id'],'--run-name',m['wandb_run_name']]
    for suite,roots in m['expanded_roots'].items():
        for root in roots:args+=['--'+suite+'-root',root]
    return args


def execute(install=False):
    CONTROL.mkdir(parents=True,exist_ok=True)
    with PlanLock(PLAN):
        before=read_plan(PLAN/'plan.tsv');after=build(before)
        if install:
            from eval_scheduler import runtime
            import inspect
            source=inspect.getsource(runtime.run_average)
            if 'suite_avg_dala_v2' not in source or 'extra_average_prefixes' not in source.split('if job.metadata.get("multilingual_manifest")')[0]:
                raise ValueError('Await atomic both-prefix expanded dispatch')
            if not (PLAN/'stop.request').exists():raise ValueError('Keep scheduler paused')
            backup=CONTROL/'plan-before.tsv'
            if backup.exists():raise ValueError('Prior install evidence')
            write_plan(backup,before);write_plan(PLAN/'plan.tsv',after)
        else:write_plan(CONTROL/'preview.tsv',after)
        write_json(CONTROL/('installed.json' if install else 'preview.json'),dict(installed=install,
            rows=[{'id':j.job_id,'deps':list(j.deps),'command':command(j)} for j in after[len(before):]],
            no_launch=True,historical_sync=False))


def dispatch():
    with PlanLock(PLAN):
        jobs=read_plan(PLAN/'plan.tsv');by={j.job_id:j for j in jobs}
        rows=[j for j in jobs if j.metadata.get(FLAG) and j.status==JobStatus.RUNNING]
        if len(rows)!=1:raise ValueError('Expected exactly one running expanded REPORT')
        row=rows[0]
        if any(by[d].status!=JobStatus.DONE for d in row.deps):raise ValueError('Inputs incomplete')
        for p,h in row.metadata['source_pins'].items():
            if file_hash(p)!=h:raise ValueError('Expanded logger pin drift: '+p)
    subprocess.run(command(row),cwd=ROOT,check=True)

if __name__=='__main__':
    if sys.argv[1:]==['scripts/generate_dfm5_l_eval_comparison_report.py']:dispatch()
    elif sys.argv[1:]==['install']:execute(True)
    elif sys.argv[1:]==['prepare']:execute(False)
    else:raise SystemExit('Use prepare/install or scheduler dispatch')
