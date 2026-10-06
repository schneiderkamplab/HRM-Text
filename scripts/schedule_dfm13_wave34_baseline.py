"""Prepare/install coverage only: train3200 -> baseline3150 -> eval3200. No launch."""
import argparse
import copy
from collections import deque
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'eval_scheduler'))
from dfm12.io import file_hash,load,write_json
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import Action,Job,JobStatus,read_plan,write_plan
from scripts.schedule_identity_final_ema_full import canonical_log_dir

PLAN=ROOT/'logs/scheduler/dfm12_XL_epoch11_noidentity'
CONTROL=ROOT/'data/dfm13/wave34-eval-baseline-20261006'
RUN='dfm8-xl-from-dfm6-dfm7-epoch5-clean-full'
MARK='wave34_baseline_extension'
SYNC_ID='dfm13-xl-wave34-talemaader-v2-sync'
SYNC_SCRIPT=ROOT/'scripts/rejudge_talemaader_v2.py'
SYNC_BRIDGE=ROOT/'scripts/talemaader_v2_scheduler_sync'
EVALS={Action.EVAL_DFM,Action.EVAL_DFM_IFEVAL,Action.EVAL_STANDARD,
       Action.EVAL_EUROEVAL,Action.EVAL_EUROEVAL_BATCHED_IFEVAL}


def boundary(job):
    return int(job.metadata.get('xl_boundary',job.metadata.get('eval_step',0)))


def prepare_coverage(completion_path,control=CONTROL):
    import yaml
    complete=load(completion_path)
    if complete.get('complete') is not True:raise ValueError('Coverage incomplete')
    pins=dict(complete['files'])
    for key in ('task_preflight','euro_access'):
        item=complete[key];pins[item['path']]=item['sha256']
    for path,sha in pins.items():
        if file_hash(path)!=sha:raise ValueError('Upstream coverage drift: '+path)
    preflight=load(complete['task_preflight']['path'])
    if preflight.get('valid') is not True:raise ValueError('Task preflight failed')
    pins[str(Path(completion_path).resolve())]=file_hash(completion_path)
    config=ROOT/'config'
    euro=yaml.safe_load((config/'euroeval_dfm13_multilingual_20261006.yaml').read_text())
    tasks=[{**t,'languages':t['euroeval_result_languages']} for t in euro['entries']
           if t['status'] in euro['execution']['run_statuses']]
    if len(tasks)!=complete['euro_jobs'] or any(t.get('remote_access_status')!='accessible' for t in tasks):
        raise ValueError('EuroEval access/count mismatch')
    dfm=load(config/'dfm13_dala_heldout_registry_20261006.json')
    if len(dfm)!=complete['dfm_tasks']:raise ValueError('DFM count mismatch')
    registry=dict(dfm=dfm,euroeval=tasks,euroeval_bin=euro['execution']['euroeval_bin'],
        headline_manifest=str(config/'multilingual_headline_populations_dfm13_20261006.json'))
    control.mkdir(parents=True,exist_ok=True)
    rp=control/'coverage-registry.json'; receipt=control/'coverage-ready.json'
    write_json(rp,registry)
    write_json(receipt,dict(status='passed',coverage_ready=True,registry_sha256=file_hash(rp),pins=pins))
    return rp,receipt


def ready(registry_path,receipt_path):
    registry=load(registry_path); receipt=load(receipt_path)
    if receipt.get('status')!='passed' or receipt.get('coverage_ready') is not True:
        raise ValueError('Tesla coverage not ready')
    if receipt.get('registry_sha256')!=file_hash(registry_path):
        raise ValueError('Coverage registry drift')
    pins=receipt.get('pins',{})
    required=[registry['headline_manifest'],*[t['config'] for t in registry['dfm']]]
    if not pins or any(str(Path(p).resolve()) not in pins for p in required):
        raise ValueError('Coverage input pins incomplete')
    for path,sha in pins.items():
        if file_hash(path)!=sha:raise ValueError('Coverage input drift: '+path)
    if not registry['dfm'] and not registry['euroeval']:raise ValueError('Empty coverage')
    from scripts.headline_population_registry import load_registry
    load_registry(Path(registry['headline_manifest']))
    legacy=set()
    for name in ('multilingual_headline_populations_20260930.json','multilingual_headline_populations_semantic_v1.json'):
        legacy.update(p['id'] for p in load(ROOT/'config'/name)['populations'])
    if any(p['id'] in legacy for p in load(registry['headline_manifest'])['populations']):
        raise ValueError('New averages must not overwrite existing population IDs')
    return registry


