#!/home/ucloud/miniforge3/envs/hrm/bin/python
"""Exclusive XL history append before the normal3200 averages."""
import argparse
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.schedule_dfm13_wave34_baseline import (
    PLAN,Action,JobStatus,PlanLock,read_plan,write_plan,boundary,check_graph,
    load,write_json,file_hash,EVALS,SYNC_ID)
from scripts.backfill_available_eval_averages import canonical_hash
ID='dfm13-xl-step_3200000-historical-available-average-sync'
RUN='peter-sk-sdu/DFM5/dfm8-xl-from-dfm6-dfm7-epoch5-clean-full'
CONTROL=ROOT/'data/dfm13/historical-available-sync-schedule-20261007'
IMPLEMENTATION=ROOT/'scripts/backfill_available_eval_averages.py'


def validate_payload(path):
    payload=load(path);body=dict(payload);expected=body.pop('payload_sha256')
    if canonical_hash(body)!=expected or body['run_path']!=RUN:raise ValueError('Payload identity/hash mismatch')
    if len(body['points'])<67:raise ValueError('Expected at least67 historical XL points')
    for p,h in body['pins'].items():
        if file_hash(p)!=h:raise ValueError('Payload source drift: '+p)
    return payload


def build(jobs,path,payload,prepare_at_execution=False):
    if any(j.job_id==ID for j in jobs):raise ValueError('Already installed')
    if sum(j.job_id=='dfm13-xl-step_3250000-train' for j in jobs)!=1:raise ValueError('Missing3250 continuation')
    template=next(j for j in jobs if j.job_id==SYNC_ID)
    averages=[j for j in jobs if boundary(j)==3200000 and j.action==Action.AVERAGE]
    if not averages or any(j.status!=JobStatus.PENDING or j.attempt for j in averages):
        raise ValueError('3200 averages must all be unattempted pending')
    writers=EVALS|{Action.MERGE_STANDARD,Action.MERGE_DFM,Action.MERGE_IFEVAL,
        Action.REPORT,Action.RELOG_PROJECT_AVERAGES,Action.AVERAGE_LONG_CONTEXT,Action.TEARDOWN_EVAL}
    downstream={j.job_id for j in averages}
    while True:
        expanded=downstream|{j.job_id for j in jobs if set(j.deps)&downstream}
        if expanded==downstream:break
        downstream=expanded
    deps=tuple(j.job_id for j in jobs if boundary(j)==3200000 and j.action in writers
               and j.job_id not in downstream
               and j.status!=JobStatus.SKIPPED and 'valeu' not in j.name.lower())
    row=template.with_updates(job_id=ID,name='historical-available-average-sync',deps=deps,
        status=JobStatus.PENDING,attempt=0,max_retries=0,log_dir=str(PLAN/'history-available-sync'),
        metadata={'python_bin':str(Path(__file__).resolve()),'payload':str(path.resolve()),
            'payload_file_sha256':None if prepare_at_execution else file_hash(path),
            'payload_sha256':None if prepare_at_execution else payload['payload_sha256'],
            'prepare_at_execution':prepare_at_execution,
            'source_pins':{**{p:file_hash(p) for p in payload.get('pins',{})},
                **{str(p):file_hash(p) for p in (IMPLEMENTATION,Path(__file__).resolve())}}})
    out=[]
    for j in jobs:
        if j in averages:
            j=j.with_updates(deps=tuple(dict.fromkeys((*j.deps,ID))))
        if j.job_id=='dfm13-xl-step_3250000-train':
            if j.status!=JobStatus.PENDING or j.attempt:raise ValueError('3250 training already attempted')
            j=j.with_updates(deps=tuple(dict.fromkeys((*j.deps,ID))))
        out.append(j)
    out.append(row);check_graph(out);return out


def install(path,prepare_at_execution=False):
    payload=load(path) if prepare_at_execution else validate_payload(path)
    if payload['run_path']!=RUN:raise ValueError('Wrong XL input registry')
    target=CONTROL/'xl-after3200.json' if prepare_at_execution else path
    CONTROL.mkdir(parents=True,exist_ok=True)
    with PlanLock(PLAN):
        before=read_plan(PLAN/'plan.tsv');after=build(before,target,payload,prepare_at_execution)
        backup=CONTROL/'plan-before-install.tsv'
        if backup.exists():raise ValueError('Prior installation evidence')
        write_plan(backup,before);write_plan(PLAN/'plan.tsv',after)
        write_json(CONTROL/'installed.json',dict(job_id=ID,payload=str(target),prepare_at_execution=prepare_at_execution,
            deps=list(after[-1].deps),run_path=RUN,summary_ordering='backfill_then_all3200_averages',
            source_pins=after[-1].metadata['source_pins'],no_launch=True))


def summary_subset(summary,payload):
    keys={k for point in payload['points'] for k in point['row']}
    prefixes={'avg_population','headline_avg_dala_v2','headline_avg_talemaader_v2','suite_avg_dala_v2','suite_avg_talemaader_v2'}
    if any(k.split('/')[0] not in prefixes for k in keys):raise ValueError('Unexpected historical namespace')
    return {k:summary[k] for k in keys if k in summary}


def dispatch():
    with PlanLock(PLAN):
        jobs=read_plan(PLAN/'plan.tsv');by={j.job_id:j for j in jobs};row=by[ID]
        if row.status!=JobStatus.RUNNING or any(by[d].status!=JobStatus.DONE for d in row.deps):
            raise ValueError('Exclusive3200 writer window not reached')
        if any(j.action==Action.TRAIN_UNTIL_STEP and j.status==JobStatus.RUNNING for j in jobs):
            raise ValueError('Training active')
        for p,h in row.metadata['source_pins'].items():
            if file_hash(p)!=h:raise ValueError('Sync implementation drift')
    path=Path(row.metadata['payload'])
    if row.metadata.get('prepare_at_execution'):
        if not path.exists():
            subprocess.run(['/home/ucloud/miniforge3/envs/hrm/bin/python','-m','scripts.backfill_available_eval_averages',
                'prepare','--run','xl','--output',str(path)],cwd=ROOT,check=True)
    elif file_hash(path)!=row.metadata['payload_file_sha256']:raise ValueError('Payload file drift')
    payload=validate_payload(path)
    if row.metadata.get('prepare_at_execution'):
        if payload['points'][-1]['point']['train_step']!=3200000:
            raise ValueError('Prepared final point is not completed3200')
        completed=next(j for j in jobs if j.action==Action.AVERAGE and j.metadata.get('eval_step')==3200000)
        if payload['points'][-1]['point']['epoch']!=completed.metadata['eval_epoch']:
            raise ValueError('Prepared3200 epoch mismatch')
    permit=CONTROL/'exclusive-permit.json'
    write_json(permit,dict(run_path=RUN,payload_sha256=payload['payload_sha256'],exclusive_writer_confirmed=True,
        scheduler_job=ID,all3200_raw_writers_done=True,averages_follow=True))
    subprocess.run(['/home/ucloud/miniforge3/envs/hrm/bin/python','-m','scripts.backfill_available_eval_averages','sync',
                    '--payload',str(path),'--permit',str(permit)],cwd=ROOT,check=True)

if __name__=='__main__':
    if sys.argv[1:]==['scripts/generate_dfm5_l_eval_comparison_report.py']:dispatch()
    else:
        p=argparse.ArgumentParser();p.add_argument('--payload',type=Path,required=True)
        p.add_argument('--prepare-at-execution',action='store_true');a=p.parse_args();install(a.payload,a.prepare_at_execution)
