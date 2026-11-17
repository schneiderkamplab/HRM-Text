"""Validated launch recipe for the compute-matched, non-recurrent DFM11 baseline."""
import argparse,fcntl,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'logs/training/transformer48_dfm11_causal_20261109'
RUN='transformer48-dfm11-causal-alltokens-epoch1'
PYTHON='/home/ucloud/miniforge3/envs/hrm/bin/python'

def overrides(smoke=False):
    run=RUN+('-smoke' if smoke else '')
    return ['arch/net@arch=transformer','arch/size@arch=B_compute48','+arch.attn_type=causal',
        'data=dfm11',f'data.path={ROOT}/data/sampled_dfm11','data.target_only=false',
        'epochs=1','training_total_steps=null','stop_after_step=null',
        'global_batch_size=262144','gradient_accumulation_steps=1','seed=0',
        'lr=3e-4','lr_auto=false','lr_min_ratio=1','lr_warmup_steps=5000',
        'lr_decay_start_step=null','lr_decay_end_step=null','lr_piecewise_points=null',
        'lr_rewarm_steps=0','lr_cooldown_checkpoint=null',
        'accelerator_type=sm100','distributed_strategy=fsdp','fsdp_params_precision=fp32',
        'fsdp_wrap_policy=single_unit','fsdp_reshard_after_forward=false',
        'fwd_bwd_dtype=bfloat16','activation_checkpointing=none','compile_train_batch=true',
        'checkpoint_format=sharded','checkpoint_interval=1','checkpoint_step_interval=50000',
        'ephemeral_checkpoint_step_interval=500','suspend_after_steps=[]',
        'memory_log_interval=1' if smoke else 'memory_log_interval=100',
        f'checkpoint_path={ROOT}/checkpoints/transformer/{run}',
        'project_name=DFM5',f'run_name={run}',f'wandb_run_id={run}','wandb_resume=never',
        *(['max_steps=10','log_interval=1'] if smoke else [])]

def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('mode',choices=['config','smoke','train'])
    parser.add_argument('--wait-for-gpus',action='store_true',help='Use the recovery supervisor to wait for all eight GPUs')
    parser.add_argument('--allow-unverified-smoke',action='store_true',help='Explicitly launch despite the canceled smoke test')
    parser.add_argument('--explicit-standalone-override',action='store_true',
                        help='Requires explicit user authorization to bypass the evaluation scheduler')
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);os.chdir(ROOT)
    env={**os.environ,'TMPDIR':'/dev/shm/hrm-b-recovery','PATH':str(Path(PYTHON).parent)+':'+os.environ['PATH'],'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
    if args.mode=='config':
        with (OUT/'resolved-config.yaml').open('w') as f:subprocess.run([PYTHON,'pretrain.py',*overrides(),'--cfg','job','--resolve'],env=env,stdout=f,check=True)
        return
    if args.mode=='train':
        if not args.explicit_standalone_override:
            parser.error('Production training must launch through the evaluation scheduler; standalone requires an explicit user override')
        launch_lock=(OUT/'production-launch.lock').open('a')
        fcntl.flock(launch_lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert (OUT/'smoke-verified.json').exists() or args.allow_unverified_smoke,'Smoke verification required unless explicitly waived'
        assert not (ROOT/'checkpoints/transformer'/RUN).exists(),'Refusing to overwrite an existing production run'
        preflight=json.loads((OUT/'preflight.json').read_text())
        resolved=subprocess.check_output([PYTHON,'pretrain.py',*overrides(),'--cfg','job','--resolve'],env=env)
        assert hashlib.sha256(resolved).hexdigest()==preflight['config_sha256'],'Configuration differs from data preflight'
        for key in ('tokenizer_path','chat_template_path'):
            assert Path(preflight['metadata']['tokenizer_info'][key]).is_file(),key
        for path in ('tokens.npy','metadata.json',*[f'epoch_0/{k}.npy' for k in ('inst_start','inst_len','resp_start','resp_len')]):
            assert (ROOT/'data/sampled_dfm11'/path).is_file(),path
        settings=json.loads((ROOT/'config/training_suspend_b200.json').read_text())
        for key in ('shim_library','nccl_library','redis_server','cuda_checkpoint'):
            assert Path(settings[key]).is_file(),key
        (OUT/'launch-authorization.json').write_text(json.dumps({'time':time.time(),'wait_for_gpus':args.wait_for_gpus,'smoke_unverified':not (OUT/'smoke-verified.json').exists(),'config_sha256':preflight['config_sha256']},indent=2))
    if not args.wait_for_gpus:
        free=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True)
        assert len(free.splitlines())==8 and min(map(int,free.splitlines()))>=178000,'All eight GPUs must be free'
    env['CUDA_VISIBLE_DEVICES']='0,1,2,3,4,5,6,7'
    env['WANDB_MODE']='disabled' if args.mode=='smoke' else 'online'
    command=[str(Path(PYTHON).parent/'torchrun'),'--standalone','--nproc_per_node=8','pretrain.py',*overrides(args.mode=='smoke')]
    control=OUT/('smoke-control' if args.mode=='smoke' else 'control')
    launch=[PYTHON,'-m','training_suspend.launcher','--settings',str(ROOT/'config/training_suspend_b200.json'),'--control-root',str(control),'--',*command]
    (OUT/(args.mode+'-command.json')).write_text(json.dumps(launch,indent=2))
    subprocess.run(launch,env=env,check=True)

if __name__=='__main__':main()