def check_graph(jobs):
    ids={j.job_id for j in jobs}
    if len(ids)!=len(jobs):raise ValueError('Duplicate job ID')
    dependents={i:[] for i in ids};degree={}
    for j in jobs:
        if not set(j.deps)<=ids:raise ValueError('Dangling dependency')
        degree[j.job_id]=len(set(j.deps))
        for d in set(j.deps):dependents[d].append(j.job_id)
    queue=deque(k for k,v in degree.items() if not v);n=0
    while queue:
        key=queue.popleft();n+=1
        for child in dependents[key]:
            degree[child]-=1
            if not degree[child]:queue.append(child)
    if n!=len(ids):raise ValueError('Dependency cycle')


def task_template(block,task,action):
    if action==Action.EVAL_DFM:
        family='gec_dala' if task['suite'].startswith('gec_dala') else 'dala'
        matches=[j for j in block if j.action==action and
                 (j.metadata.get('dfm_suite',j.name)==family or
                  j.metadata.get('dfm_suite',j.name).startswith(family+'_'))]
    else:
        category=task.get('category')
        matches=[j for j in block if j.action==action and category and
                 j.metadata.get('euroeval_category')==category]
    if not matches:raise ValueError('No matching calibrated task template: '+str(task))
    return sorted(matches,key=lambda j:(not bool(j.metadata.get('eval_capacity_calibration')),
        j.metadata.get('language')!=task.get('language'),j.job_id))[0]


