"""Build the managed B dfm15 plan: cooperative suspension training + full DFM15 XL eval suite per 50K boundary.

Clones the eval rows installed for the DFM15 XL 3.8M campaign (archived scheduler
backup) once per boundary, rewriting checkpoint paths, steps, epochs, ports and
W&B identity for the B run. Adds 11 cooperative training rows whose single live
process suspends at every 50K boundary. Writes plan.tsv; import it with
`python -m eval_scheduler database import`.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'eval_scheduler'))

from eval_scheduler.model import Action, Job, JobStatus
from eval_scheduler.store import SQLiteJobStore

SOURCE_DB = ROOT / 'incoming/mimir-xl-20261015/transfer-state/final/scheduler-backup.sqlite'
SOURCE_PREFIX = 'dfm15-xl-3800000-eval-'
SOURCE_TRAIN = 'dfm15-xl-step_3800000-train'
SOURCE_EXPORT_WRAPPER = 'scripts/export_dfm15_xl_3800000.sh'
PLAN_DIR = ROOT / 'logs/scheduler/B_dfm15_gemma4_epoch1_20261103'
CKPT_DIR = '/work/dfm/HRM-Text/checkpoints/hrm_v2/B-dfm15-gemma4-epoch1'
EPOCHS_JSON = ROOT / '.tmp_vocab_probe/b_dfm15_boundaries_gas1_c32.json'
_SIM = json.loads(EPOCHS_JSON.read_text())
TOTAL_STEPS = _SIM['_total_groups']
BOUNDARIES = [b for b in _SIM if not b.startswith('_') and not _SIM[b].get('total')]
BOUNDARIES = sorted(int(b) for b in BOUNDARIES)
assert BOUNDARIES == [50000, 100000, 150000, 200000, 250000, 300000, 350000, 400000, 450000, 500000]
BOUNDARIES.append(TOTAL_STEPS)
DECAY_START = 450000  # last 50K block + tail decays; total in (500K, 550K)
RUN_ID = 'B-dfm15-gemma4-epoch1'
RUN_NAME = 'B-dfm15-gemma4-epoch1'
CONTROL_ROOT = '/work/dfm/HRM-Text/logs/training/B-dfm15-gemma4-epoch1/cooperative_0_to_epoch1'
SETTINGS = '/work/dfm/HRM-Text/config/training_suspend_b200.json'
HRM_PYTHON = '/home/ucloud/miniforge3/envs/hrm/bin/python'
CUDA_CHECKPOINT = '/home/ucloud/miniforge3/envs/cuda-checkpoint-test/bin/cuda-checkpoint'
TOKENIZER_DIR = '/work/dfm/brainsurgery/models/gemma4_31b'
WORKDIR = '/work/dfm/HRM-Text'
EUROEVAL_BIN = ('/home/ucloud/miniforge3/envs/hrm/bin/uv run --no-project --with euroeval '
                '/work/dfm/HRM-Text/scripts/euroeval_api_no_flash_attn_guard.py')

TRAIN_ENV = ['OMP_NUM_THREADS=1', 'MKL_NUM_THREADS=1']
TRAIN_ARGS = [
    HRM_PYTHON.replace('/bin/python', '/bin/torchrun'), '--nproc_per_node=8', 'pretrain.py',
    'arch/size@arch=B',
    'data=dfm15', 'data.path=/work/dfm/HRM-Text/incoming/mimir-xl-20261015/data/sampled_dfm15',
    'epochs=1', 'global_batch_size=262144', 'gradient_accumulation_steps=1', 'seed=0',
    'accelerator_type=sm100', 'distributed_strategy=fsdp', 'fsdp_params_precision=fp32',
    'fsdp_shard_degree=null', 'fsdp_reshard_after_forward=false',
    'fsdp_accumulation_sync_mode=no_sync', 'fsdp_wrap_policy=single_unit',
    'fwd_bwd_dtype=bfloat16', 'activation_checkpointing=none', 'compile_train_batch=true',
    'arch.bp_max_steps=8', f'arch.bp_warmup_ratio={50000 / TOTAL_STEPS:.6f}',
    'lr=3e-4', 'lr_auto=true', 'lr_min_ratio=0.0333333333333333',
    'lr_warmup_steps=5000', f'lr_decay_start_step={DECAY_START}',
    f'lr_decay_end_step={TOTAL_STEPS}',
    'lr_rewarm_steps=0', 'lr_piecewise_points=null', 'lr_cooldown_checkpoint=null',
    'lr_embeddings=null', 'lr_head=null', 'lr_h=null', 'lr_l=null',
    'beta1=0.9', 'beta2=0.95', 'weight_decay=0.1', 'ema=0.9999',
    'checkpoint_format=sharded', 'checkpoint_interval=1', 'checkpoint_step_interval=10000',
    'ephemeral_checkpoint_step_interval=500', 'memory_log_interval=100',
    f'checkpoint_path={CKPT_DIR}',
    'reset_ema_on_resume=false', 'upcast_optimizer_state_on_resume=false',
    f'training_total_steps={TOTAL_STEPS}', f'stop_after_step={TOTAL_STEPS}',
    'project_name=DFM5', f'run_name={RUN_NAME}', f'wandb_run_id={RUN_ID}', 'wandb_resume=auto',
    'suspend_after_steps=[' + ','.join(str(b) for b in BOUNDARIES[:-1]) + ']',
    'suspend_poll_interval_steps=10', 'suspend_wait_poll_seconds=2',
]


def boundary_epochs():
    data = json.loads(EPOCHS_JSON.read_text())
    rows = data['_total_rows']
    return {int(k): v['cursor'] / rows for k, v in data.items() if not k.startswith('_')}


def rewrite(value, boundary):
    if isinstance(value, dict):
        return {rewrite(k, boundary): rewrite(v, boundary) for k, v in value.items()}
    if isinstance(value, list):
        return [rewrite(v, boundary) for v in value]
    if isinstance(value, str):
        for old, new in [
            ('/work/dfm/HRM-Text/' + SOURCE_EXPORT_WRAPPER, HRM_PYTHON),
            ('/work/dfm/HRM-Text', '/work/dfm/HRM-Text'),
            ('/work/dfm/HRM-Text/checkpoints/dfm15/XL-from-dfm14-epoch1', CKPT_DIR),
            ('dfm15_XL_step_3800000_ema_hf', f'B_dfm15_gemma4_step_{boundary}_ema_hf'),
            ('dfm15_XL/step_3800000', f'B_dfm15_gemma4/step_{boundary}'),
            ('dfm15_XL', 'B_dfm15_gemma4'),
            ('hrm-dfm15-XL', 'hrm-B-dfm15'),
            (SOURCE_EXPORT_WRAPPER, HRM_PYTHON),
            ('step_3800000', f'step_{boundary}'),
            ('3768319', str(boundary)),
            ('3800000', str(boundary)),
        ]:
            value = value.replace(old, new)
        return value
    return value


def prune_roots(value):
    if isinstance(value, list):
        return [prune_roots(v) for v in value
                if not (isinstance(v, str) and v.startswith('/') and not Path(v).exists())]
    if isinstance(value, dict):
        return {k: prune_roots(v) for k, v in value.items()}
    return value


def clone_block(boundary, index, epochs, train_id, prev_boundary=None, terminals=()):
    con = sqlite3.connect(f'file:{SOURCE_DB}?mode=ro', uri=True)
    source = [json.loads(d) for (d,) in con.execute(
        "SELECT definition FROM jobs WHERE job_id LIKE 'dfm15-xl-3800000-eval-%'")]
    con.close()
    id_map = {}
    for row in source:
        id_map[row['job_id']] = 'b-dfm15-{}-eval-{}'.format(
            boundary, row['job_id'][len(SOURCE_PREFIX):])
    jobs = []
    unexplained = []
    for row in source:
        metadata = rewrite(json.loads(row['metadata_json']), boundary)
        metadata.update(eval_step=boundary, eval_epoch=epochs[boundary],
                        xl_boundary=boundary, checkpoint_tag=f'step_{boundary}',
                        plan_dir=str(PLAN_DIR), wandb_project='DFM5',
                        wandb_run_id=RUN_ID, wandb_run_name=RUN_NAME)
        if 'port_base' in metadata:
            metadata['port_base'] = 50000 + index * 200
        if metadata.get('export_tokenizer_path'):
            metadata['export_tokenizer_path'] = TOKENIZER_DIR
        if metadata.get('euroeval_bin'):
            metadata['euroeval_bin'] = EUROEVAL_BIN
        if isinstance(metadata.get('python_bin'), str) and (
                metadata['python_bin'].endswith('resume_xl_dfm12_epoch11.sh')
                or metadata['python_bin'].endswith('export_dfm15_xl_3800000.sh')):
            metadata['python_bin'] = HRM_PYTHON
        for key in ('additional_dfm_roots', 'additional_euroeval_roots', 'expanded_roots'):
            if key in metadata:
                metadata[key] = prune_roots(metadata[key])
        deps = []
        for dep in (row['deps'] or '').split(','):
            dep = dep.strip()
            if not dep:
                continue
            if dep == SOURCE_TRAIN:
                deps.append(train_id)
            elif dep in id_map:
                deps.append(id_map[dep])
            else:
                unexplained.append((row['job_id'], dep))
                deps.append(train_id)
        if row['action'] == 'wait_checkpoint' and prev_boundary is not None:
            deps += [f'b-dfm15-{prev_boundary}-eval-{s}' for s in terminals]
        new_id = id_map[row['job_id']]
        jobs.append(Job.from_wire({**row, 'job_id': new_id, 'deps': ','.join(deps),
                                    'metadata_json': json.dumps(metadata),
                                    'status': 'pending', 'attempt': '0'}))
    if unexplained:
        print(f'WARNING boundary {boundary}: {len(unexplained)} unmapped deps, e.g. {unexplained[:3]}')
    return jobs, id_map


def train_rows(epochs, resume_tag, terminals=()):
    rows = []
    previous = None
    for index, boundary in enumerate(BOUNDARIES):
        job_id = f'b-dfm15-train-{boundary}'
        command = list(TRAIN_ENV) + TRAIN_ARGS
        cooperative = {'control_root': CONTROL_ROOT, 'command': command,
                       'python': HRM_PYTHON, 'launcher_settings': SETTINGS,
                       'cuda_checkpoint': CUDA_CHECKPOINT,
                       'final_boundary': boundary == TOTAL_STEPS}
        metadata = {
            'checkpoint_carry_ranks': 8, 'ckpt_path': CKPT_DIR,
            'ckpt_tag': f'step_{boundary}', 'command': ' '.join(command),
            'min_gpu_free_mib': 178000, 'resume_ckpt_path': CKPT_DIR,
            'stop_after_step': boundary, 'workdir': WORKDIR,
            'cooperative_training': cooperative,
            'eval_step': boundary, 'eval_epoch': epochs[boundary],
        }
        first_tag = resume_tag if resume_tag not in (None, '', 'none') else None
        if first_tag is not None or previous is not None:
            metadata['resume_from_tag'] = first_tag if previous is None else f'step_{previous}'
        if boundary == TOTAL_STEPS:
            metadata['completion_checkpoint_tag'] = 'epoch_1'
        deps = []
        if previous is not None:
            deps = [f'b-dfm15-train-{previous}']
            deps += [f'b-dfm15-{previous}-eval-{s}' for s in terminals]
        rows.append(Job(
            job_id=job_id, action=Action.TRAIN_UNTIL_STEP, family='training',
            name=f'step_{boundary}', deps=tuple(deps),
            deps_mode='terminal' if deps else 'success',
            max_retries=1, gpu_policy='all', status=JobStatus.PENDING,
            log_dir=f'/work/dfm/HRM-Text/logs/training/B-dfm15-gemma4-epoch1/to_{boundary}',
            metadata=metadata))
        previous = boundary
    return rows


BARRIER_SUFFIXES = None


def load_source():
    con = sqlite3.connect(f'file:{SOURCE_DB}?mode=ro', uri=True)
    source = [json.loads(d) for (d,) in con.execute(
        "SELECT definition FROM jobs WHERE job_id LIKE 'dfm15-xl-3800000-eval-%'")]
    con.close()
    return source


def block_terminals():
    """Suffixes of source block rows with no dependents inside the block."""
    source = load_source()
    idset = {r['job_id'] for r in source}
    gated = set()
    for row in source:
        for dep in (row.get('deps') or '').split(','):
            dep = dep.strip()
            if dep in idset:
                gated.add(dep)
    return sorted(row['job_id'][len(SOURCE_PREFIX):] for row in source
                  if row['job_id'] not in gated)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume-tag', default='none',
                        help="Checkpoint tag for the first training row to resume from ('none' = fresh)")
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    epochs = boundary_epochs()
    missing = [b for b in BOUNDARIES if b not in epochs]
    if missing:
        raise RuntimeError(f'Missing boundary cursors: {missing}')

    source = load_source()
    suffixes = [row['job_id'][len(SOURCE_PREFIX):] for row in source
                if row['action'] == 'terminal_barrier']
    global BARRIER_SUFFIXES
    BARRIER_SUFFIXES = suffixes
    gate = [s for s in suffixes if s.endswith('train-evals-terminal')]
    if len(gate) != 1:
        raise RuntimeError(f'Expected one train-evals-terminal gate, got {gate}')
    print(f'Source rows: {len(source)}; barriers: {suffixes}')

    train_by_id = {r.job_id: r for r in
                   train_rows(epochs, args.resume_tag, block_terminals())}
    plan = []
    for index, boundary in enumerate(BOUNDARIES):
        train_id = f'b-dfm15-train-{boundary}'
        prev = BOUNDARIES[index - 1] if index else None
        block, id_map = clone_block(boundary, index, epochs, train_id,
                                    prev, block_terminals() if prev else ())
        plan.append(train_by_id[train_id])
        plan.extend(block)
        print(f'boundary {boundary}: block={len(block)} rows')

    total = sum(1 for j in plan if j.action != Action.TRAIN_UNTIL_STEP)
    print(f'plan rows: {len(plan)} ({total} eval rows, {len(plan) - total} train rows)')

    ids = {j.job_id for j in plan}
    dangling = [(j.job_id, d) for j in plan for d in j.deps if d not in ids]
    if dangling:
        raise RuntimeError(f'Dangling deps: {dangling[:5]}')
    leftovers = [j.job_id for j in plan if '3800000' in json.dumps(j.metadata) or '/work/dfm' in json.dumps(j.metadata)]
    if leftovers:
        raise RuntimeError(f'Unrewritten source strings in: {leftovers[:5]}')

    if not args.apply:
        print('Dry run OK; rerun with --apply to write plan.tsv')
        return
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    from eval_scheduler.model import write_plan
    write_plan(PLAN_DIR / 'plan.tsv', plan)
    print(f'Wrote {PLAN_DIR / "plan.tsv"}')


if __name__ == '__main__':
    main()
