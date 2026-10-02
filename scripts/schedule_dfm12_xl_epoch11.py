"""Prepare (never auto-start) original XL's identity-free DFM12 epoch campaign."""
import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
from dfm12.io import digest, file_hash, load, write_json
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import Action, Job, JobStatus, read_plan, write_plan
from eval_scheduler.runtime import checkpoint_ready
from scripts.schedule_identity_final_ema_full import canonical_log_dir

SOURCE_PLAN = ROOT / 'logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725'
TEMPLATE_PREFIX = 'dfm11-xl-e10-epoch_10-'
RUN_MANIFEST = ROOT / 'data/dfm12/xl-epoch11-noidentity/run.json'
SOURCE = ROOT / 'checkpoints/dfm11/XL-from-dfm10-epoch9'
CHECKPOINT = ROOT / 'checkpoints/dfm12/XL-from-dfm11-epoch10-noidentity'
DATA = ROOT / 'data/sampled_dfm12_xl_epoch11_noidentity'
PLAN = ROOT / 'logs/scheduler/dfm12_XL_epoch11_noidentity'
RUN = 'dfm8-xl-from-dfm6-dfm7-epoch5-clean-full'
PYTHON = '/home/ucloud/miniforge3/envs/hrm/bin/python'
PREFIX = 'dfm12-xl-e11-'


def run_policy_hash(path):
    return digest({k:v for k,v in read_run(path).items() if k!='completed'})


def read_run(path):
    run = load(path)
    if (type(run.get('start_step')) is not int or run['start_step'] != 2877261
            or type(run.get('end_step')) is not int or run['end_step'] <= 2950000):
        raise ValueError('Require original XL start2877261 and disjoint rewarm to2900000/final50K decay')
    if run.get('identity_repeat', 0) != 0:
        raise ValueError('Identity repeat must be zero')
    for key, expected in dict(epochs=11, wandb_project='DFM5', wandb_run_id=RUN,
                              source_tag='epoch_10', lr=3e-4, lr_auto=True,
                              lr_rewarm_start_step=run['start_step']).items():
        if key in run and run[key] != expected:
            raise ValueError('Unexpected run manifest field: '+key)
    for key, expected in dict(dataset=DATA,source_checkpoint=SOURCE,checkpoint_path=CHECKPOINT).items():
        if key in run and (ROOT/run[key]).resolve()!=expected.resolve():
            raise ValueError('Unexpected run manifest path: '+key)
    for key, expected in dict(lr_rewarm_steps=2900000-run['start_step'], lr_rewarm_start_ratio=1/30,
                              lr_min_ratio=1/30, lr_decay_start_step=3250000,
                              lr_decay_end_step=run['end_step']).items():
        if key in run and run[key] != expected:
            raise ValueError('Unexpected LR manifest field: '+key)
    return run


