"""User-authorized Gemma eval interlude; keep the active trainer in host memory."""
import json,os,re,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from training_suspend.protocol import read_json,atomic_write,submit,matches,validate_process
from eval_scheduler.store import SQLiteJobStore,_validate_graph
from eval_scheduler.model import write_plan,JobStatus
from eval_scheduler.preflight import check_job
PYTHON='/home/ucloud/miniforge3/envs/hrm/bin/python'
CUDA='/home/ucloud/miniforge3/envs/cuda-checkpoint-test/bin/cuda-checkpoint'
PLAN=ROOT/'logs/scheduler/gemma_semantic_memory_interlude_20261112'
DB=Path('/var/tmp/gemma-semantic-memory-interlude-20261112/jobs.sqlite')
MAIN=SQLiteJobStore('/var/tmp/dfm11-architecture-comparison/jobs.sqlite')
HOLD='User-authorized Gemma semantic evaluation interlude; automatic memory resume\n'
MODELS=['gemma4-e2b','gemma4-e4b','gemma4-26b-a4b','gemma4-31b']
def note(stage,**kwargs):
    value={'stage':stage,'time':time.time(),**kwargs}
    atomic_write(PLAN/'status.json',value);print(json.dumps(value),flush=True)
def wait_for(fn,seconds=900):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        result=fn()
        if result:return result
        time.sleep(2)
    raise TimeoutError('Timed out waiting for '+fn.__name__)
def main():
    PLAN.mkdir(parents=True,exist_ok=True)
    jobs=MAIN.load_jobs();train=next(j for j in jobs if j.job_id=='transformer48-step_300000-train');assert train.status=='running'
    control=Path(train.metadata['cooperative_training']['control_root'])
    active=Path(read_json(control/'active.json')['control_dir'])
    launcher=read_json(control/'launcher.json')['identity'];validate_process(launcher)
    assert not (control/'hold').exists(),'Unexpected existing hold'
    assert not DB.exists(),'Interlude already prepared'
    added=[];previous=[]
    for model in MODELS:
        group=[j for j in jobs if j.job_id.startswith('dsrb-ext-'+model+'-')];assert len(group)==8 and all(j.status=='failed' for j in group)
        ids=[j.job_id for j in group if j.action=='eval_dfm']
        for j in group:
            md={**j.metadata,'plan_dir':str(PLAN)}
            if j.action=='eval_dfm':
                md.update(vllm_python=str(ROOT/'scripts/gemma_cuda_python'),vllm_attention_backend='TRITON_ATTN',cuda_home='/home/ucloud/miniforge3/envs/audit',vllm_extra_args='--attention-backend TRITON_ATTN --language-model-only --default-chat-template-kwargs \'{"enable_thinking":false}\'')
            added.append(j.with_updates(metadata=md,deps=tuple(ids if j.action=='average' else previous),status=JobStatus.PENDING,attempt=0))
        previous=ids
    _validate_graph(added)
    for j in added:assert not check_job(j,ROOT),(j.job_id,check_job(j,ROOT))
    assert Path('/home/ucloud/miniforge3/envs/audit/bin/nvcc').is_file()
    subprocess.run(['/home/ucloud/miniforge3/envs/audit/bin/nvcc','--version'],check=True)
    import wandb
    assert callable(wandb.init)
    store=SQLiteJobStore(DB);store.import_jobs(added);write_plan(PLAN/'plan.tsv',added)
    atomic_write(PLAN/'database.json',{'database':str(DB)})
    atomic_write(PLAN/'original-rows.json',[j.to_row() for j in jobs if j.job_id in {x.job_id for x in added}])
    # Hold BEFORE requesting the handshake; the main runner must not release it.
    with (control/'training.log').open('rb') as f:
        f.seek(max(0,(control/'training.log').stat().st_size-20000));tail=f.read().decode(errors='replace')
    steps=[int(x) for x in re.findall(r'step=(\d+)',tail)];assert steps
    target=max(steps)+20;assert target<300000
    ready=None;offloaded=False
    atomic_write(control/'hold',HOLD)
    try:
        submit(active,[target]);note('suspension_requested',requested_step=target,launcher=launcher)
        def ready_now():
            p=active/'suspend_ready.json'
            if p.exists():
                r=read_json(p)
                if r['step']>=target:return r
        ready=wait_for(ready_now)
        subprocess.run([PYTHON,'-m','training_suspend.controller','--cuda-checkpoint',CUDA,'offload',str(active),'--lease-seconds','86400'],check=True,timeout=900)
        gen=active/f"generation_{ready['generation']:06d}"
        assert matches(read_json(gen/'offloaded.json'),ready);offloaded=True
        atomic_write(PLAN/'suspension.json',ready);note('offloaded',step=ready['step'],launcher=launcher)
        env={**os.environ,'TMPDIR':'/dev/shm/hrm-b-recovery','PATH':'/home/ucloud/miniforge3/envs/hrm/bin:'+os.environ['PATH']}
        cmd=[PYTHON,'-m','eval_scheduler','run','--plan-dir',str(PLAN),'--backend','sqlite','--gpus','0,1,2,3,4,5,6,7','--persistent-vllm','--cpu-cores','256','--reserve-cores','8','--max-clients','128','--server-concurrency','1024']
        with (PLAN/'runner.log').open('ab') as log:
            child=subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            note('evaluating',scheduler_pid=child.pid,step=ready['step'])
            code=child.wait()
        finished=store.load_jobs();assert all(j.status in ('done','failed','skipped') for j in finished),'Unexpected pending eval work'
        MAIN.update_jobs({j.job_id:{'status':j.status,'attempt':j.attempt} for j in finished})
        note('evaluations_terminal',exit_code=code,statuses={j.job_id:str(j.status) for j in finished})
    finally:
        # Restore only after the eval runner has exited and GPU workloads drained.
        from training_suspend.controller import CudaBackend
        backend=CudaBackend(CUDA)
        if 'child' in locals() and child.poll() is None:
            note('recovery_required',reason='Eval scheduler remains alive; training hold preserved')
            raise RuntimeError('Cannot release hold while eval scheduler is live')
        owned={r['pid'] for r in ready['ranks']} if ready else set()
        if offloaded and any(pid not in owned or mib>64 for (pid,gpu),mib in backend.memory().items()):
            note('recovery_required',reason='GPU processes remain; training hold preserved')
            raise RuntimeError('Cannot restore over remaining GPU allocations')
        validate_process(launcher)
        assert read_json(control/'active.json')['control_dir']==str(active)
        assert (control/'hold').read_text()==HOLD
        (control/'hold').unlink()
        if ready:
            gen=active/f"generation_{ready['generation']:06d}"
            atomic_write(gen/'restore.request',ready)
            def resumed_now():
                p=active/'resumed.json'
                return p.exists() and matches(read_json(p),ready)
            wait_for(resumed_now,1200)
            validate_process(launcher)
            for rank in ready['ranks']:validate_process(rank)
            assert not (gen/'disk_fallback.json').exists()
            note('resumed_from_memory',step=ready['step'],launcher=launcher,ranks=ready['ranks'])
if __name__=='__main__':main()