def build(jobs,registry,plan=PLAN):
    if any(j.metadata.get(MARK) for j in jobs):raise ValueError('Extension already installed')
    if any('valeu' in t.get('name',t.get('dataset','')).lower()
           for t in [*registry['dfm'],*registry['euroeval']]):raise ValueError('VALEU prohibited')
    active=[j for j in jobs if j.action==Action.TRAIN_UNTIL_STEP and boundary(j)==3200000]
    if len(active)!=1 or active[0].status!=JobStatus.RUNNING:
        raise ValueError('Expected currently running train3200; refuse late/raced installation')
    training=active[0]; steps=sorted({boundary(j) for j in jobs if j.action==Action.TRAIN_UNTIL_STEP and boundary(j)>=3200000})
    result=list(jobs);gates={};new_gpu={}
    additions=[Job(job_id=SYNC_ID,action=Action.REPORT,family='report',name='talemaader-v2-sync',
        deps=(training.job_id,),deps_mode='success',max_retries=0,gpu_count=0,
        execution_scope='control',required_capability='control',
        log_dir=str(plan/'wave34'/'talemaader-v2-sync'),metadata={MARK:True,
            'report_kind':'talemaader_v2_sync','wandb_run_id':RUN,'wandb_project':'DFM5',
            'python_bin':str(SYNC_BRIDGE),'source_pin_path':str(SYNC_BRIDGE),
            'source_pin_sha256':file_hash(SYNC_BRIDGE),
            'command':['/home/ucloud/miniforge3/envs/hrm/bin/python',str(SYNC_SCRIPT),
                'sync','--wait','--output',str(ROOT/'logs/rejudge_talemaader_v2')],
            'workdir':str(ROOT)})]
    for step in [3150000,*steps]:
        block=[j for j in jobs if boundary(j)==step and j.action!=Action.TRAIN_UNTIL_STEP]
        lifecycle={Action.TERMINAL_BARRIER,Action.TEARDOWN_EVAL}
        if step>=3200000 and any(j.attempt or (j.status not in (JobStatus.PENDING,JobStatus.SKIPPED)
                and not (j.action in lifecycle and j.status==JobStatus.DONE)) for j in block):
            raise ValueError('Future evaluation already attempted')
        def one(action):
            values=[j for j in block if j.action==action]
            if len(values)!=1:raise ValueError('Ambiguous lifecycle '+str(action))
            return values[0]
        export=one(Action.EXPORT_HF)
        avg=next(j for j in block if j.action==Action.AVERAGE and j.metadata.get('multilingual_manifest'))
        tag=export.metadata['ckpt_tag'];prefix='dfm13-xl-wave34-'+tag+'-'
        meta=copy.deepcopy(export.metadata)
        if meta.get('wandb_run_id')!=RUN or meta.get('wandb_project')!='DFM5':raise ValueError('Wrong W&B identity')
        if meta.get('fix_mistral_regex') is not False:raise ValueError('Wrong tokenizer contract')
        for key in list(meta):
            if key.startswith(('judge_','managed_judge')):meta.pop(key)
        meta.update({MARK:True,'multilingual_manifest':registry['headline_manifest'],
            'dfm_log_root':str(plan/'wave34'/tag/'dfm'),
            'euroeval_log_root':str(plan/'wave34'/tag/'euroeval'),
            'population_require_complete':True})
        deps=(export.job_id,SYNC_ID) if step==3150000 else (export.job_id,)
        if step==3150000 and export.status!=JobStatus.DONE:raise ValueError('Original3150 export not done')
        gpu=[];writers=[]
        existing_names={j.name for j in block if j.action in EVALS}
        def clone(template,suffix,name,metadata,dependencies,**kw):
            j=template.with_updates(job_id=prefix+suffix,name=name,metadata=metadata,deps=tuple(dependencies),
                deps_mode='success',status=JobStatus.PENDING,attempt=0,**kw)
            return j.with_updates(log_dir=str(canonical_log_dir(j)))
        def task_metadata(template):
            inherited=copy.deepcopy(template.metadata)
            for key in list(inherited):
                if key.startswith(('judge_','managed_judge')):inherited.pop(key)
            for key in (MARK,'multilingual_manifest','dfm_log_root','euroeval_log_root','population_require_complete'):
                inherited[key]=meta[key]
            inherited['template_job_id']=template.job_id
            inherited['capacity_inheritance']='family/category template; new task not independently calibrated'
            return inherited
        for task in registry['dfm']:
            name=task['name']
            if name in existing_names:raise ValueError('New task duplicates existing coverage: '+name)
            shards=int(task.get('shards',4))
            if not 1<=shards<=64:raise ValueError('Invalid shard count')
            dfm=task_template(block,task,Action.EVAL_DFM)
            merge=next(j for j in block if j.action==Action.MERGE_DFM and j.name==dfm.name)
            taskmeta={**task_metadata(dfm),'dfm_suite':task['suite'],'dfm_single_tasks_config':task['config'],
                'language':task['language'],'dfm_max_gen_toks':task.get('max_tokens',512)}
            ids=[]
            for s in range(shards):
                j=clone(dfm,name+f'-{s}',name,taskmeta,deps,shard=s,shards=shards)
                additions.append(j);ids.append(j.job_id);gpu.append(j.job_id)
            j=clone(merge,name+'-merge',name,{**taskmeta,'shards':shards},ids,shard=None,shards=None)
            additions.append(j);writers.append(j.job_id)
        for task in registry['euroeval']:
            name=task['dataset']
            if name in existing_names:raise ValueError('New task duplicates existing coverage: '+name)
            euro=task_template(block,task,Action.EVAL_EUROEVAL)
            taskmeta={**task_metadata(euro),'euroeval_languages':task.get('languages',[task['language']]),
                'euroeval_context_policy':'native_head_tail_v1','euroeval_category':task.get('category','')}
            if registry.get('euroeval_bin'):taskmeta['euroeval_bin']=registry['euroeval_bin']
            j=clone(euro,'euro-'+name,name,taskmeta,deps,shard=None,shards=None)
            additions.append(j);gpu.append(j.job_id);writers.append(j.job_id)
        avgmeta={**meta}
        for suite,key in [('dfm','dfm_log_root'),('euroeval','euroeval_log_root'),('standard','log_root')]:
            roots=list(avg.metadata.get('additional_'+suite+'_roots',[]))
            roots.extend((str(j.metadata[key])+('/'+tag if suite=='euroeval' else ''))
                         for j in block if key in j.metadata and j.action in EVALS)
            avgmeta['additional_'+suite+'_roots']=list(dict.fromkeys(roots))
        average=clone(avg,'average','wave34-headline',avgmeta,
                      [*writers,*([SYNC_ID] if step==3150000 else []),
                       *[j.job_id for j in block if j.action==Action.AVERAGE]])
        average=average.with_updates(log_dir=str(plan/'wave34'/tag/'average'))
        additions.append(average);gates[step]=[average.job_id];new_gpu[step]=gpu
        lifecycle_deps=gpu if step==3150000 else [*gpu,*[j.job_id for j in block if j.action in EVALS and j.status!=JobStatus.SKIPPED]]
        barrier=clone(one(Action.TERMINAL_BARRIER),'barrier','wave34-barrier',meta,lifecycle_deps)
        barrier=barrier.with_updates(log_dir=str(plan/'wave34'/tag/'barrier'),deps_mode='terminal')
        teardown=clone(one(Action.TEARDOWN_EVAL),'teardown','wave34-teardown',meta,[barrier.job_id])
        teardown=teardown.with_updates(log_dir=str(plan/'wave34'/tag/'teardown'))
        additions.extend([barrier,teardown]);gates[step].append(teardown.job_id)
    updated=[]
    for j in result:
        step=boundary(j);extra=[]
        if step==3200000 and j.action==Action.WAIT_CHECKPOINT:extra+=gates[3150000]
        if step in steps and j.action==Action.TERMINAL_BARRIER and j.status==JobStatus.PENDING:
            if j.deps_mode!='terminal':raise ValueError('Existing cleanup barrier must be terminal')
            extra+=new_gpu[step]
        if j.action==Action.TRAIN_UNTIL_STEP and step>3200000:
            extra+=gates[max(s for s in steps if s<step)]
        if extra:
            if j.status!=JobStatus.PENDING or j.attempt:raise ValueError('Cannot change attempted job')
            j=j.with_updates(deps=tuple(dict.fromkeys((*j.deps,*extra))))
        updated.append(j)
    result=updated+additions;check_graph(result)
    assert next(j for j in result if j.job_id==training.job_id)==training
    return result


