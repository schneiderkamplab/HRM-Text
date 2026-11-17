"""Clone the B evaluation coverage into a cooperative Transformer48 epoch plan."""
import json
from pathlib import Path
import sqlite3
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from eval_scheduler.model import Job,Action,JobStatus,write_plan
from eval_scheduler.store import SQLiteJobStore
from eval_scheduler.preflight import check_job

RUN='transformer48-dfm11-causal-alltokens-epoch1'
PLAN=ROOT/'logs/scheduler/transformer48_dfm11_causal_epoch1_20261109'
DB=Path('/var/tmp/dfm-transformer48-evals/jobs.sqlite')
OUT=ROOT/'logs/training/transformer48_dfm11_causal_20261109'
CKPT=ROOT/'checkpoints/transformer'/RUN
CONTROL=OUT/'control-shared-1'
PYTHON='/home/ucloud/miniforge3/envs/hrm/bin/python'


def replace(value,pairs):
    if isinstance(value,str):
        for a,b in pairs:value=value.replace(a,b)
        return value
    if isinstance(value,list):return [replace(v,pairs) for v in value]
    if isinstance(value,dict):return {k:replace(v,pairs) for k,v in value.items()}
    return value


ARTIFACT_NAMESPACE_PAIRS = [
    ('logs/dfm_evals/dfm13_multilingual/', 'logs/dfm_evals/transformer48_dfm11_causal_multilingual/'),
    ('logs/euroeval/dfm13_multilingual/', 'logs/euroeval/transformer48_dfm11_causal_multilingual/'),
    ('logs/dfm_evals/dfm14_extension/', 'logs/dfm_evals/transformer48_dfm11_causal_extension/'),
    ('logs/dfm_evals/andersen_xl_backfill/', 'logs/dfm_evals/transformer48_dfm11_causal_andersen/'),
    ('logs/scheduler/dfm12_XL_epoch11_noidentity/wave34/', 'logs/scheduler/transformer48_dfm11_causal_wave34/'),
]


def main():
    assert not DB.exists(),'Refusing to overwrite an existing plan'
    PLAN.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect('file:/tmp/dfm15-B-production/jobs.sqlite?mode=ro',uri=True)
    source=[Job.from_row(json.loads(d)) for d, in c.execute("select definition from jobs where job_id like 'b-dfm15-1500000-%' order by position")]
    assert len(source)==2203
    supervisor=json.loads((CONTROL/'supervisor.json').read_text())
    command=[x for x in supervisor['command'] if not x.startswith('suspend_control_dir=')]
    all_jobs=[];previous=[];boundaries=[*range(50000,350001,50000),393732]
    for step in boundaries:
        final=step==393732;tag='epoch_1' if final else f'step_{step}'
        prefix=f'transformer48-{tag}'
        train_id=prefix+'-train'
        coop={'control_root':str(CONTROL),'python':PYTHON,
              'cuda_checkpoint':'/home/ucloud/miniforge3/envs/cuda-checkpoint-test/bin/cuda-checkpoint',
              'launcher_settings':str(OUT/'shared-gpu-settings.json'),'command':command,'final_boundary':final}
        if final:coop['finalize_command']=[PYTHON,str(ROOT/'scripts/finalize_transformer48_epoch.py'),str(DB),str(CKPT)]
        md={'cooperative_training':coop,'stop_after_step':step,'ckpt_tag':f'step_{step}','ckpt_path':str(CKPT),
            'checkpoint_carry_ranks':8,'workdir':str(ROOT),'min_gpu_free_mib':0,
            'wandb_run_id':RUN,'wandb_project':'DFM5'}
        if step > 50000:
            md.update(resume_from_tag=f'step_{350000 if final else step-50000}',resume_ckpt_path=str(CKPT))
        if final:md['completion_checkpoint_tag']='epoch_1'
        train=Job(job_id=train_id,action=Action.TRAIN_UNTIL_STEP,family='training',name=tag,
                  deps=tuple(previous),deps_mode='terminal',gpu_policy='all',max_retries=1,metadata=md,
                  log_dir=str(PLAN/'runs'/train_id))
        all_jobs.append(train)
        pairs=[('b-dfm15-1500000',prefix),('B-dfm15-gemma4-epoch1',RUN),
               ('checkpoints/hrm_v2/'+RUN,'checkpoints/transformer/'+RUN),
               ('B_dfm15_gemma4', 'transformer48_dfm11_causal'),('step_1500000',tag),
               ('hrm-B-dfm15','transformer48-dfm11'),
               ('logs/scheduler/B_dfm15_gemma4_epoch1_20261103',str(PLAN.relative_to(ROOT)))]
        pairs += ARTIFACT_NAMESPACE_PAIRS
        ids={j.job_id:replace(j.job_id,pairs) for j in source}
        block=[]
        for j in source:
            m=replace(j.metadata,pairs)
            m.update(plan_dir=str(PLAN),ckpt_path=str(CKPT),ckpt_tag=tag,checkpoint_tag=tag,
                     eval_step=step,eval_epoch=1.0 if final else step/393732,
                     xl_boundary=step,transformer_single_pass=True,min_gpu_free_mib=10000,
                     vllm_gpu_memory_utilization=.95,wandb_run_id=RUN,wandb_run_name=RUN)
            if m.get('judge_server_model'):
                m['vllm_gpu_memory_utilization']=.85  # Reserve 16 GiB for co-located judge.
            if final:m['transformer_final_epoch']=True
            deps=tuple(ids[d] for d in j.deps if d in ids)
            if j.action==Action.WAIT_CHECKPOINT:deps=(train_id,)
            elif not deps:deps=(train_id,)
            block.append(j.with_updates(job_id=ids[j.job_id],metadata=m,deps=deps,
                         status=JobStatus.PENDING,attempt=0,log_dir=replace(j.log_dir,pairs)))
        inference_ids=tuple(j.job_id for j in block if j.action.value.startswith('eval_'))
        block=[j.with_updates(deps=inference_ids,deps_mode='terminal') if j.action==Action.TEARDOWN_EVAL else j for j in block]
        all_jobs.extend(block)
        # GPU work gates training; CPU publication continues alongside it.
        # Terminal mode preserves continuity if an evaluation fails.
        previous=[j.job_id for j in block if j.action.value.startswith('eval_') or j.action in (Action.EXPORT_HF,Action.WAIT_CHECKPOINT)]
    failures={j.job_id:errors for j in all_jobs if (errors:=check_job(j,ROOT))}
    (PLAN/'preflight.json').write_text(json.dumps({'rows':len(all_jobs),'failures':failures},indent=2))
    if failures:raise RuntimeError(f'{len(failures)} rows failed preflight')
    write_plan(PLAN/'plan.tsv',all_jobs)
    store=SQLiteJobStore(DB);store.import_jobs(all_jobs,preserve_runtime=False)
    (PLAN/'database.json').write_text(json.dumps({'database':str(DB)},indent=2))
    (PLAN/'manifest.json').write_text(json.dumps({'run':RUN,'boundaries':boundaries,'final_checkpoint':'epoch_1',
      'source_plan':'B_dfm15_gemma4_epoch1_20261103','source_step':1500000,'rows':len(all_jobs),
      'database':str(DB),'causal_adapter':'evaluation/vllm_plugins/transformer48_vllm.py'},indent=2))
    print('Prepared',len(all_jobs),'rows:',PLAN)


if __name__=='__main__':main()
