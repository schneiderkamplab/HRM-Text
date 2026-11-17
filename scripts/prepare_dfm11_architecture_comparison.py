"""Prepare, never launch, the full-backprop B / Transformer48 alternating plan."""
import hashlib,json,os,sqlite3,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from eval_scheduler.model import Job,JobStatus,Action,write_plan
from eval_scheduler.store import SQLiteJobStore
from eval_scheduler.preflight import check_job
from prepare_transformer48_eval_plan import replace
from run_transformer48_dfm11 import overrides
PLAN=ROOT/'logs/scheduler/dfm11_architecture_comparison_20261110'
DB=Path('/var/tmp/dfm11-architecture-comparison/jobs.sqlite')
OUT=ROOT/'logs/training/B_dfm11_causal_fullbp_20261110'
RUN='B-dfm11-causal-fullbp-alltokens-epoch1'
CKPT=ROOT/'checkpoints/hrm'/RUN
PYTHON='/home/ucloud/miniforge3/envs/hrm/bin/python'
TCONTROL=ROOT/'logs/training/transformer48_dfm11_causal_20261109/control-shared-1'
BCONTROL=OUT/'control'


def b_overrides():
    values=[x for x in overrides() if not x.startswith(('arch/net@','arch/size@','checkpoint_path=','run_name=','wandb_run_id=','wandb_resume=','suspend_after_steps='))]
    return values+['arch/net@arch=hrm','arch/size@arch=B','arch.H_cycles=2','arch.L_cycles=3',
      '+arch.bp_min_steps=8','arch.bp_max_steps=8','arch.bp_warmup_ratio=0',
      f'checkpoint_path={CKPT}',f'run_name={RUN}',f'wandb_run_id={RUN}','wandb_resume=allow',
      'suspend_after_steps=[50000,100000,150000,200000,250000,300000,350000]']