def execute(registry_path,receipt_path,plan=PLAN,control=CONTROL,install=False):
    registry=ready(registry_path,receipt_path)
    control.mkdir(parents=True,exist_ok=True)
    with PlanLock(plan):
        # Reload under lock; never replace live statuses from an earlier preview.
        ready(registry_path,receipt_path)
        before=read_plan(plan/'plan.tsv');after=build(before,registry,plan)
        old={j.job_id:j for j in before};new={j.job_id:j for j in after}
        report=dict(installed=install,coverage_registry=str(registry_path),coverage_sha256=file_hash(registry_path),
            readiness_receipt=str(receipt_path),readiness_sha256=file_hash(receipt_path),
            new_jobs=[j.job_id for j in after if j.job_id not in old],
            changed_dependencies={i:list(new[i].deps) for i in old if old[i]!=new[i]},
            original_plan_sha256=file_hash(plan/'plan.tsv'),
            training3200_preserved=True,baseline_runs_after_train3200=True,
            existing_run_id=RUN,no_gpu_launched=True,time=time.time())
        if install:
            import inspect
            from eval_scheduler import runtime
            # The already-running scheduler honors python_bin, not command.
            import os
            if not SYNC_SCRIPT.exists() or not os.access(SYNC_BRIDGE,os.X_OK) or 'python_bin(job)' not in inspect.getsource(runtime.run_report):
                raise ValueError('Talemaader sync script/scoped REPORT dispatcher not ready')
            if not (control/'preview.json').exists():raise ValueError('Prepare and report before installation')
            preview=load(control/'preview.json')
            if preview['coverage_sha256']!=report['coverage_sha256'] or preview['readiness_sha256']!=report['readiness_sha256']:
                raise ValueError('Prepared coverage changed')
            backup=control/'plan-before-install.tsv'
            if backup.exists():raise ValueError('Prior installation/backup exists; inspect manually')
            shutil.copy2(plan/'plan.tsv',backup)
            write_json(control/'install-intent.json',report)
            write_plan(plan/'plan.tsv',after)
        else:write_plan(control/'plan-preview.tsv',after)
        report['result_plan_sha256']=file_hash(plan/'plan.tsv' if install else control/'plan-preview.tsv')
        write_json(control/('installed.json' if install else 'preview.json'),report)
        return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['prepare','install'])
    p.add_argument('--registry',type=Path,required=True);p.add_argument('--readiness',type=Path,required=True)
    p.add_argument('--plan-dir',type=Path,default=PLAN);p.add_argument('--control',type=Path,default=CONTROL)
    a=p.parse_args();r=execute(a.registry,a.readiness,a.plan_dir,a.control,a.mode=='install')
    print('installed' if r['installed'] else 'prepared',len(r['new_jobs']),'new jobs')