def boundaries(run):
    return list(range((run['start_step']//50000+1)*50000, run['end_step'], 50000))


def build(template, run, plan=PLAN, manifest=RUN_MANIFEST):
    """Clone complete original-XL axes/tasks, with clean epoch-specific paths."""
    if len(template) != 290 or any(j.action == Action.TRAIN_UNTIL_STEP for j in template):
        raise ValueError('Expected the complete 290-job original XL evaluation template')
    if any(j.status not in (JobStatus.DONE, JobStatus.SKIPPED) for j in template):
        raise ValueError('Evaluation template is not fully settled')
    for action in (Action.WAIT_CHECKPOINT, Action.EXPORT_HF, Action.TERMINAL_BARRIER, Action.TEARDOWN_EVAL):
        if sum(j.action == action for j in template) != 1:
            raise ValueError('Missing or ambiguous evaluation lifecycle')
    jobs, previous, resume = [], None, 'epoch_10'
    for target in [*boundaries(run), run['end_step']]:
        final = target == run['end_step']
        tag = 'epoch_11' if final else f'step_{target}'
        prefix = PREFIX + tag + '-'
        train_id = prefix + 'train'
        command = [PYTHON, str(Path(__file__).resolve()), 'segment', '--plan-dir', str(plan),
                   '--run-manifest', str(manifest), '--', 'bash',
                   str(ROOT/'scripts/resume_xl_dfm12_epoch11.sh'), '--run-manifest', str(manifest)]
        jobs.append(Job(job_id=train_id, action=Action.TRAIN_UNTIL_STEP, family='training', name=tag,
            deps=(previous,) if previous else (), gpu_policy='all', gpu_count=8, max_retries=0,
            log_dir=str(ROOT/'logs/training/dfm12_XL_epoch11'/tag), metadata=dict(
                command=shlex.join(command), workdir=str(ROOT), ckpt_path=str(CHECKPOINT), ckpt_tag=tag,
                stop_after_step=target+1 if final else target, completion_checkpoint_tag='epoch_11',
                checkpoint_carry_ranks=8, resume_ckpt_path=str(SOURCE if resume=='epoch_10' else CHECKPOINT),
                resume_from_tag=resume, min_gpu_free_mib=178000, xl_boundary=target)))
        mapping = {j.job_id: prefix+j.job_id.removeprefix(TEMPLATE_PREFIX) for j in template}
        batch = []
        for old in template:
            meta = copy.deepcopy(old.metadata)
            new_root = f'dfm12_XL_epoch11/{tag}'
            for key, value in list(meta.items()):
                if isinstance(value,str):
                    meta[key] = value.replace('dfm11_XL_epoch10/epoch_10',new_root)
            meta.update(ckpt_path=str(CHECKPOINT), ckpt_tag=tag, checkpoint_tag=tag,
                eval_epoch=11.0 if final else 10+(target-run['start_step'])/(run['end_step']-run['start_step']),
                wandb_project='DFM5', wandb_run_id=RUN,
                wandb_run_name='DFM8-XL clean full from DFM6-DFM7 epoch5',
                model_prefix='hrm-dfm12-XL-epoch11', plan_dir=str(plan), xl_boundary=target,
                fix_mistral_regex=False, no_ema=False)
            for key in ('hf_export_dir','hrm_hf_export_dir','standard_hf_export_dir'):
                if key in meta:
                    meta[key] = str(ROOT/f'exports/dfm12_XL_epoch11_{tag}_ema_hf')
            if old.action == Action.EXPORT_HF:
                meta['export_tokenizer_path'] = str(ROOT/'data/dfm11_tokenizer')
                meta['python_bin'] = str(ROOT/'scripts/resume_xl_dfm12_epoch11.sh')
                meta['tokenizer_variant'] = 'training_no_mistral_regex'
            if old.action == Action.AVERAGE:
                meta.update(atomic_v3_averages=True, average_prefix='headline_avg_v3')
            deps = (train_id,) if old.action == Action.WAIT_CHECKPOINT else tuple(mapping[d] for d in old.deps)
            job = old.with_updates(job_id=mapping[old.job_id], deps=deps, metadata=meta, attempt=0,
                name=tag if old.action in (Action.WAIT_CHECKPOINT,Action.EXPORT_HF) else old.name,
                status=JobStatus.SKIPPED if old.status==JobStatus.SKIPPED else JobStatus.PENDING,
                log_dir=str(plan/'checkpoints'/tag))
            batch.append(job.with_updates(log_dir=str(canonical_log_dir(job))))
        # Training release is independent of CPU merge/report success, as in the source plan.
        previous = next(j.job_id for j in batch if j.action == Action.TEARDOWN_EVAL)
        jobs.extend(batch)
        resume = tag
    ids = {j.job_id for j in jobs}
    if len(ids) != len(jobs) or any(not set(j.deps) <= ids for j in jobs):
        raise ValueError('Invalid campaign dependency graph')
    return jobs


def training_arguments(run, overrides):
    allowed = {'stop_after_step','resume_checkpoint_path','resume_checkpoint_tag'}
    if any('=' not in arg or arg.split('=',1)[0] not in allowed for arg in overrides):
        raise ValueError('Only scheduler stop/resume overrides are accepted')
    return ['torchrun','--nproc_per_node=8','pretrain.py','data=dfm12_xl_epoch11_noidentity',f'data.path={DATA}',
        'arch/size@arch=XL','arch.bp_max_steps=8','arch.bp_warmup_ratio=0.2',
        'lr=3e-4','lr_auto=true','lr_min_ratio=0.03333333333333333',
        f"lr_rewarm_steps={2900000-run['start_step']}",'lr_rewarm_start_ratio=0.03333333333333333',
        f"lr_rewarm_start_step={run['start_step']}",'lr_decay_start_step=3250000',
        f"lr_decay_end_step={run['end_step']}",'lr_cooldown_checkpoint=null',
        'lr_embeddings=null','lr_head=null','lr_h=null','lr_l=null',
        'beta1=0.9','beta2=0.95','weight_decay=0.1','ema=0.9999',
        'global_batch_size=262144','gradient_accumulation_steps=2','epochs=11',
        f"training_total_steps={run['end_step']}",'distributed_strategy=fsdp','fsdp_params_precision=fp32',
        'fsdp_wrap_policy=transformer_block','fsdp_shard_degree=null','fsdp_reshard_after_forward=false',
        'fsdp_accumulation_sync_mode=no_sync','fwd_bwd_dtype=bfloat16','accelerator_type=sm100',
        'activation_checkpointing=none','compile_train_batch=true','checkpoint_format=sharded',
        'checkpoint_interval=1','checkpoint_step_interval=10000','ephemeral_checkpoint_step_interval=500',
        f'checkpoint_path={CHECKPOINT}',f'resume_checkpoint_path={SOURCE}','resume_checkpoint_tag=epoch_10',
        'reset_ema_on_resume=false','upcast_optimizer_state_on_resume=false','project_name=DFM5',
        'run_name=DFM8-XL clean full from DFM6-DFM7 epoch5',f'wandb_run_id={RUN}','wandb_resume=must',
        *overrides]


def gpu_gate(output):
    rows = [line.split(',') for line in output.strip().splitlines()]
    if len(rows)!=8 or {int(r[0]) for r in rows}!=set(range(8)) or any(int(r[1])<178000 for r in rows):
        raise RuntimeError('All eight GPUs must have >=178000 MiB free; no processes will be stopped')


def validate_export_tokenizer(directory):
    from tokenizers import Tokenizer
    from transformers import AutoTokenizer
    directory=Path(directory)
    training=ROOT/'data/dfm11_tokenizer'
    if (directory/'tokenizer.json').read_bytes()!=(training/'tokenizer.json').read_bytes():
        # Tokenizers serialization may change whitespace, never the actual tokenizer.
        if load(directory/'tokenizer.json')!=load(training/'tokenizer.json'):
            raise ValueError('Export tokenizer differs from training')
    config=load(directory/'tokenizer_config.json')
    config['fix_mistral_regex']=False
    write_json(directory/'tokenizer_config.json',config)
    tokenizer=AutoTokenizer.from_pretrained(directory,local_files_only=True)
    if tokenizer.chat_template!=(training/'chat_template.jinja').read_text():
        raise ValueError('Export template differs from training')
    raw=Tokenizer.from_file(str(training/'tokenizer.json'))
    if json.loads(tokenizer.backend_tokenizer.to_str())['pre_tokenizer']!=json.loads(raw.to_str())['pre_tokenizer']:
        raise ValueError('Export AutoTokenizer changed pre-tokenization')
    samples=['Hello, world!\nNext line.','Dansk: et svar, og en forklaring.',
             'def f(x):\n    return x + 1','\\boxed{42}',
             '{"name":"search","arguments":{"q":"test"}}']
    samples += [tokenizer.apply_chat_template([dict(role='user',content=s)],tokenize=False,
                add_generation_prompt=True,enable_thinking=False) for s in samples.copy()]
    for sample in samples:
        if raw.encode(sample,add_special_tokens=False).ids!=tokenizer.encode(sample,add_special_tokens=False):
            raise ValueError('Training/export tokenizer parity failed')
    write_json(directory/'training-tokenizer-parity.json',dict(fix_mistral_regex=False,
        samples=len(samples),tokenizer_sha256=file_hash(training/'tokenizer.json'),
        template_sha256=file_hash(training/'chat_template.jinja')))


def export_checkpoint(command):
    if not command or command[0]!='conversion/convert_to_hf.py':
        raise ValueError('Expected retained checkpoint converter')
    directory=Path(command[command.index('--out_dir')+1])
    subprocess.run([PYTHON,*command],cwd=ROOT,check=True)
    validate_export_tokenizer(directory)


def prepare(plan, manifest):
    run = read_run(manifest)
    template = [j for j in read_plan(SOURCE_PLAN/'plan.tsv') if j.job_id.startswith(TEMPLATE_PREFIX)]
    jobs = build(template,run,plan,manifest)
    plan.mkdir(parents=True,exist_ok=True)
    with PlanLock(plan):
        if (plan/'plan.tsv').exists():
            raise FileExistsError('Refuse to overwrite an existing plan')
        write_plan(plan/'plan.tsv',jobs)
        write_json(plan/'preflight.json',dict(start_step=run['start_step'],end_step=run['end_step'],
            run_manifest=str(manifest),run_policy_sha256=run_policy_hash(manifest),source_plan=str(SOURCE_PLAN),
            template_plan_sha256=file_hash(SOURCE_PLAN/'plan.tsv'),jobs=len(jobs),
            pins={str(p):file_hash(p) for p in (Path(__file__).resolve(),ROOT/'scripts/resume_xl_dfm12_epoch11.sh')},
            clean_boundaries=boundaries(run),persistent_vllm_required=True,started=False))
    print(plan)


def data_ready(manifest):
    """Publication receipt is required independently of the early packed budget."""
    receipt_path=Path(manifest).parent/'ready.json'
    if not receipt_path.is_file() or not (DATA/'metadata.json').is_file():
        return False
    receipt=load(receipt_path)
    run=read_run(manifest)
    if (not run.get('specification_sha256') or receipt.get('specification_sha256')!=run['specification_sha256']
            or receipt.get('end_step')!=run['end_step']
            or (ROOT/receipt.get('dataset','')).resolve()!=DATA.resolve()
            or receipt.get('metadata_sha256')!=file_hash(DATA/'metadata.json')):
        raise ValueError('Data readiness receipt specification/end/dataset/metadata mismatch')
    for path in (DATA/'tokens.npy',DATA/'epoch-mapping.json',
                 *(DATA/'epoch_10'/f'{name}.npy' for name in ('inst_start','inst_len','resp_start','resp_len'))):
        if not path.is_file():
            raise ValueError('Published data file missing: '+str(path))
    if load(DATA/'epoch-mapping.json')['identity_repeat']!=0:
        raise ValueError('Published data includes identity repetition')
    return True


def scheduler_command(plan, monitor=False):
    return [PYTHON,'-m','eval_scheduler','monitor' if monitor else 'run',
            '--plan-dir',str(plan),'--gpus','0,1,2,3,4,5,6,7',
            '--rich' if monitor else '--persistent-vllm']


def bootstrap(plan, manifest, monitor=False):
    """CPU-only waiting; the ordinary scheduler remains the only GPU job runner."""
    plan.mkdir(parents=True,exist_ok=True)
    handle=(plan/('monitor-bootstrap.lock' if monitor else 'bootstrap.lock')).open('a')
    fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    os.set_inheritable(handle.fileno(),True)
    def available():
        return ((plan/'preflight.json').exists() and (plan/'plan.tsv').exists()) if monitor else manifest.is_file()
    while not available():
        print('Waiting for '+str(plan/'preflight.json' if monitor else manifest),flush=True)
        time.sleep(30)
    if not monitor:
        if not (plan/'plan.tsv').exists():
            prepare(plan,manifest)
        receipt=load(plan/'preflight.json')
        if receipt['run_policy_sha256']!=run_policy_hash(manifest):
            raise ValueError('Existing plan run manifest drift')
        if any(file_hash(p)!=sha for p,sha in receipt['pins'].items()):
            raise ValueError('Existing plan implementation drift')
        while not data_ready(manifest):
            if (plan/'stop.request').exists():
                print('Manual stop present; bootstrap will not start scheduler',flush=True)
                return
            print('Plan prepared; waiting for metadata.json and ready.json',flush=True)
            time.sleep(30)
    command=scheduler_command(plan,monitor)
    print('Starting '+shlex.join(command),flush=True)
    os.execv(command[0],command)


def segment(plan, manifest, command):
    receipt = load(plan/'preflight.json')
    if receipt['run_policy_sha256']!=run_policy_hash(manifest) or any(file_hash(p)!=sha for p,sha in receipt['pins'].items()):
        raise ValueError('Prepared training inputs/launcher drift')
    # Freeze the validated policy before training: later queued-policy edits
    # must not invalidate a successfully completed segment.
    run = read_run(manifest)
    result = subprocess.run(command,cwd=ROOT)
    if result.returncode:
        raise SystemExit(result.returncode)
    target = int(next(x.split('=',1)[1] for x in command if x.startswith('stop_after_step=')))
    tag = 'epoch_11' if target>run['end_step'] else f'step_{target}'
    with PlanLock(plan):
        jobs = read_plan(plan/'plan.tsv')
        train = next(j for j in jobs if j.action==Action.TRAIN_UNTIL_STEP and j.metadata['ckpt_tag']==tag)
        if not checkpoint_ready(train)[0]:
            raise RuntimeError('Expected segment checkpoint is incomplete')
        if tag!='epoch_11':
            import numpy as np
            state = load(CHECKPOINT/f'checkpoint_state_{tag}.json')
            rows = len(np.load(DATA/'epoch_10/inst_start.npy',mmap_mode='r'))
            epoch = 10 + state['global_row_cursor_in_epoch']/rows
            jobs = [j.with_updates(metadata={**j.metadata,'eval_epoch':epoch})
                    if j.metadata.get('ckpt_tag')==tag and j.action!=Action.TRAIN_UNTIL_STEP else j for j in jobs]
            write_plan(plan/'plan.tsv',jobs)


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('mode',choices=('prepare','segment','train','bootstrap','monitor','export'))
    parser.add_argument('--plan-dir',type=Path,default=PLAN)
    parser.add_argument('--run-manifest',type=Path,default=RUN_MANIFEST)
    args,rest=parser.parse_known_args()
    os.chdir(ROOT)
    os.environ['PATH']='/home/ucloud/miniforge3/envs/hrm/bin:/usr/local/cuda/bin:'+os.environ.get('PATH','')
    os.environ['PYTHONPATH']=str(ROOT/'eval_scheduler')+os.pathsep+os.environ.get('PYTHONPATH','')
    if args.mode=='prepare':
        if rest: parser.error('Unexpected prepare arguments')
        prepare(args.plan_dir.resolve(),args.run_manifest.resolve())
    elif args.mode=='segment':
        segment(args.plan_dir.resolve(),args.run_manifest.resolve(),rest[1:] if rest[:1]==['--'] else rest)
    elif args.mode=='export':
        export_checkpoint(rest[1:] if rest[:1]==['--'] else rest)
    elif args.mode in ('bootstrap','monitor'):
        if rest: parser.error('Unexpected bootstrap arguments')
        bootstrap(args.plan_dir.resolve(),args.run_manifest.resolve(),args.mode=='monitor')
    else:
        run=read_run(args.run_manifest)
        command=training_arguments(run,rest)
        if not data_ready(args.run_manifest):
            raise ValueError('Prepared identity-free data readiness receipt missing')
        gpu_gate(subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.free','--format=csv,noheader,nounits'],text=True))
        os.execvp(command[0],command)


if __name__=='__main__':
    main()
