"""Add42 v2 tasks and successor populations without replacing legacy rows."""
import argparse
import copy
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.schedule_dfm13_wave34_baseline import (
    PLAN,MARK,Action,JobStatus,PlanLock,read_plan,write_plan,load,write_json,
    file_hash,boundary,check_graph,canonical_log_dir)
CONTROL=ROOT/'data/dfm13/dala-v2-plan-20261006'
COMPLETION=ROOT/'data/dfm13/dala-v2-existing21-evals-20261006-v1/completion.json'
REGISTRY=ROOT/'config/dfm13_dala_v2_existing21_registry_20261006.json'
POPULATIONS=ROOT/'config/multilingual_headline_populations_dfm13_dala_v2_20261006.json'
FLAG='dala_v2_existing21_addition'


def inputs():
    receipt=load(COMPLETION)
    if receipt.get('complete') is not True or len(receipt['tasks'])!=42:raise ValueError('Incomplete42-task preflight')
    for p,h in receipt['files'].items():
        if file_hash(p)!=h:raise ValueError('Coverage drift: '+p)
    registry=load(REGISTRY)
    if len(registry)!=42:raise ValueError('Expected42 suites')
    return registry


def build(jobs,registry,populations):
    if any(j.metadata.get(FLAG) for j in jobs):raise ValueError('Already installed')
    additions=[];gates={};gpu_by_step={}
    averages=[j for j in jobs if j.metadata.get(MARK) and j.action==Action.AVERAGE]
    for avg in averages:
        step=boundary(avg);block=[j for j in jobs if j.metadata.get(MARK) and boundary(j)==step]
        if any(j.status!=JobStatus.PENDING or j.attempt for j in block):raise ValueError('Extension already attempted')
        prefix=f'dfm13-xl-dala-v2-step_{step}-';gpu=[];merges=[]
        for task in registry:
            family='gec_dala_' if task['suite'].startswith('gec_dala_') else 'dala_'
            template=next(j for j in block if j.action==Action.EVAL_DFM and j.name.startswith(family))
            merger=next(j for j in block if j.action==Action.MERGE_DFM and j.name==template.name)
            meta={**copy.deepcopy(template.metadata),FLAG:True,'dfm_suite':task['suite'],
                  'dfm_single_tasks_config':task['config'],'language':task['language'],
                  'dfm_max_gen_toks':task['max_tokens'],'template_job_id':template.job_id}
            ids=[]
            for shard in range(task['shards']):
                j=template.with_updates(job_id=prefix+task['name']+f'-{shard}',name=task['name'],
                    metadata=meta,shard=shard,shards=task['shards'])
                j=j.with_updates(log_dir=str(canonical_log_dir(j)));additions.append(j);ids.append(j.job_id)
            j=merger.with_updates(job_id=prefix+task['name']+'-merge',name=task['name'],
                deps=tuple(ids),metadata={**meta,'shards':task['shards']})
            additions.append(j.with_updates(log_dir=str(canonical_log_dir(j))))
            gpu.extend(ids);merges.append(j.job_id)
        successor=avg.with_updates(job_id=prefix+'average',name='dala-v2-populations',
            deps=tuple([avg.job_id,*merges]),metadata={**avg.metadata,FLAG:True,
                'multilingual_manifest':str(populations)},log_dir=str(PLAN/'dala-v2'/f'step_{step}'/'average'))
        additions.append(successor);gates[step]=successor.job_id;gpu_by_step[step]=gpu
    out=[]
    for j in jobs:
        extra=[];step=boundary(j)
        if j.action==Action.TERMINAL_BARRIER and step in gpu_by_step and j.status==JobStatus.PENDING:
            if j.deps_mode!='terminal':raise ValueError('Cleanup requires terminal barrier')
            extra+=gpu_by_step[step]
        if j.action==Action.WAIT_CHECKPOINT and step==3200000:extra.append(gates[3150000])
        if j.action==Action.TRAIN_UNTIL_STEP and step>3200000:
            extra.append(gates[max(s for s in gates if s<step)])
        if extra:
            if j.status!=JobStatus.PENDING or j.attempt:raise ValueError('Cannot alter attempted row')
            j=j.with_updates(deps=tuple(dict.fromkeys((*j.deps,*extra))))
        out.append(j)
    out+=additions;check_graph(out);return out


def execute(install=False):
    registry=inputs();CONTROL.mkdir(parents=True,exist_ok=True)
    pop=load(POPULATIONS)
    pop['populations']=[p for p in pop['populations'] if p['id'] in ('dfm13_multilingual_v2','dfm13_all_languages_v2')]
    if len(pop['populations'])!=2:raise ValueError('Expected two additive successor populations')
    path=CONTROL/'successor-populations.json';write_json(path,pop)
    with PlanLock(PLAN):
        before=read_plan(PLAN/'plan.tsv');after=build(before,registry,path)
        report=dict(installed=install,new_jobs=len(after)-len(before),coverage_pins=load(COMPLETION)['files'],
            population_sha256=file_hash(path),training3200_unchanged=next(j for j in before if j.action==Action.TRAIN_UNTIL_STEP and boundary(j)==3200000)==next(j for j in after if j.action==Action.TRAIN_UNTIL_STEP and boundary(j)==3200000))
        if install:
            backup=CONTROL/'plan-before.tsv'
            if backup.exists():raise ValueError('Prior installation backup exists')
            inputs();write_plan(backup,before);write_plan(PLAN/'plan.tsv',after)
        else:write_plan(CONTROL/'preview.tsv',after)
        write_json(CONTROL/('installed.json' if install else 'preview.json'),report)
        print(report['new_jobs'],'new rows; installed',install)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--install',action='store_true');execute(p.parse_args().install)