def main():
    assert not DB.exists(),'Refusing to overwrite prepared comparison DB'
    CKPT.mkdir(parents=True,exist_ok=True)
    assert not any(CKPT.iterdir()),'B checkpoint directory is not empty'
    OUT.mkdir(parents=True,exist_ok=True);PLAN.mkdir(parents=True,exist_ok=True);DB.parent.mkdir(parents=True,exist_ok=True)
    env={**os.environ,'TMPDIR':'/dev/shm/hrm-b-recovery','PATH':str(Path(PYTHON).parent)+':'+os.environ['PATH']}
    resolved=subprocess.check_output([PYTHON,'pretrain.py',*b_overrides(),'--cfg','job','--resolve'],cwd=ROOT,env=env)
    (OUT/'resolved-config.yaml').write_bytes(resolved)
    settings=json.loads((TCONTROL.parent/'shared-gpu-settings.json').read_text())
    for k in ['shim_library','nccl_library','redis_server','cuda_checkpoint']:assert Path(settings[k]).is_file(),k
    (OUT/'launcher-settings.json').write_text(json.dumps(settings,indent=2))
    c=sqlite3.connect('file:/var/tmp/dfm-transformer48-evals/jobs.sqlite?mode=ro',uri=True)
    current={jid:Job.from_row(json.loads(d)).with_updates(log_dir=l) for jid,d,l in c.execute('select job_id,definition,log_dir from jobs')}
    archived=json.loads((TCONTROL.parent.parent.parent/'scheduler/transformer48_dfm11_causal_epoch1_20261109/future-rows-before-alternation.json').read_text())
    for row in archived:current[row[0]]=Job.from_row(json.loads(row[2])).with_updates(log_dir=row[7])
    all_jobs=[];previous=[];prior_model=None;prior_step=None;order=[]
    stages=[('B',s) for s in (50000,100000,150000)]
    for step in (200000,250000,300000,350000,393732):stages.extend([('T',step),('B',step)])
    for model,step in stages:
        tag='epoch_1' if step==393732 else f'step_{step}'
        oldprefix=f'transformer48-{tag}';newprefix=f'bfull-dfm11-{tag}' if model=='B' else oldprefix
        source_tag=tag if model=='T' else 'step_50000'
        sources=[j for jid,j in current.items() if jid.startswith(f'transformer48-{source_tag}-')]
        assert len(sources)==2204,(model,step,len(sources))
        pairs=[(f'transformer48-{source_tag}',newprefix)]
        if model=='B':
            pairs += [('transformer48-dfm11-causal-alltokens-epoch1',RUN),
                      ('checkpoints/transformer/'+RUN,'checkpoints/hrm/'+RUN),
                      ('transformer48_dfm11_causal','B_dfm11_causal_fullbp'),
                      ('transformer48-dfm11','B-dfm11-fullbp'),('step_50000',tag)]
        block=[]
        for j in sources:
            m=replace(j.metadata,pairs);jid=replace(j.job_id,pairs)
            m.update(plan_dir=str(PLAN),log_wandb=True,vllm_gpu_memory_utilization=.95,eval_step=step,eval_epoch=1. if tag=='epoch_1' else step/393732,xl_boundary=step)
            if m.get('judge_server_model'):
                m['vllm_gpu_memory_utilization']=.85  # Reserve 16 GiB for co-located judge.
            log=replace(j.log_dir,pairs)
            if j.action==Action.TRAIN_UNTIL_STEP:
                coop=m['cooperative_training'];coop['scheduled_disk_resume']=True
                m['stop_after_step']=step;m['ckpt_tag']=f'step_{step}'
                if model=='B':
                    coop.update(command=[str(Path(PYTHON).parent/'torchrun'),'--standalone','--nproc_per_node=8','pretrain.py',*b_overrides()],control_root=str(BCONTROL),launcher_settings=str(OUT/'launcher-settings.json'))
                    m['ckpt_path']=str(CKPT)
                if step==50000:
                    m.pop('resume_from_tag',None);m.pop('resume_ckpt_path',None)
                else:
                    m['resume_from_tag']=f'step_{350000 if tag=="epoch_1" else step-50000}';m['resume_ckpt_path']=m['ckpt_path']
                coop['final_boundary']=tag=='epoch_1'
                if tag=='epoch_1':
                    m['completion_checkpoint_tag']='epoch_1'
                    coop['finalize_command']=[PYTHON,str(ROOT/'scripts/finalize_transformer48_epoch.py'),str(DB),m['ckpt_path']]
                else:coop.pop('finalize_command',None)
                if prior_model is not None and prior_model!=model and prior_step!=393732:
                    coop['disk_handoff_from']={'control_root':str(BCONTROL if prior_model=='B' else TCONTROL),'step':prior_step}
                deps=tuple(previous);log=str(PLAN/'runs'/jid)
            else:
                m.update(ckpt_tag=tag,checkpoint_tag=tag)
                if model=='B':m.pop('transformer_single_pass',None);m['recurrent_causal']=True
                if tag=='epoch_1':m['transformer_final_epoch']=True
                else:m.pop('transformer_final_epoch',None)
                deps=tuple(replace(d,pairs) for d in j.deps if d.startswith(f'transformer48-{source_tag}-'))
                if not deps:deps=(newprefix+'-train',)
            block.append(j.with_updates(job_id=jid,metadata=m,deps=deps,status=JobStatus.PENDING,attempt=0,log_dir=log))
        inference_ids=tuple(j.job_id for j in block if j.action.value.startswith('eval_'))
        block=[j.with_updates(deps=inference_ids,deps_mode='terminal') if j.action==Action.TEARDOWN_EVAL else j for j in block]
        all_jobs.extend(block)
        previous=[j.job_id for j in block if j.action.value.startswith('eval_') or j.action in (Action.EXPORT_HF,Action.WAIT_CHECKPOINT)]
        order.append({'model':model,'boundary':tag,'disk_switch':prior_model is not None and prior_model!=model})
        prior_model,prior_step=model,step
    failures={j.job_id:e for j in all_jobs if (e:=check_job(j,ROOT))}
    (PLAN/'preflight.json').write_text(json.dumps({'rows':len(all_jobs),'failures':failures},indent=2))
    assert not failures,f'{len(failures)} rows failed preflight; see preflight.json'
    write_plan(PLAN/'plan.tsv',all_jobs);SQLiteJobStore(DB).import_jobs(all_jobs,preserve_runtime=False)
    (PLAN/'database.json').write_text(json.dumps({'database':str(DB)}))
    manifest={'status':'prepared_not_launched','order':order,'B_run':RUN,'database':str(DB),'config_sha256':hashlib.sha256(resolved).hexdigest(),'initial_prerequisite':'Transformer48 150K stop receipt and dead launcher','full_backward_calls':8,'layer_applications':48}
    (PLAN/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
