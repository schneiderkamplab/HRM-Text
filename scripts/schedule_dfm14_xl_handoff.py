"""Isolated DFM14 handoff; never change the active3250 DFM13 training row."""
import argparse
import copy
import os
from pathlib import Path
import shlex
import sys
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
from dfm12.io import file_hash, load, lock, write_json
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import Action, Job, JobStatus, read_plan, write_plan
from scripts import prepare_dfm14_xl_handoff as prep
from scripts import schedule_dfm12_xl_epoch11 as base
from scripts.schedule_dfm13_xl_handoff import replace_tree
from scripts.schedule_dfm13_wave34_baseline import check_graph
from scripts.stop_training_at_complete_checkpoint import complete, preserve

START, CONTROL, SOURCE, OUTPUT = prep.START, prep.CONTROL, prep.SOURCE, prep.OUTPUT
PLAN = base.PLAN
SCRIPT = Path(__file__).resolve()
GATE = 'dfm14-xl-transfer-packing-resume-ready'


def boundary(job):
    return int(job.metadata.get('xl_boundary', job.metadata.get('eval_step', 0)))


def validate_future(future):
    for j in future:
        inert_cleanup = (j.status == JobStatus.DONE and not j.attempt
                         and j.action in (Action.TERMINAL_BARRIER, Action.TEARDOWN_EVAL))
        if not inert_cleanup and (j.status not in (JobStatus.PENDING, JobStatus.SKIPPED) or j.attempt):
            raise ValueError('Future job already attempted: ' + j.job_id)


def arm_rows(jobs, control=CONTROL):
    if any(j.job_id == GATE for j in jobs):
        raise ValueError('Gate already installed')
    current = [j for j in jobs if boundary(j) == START]
    if sum(j.action == Action.TRAIN_UNTIL_STEP for j in current) != 1:
        raise ValueError('Missing unique3250 training boundary')
    future = [j for j in jobs if boundary(j) > START]
    if not future:
        raise ValueError('Future jobs absent')
    validate_future(future)
    future_ids = {j.job_id for j in future}
    gate = Job(job_id=GATE, action=Action.WAIT_CHECKPOINT, family='handoff',
               name='DFM14 verified transfer, exact packing and isolated resume',
               deps=tuple(j.job_id for j in current if j.status != JobStatus.SKIPPED),
               max_retries=0, log_dir=str(control / 'readiness'), metadata=dict(
                   ckpt_path=str(control / 'resume'), ckpt_tag=f'step_{START}',
                   checkpoint_carry_ranks=8, checkpoint_wait_seconds=30, checkpoint_wait_max_seconds=0))
    out = [j.with_updates(deps=tuple(dict.fromkeys((*j.deps, GATE))))
           if j.job_id in future_ids and j.action == Action.TRAIN_UNTIL_STEP else j for j in jobs] + [gate]
    check_graph(out)
    return out


def arm(plan=PLAN, control=CONTROL):
    with PlanLock(plan):
        jobs = read_plan(plan / 'plan.tsv')
        validate_extension(jobs)
        out = arm_rows(jobs, control)
        if (control / 'armed.json').exists():
            raise ValueError('Prior arm receipt exists')
        write_plan(control / 'plan-before-gate.tsv', jobs)
        write_plan(plan / 'plan.tsv', out)
        write_json(control / 'armed.json', dict(gate=GATE, current_training_unchanged=True,
                   future_training_gated=True, time=time.time()))


def build(jobs, run, plan=PLAN, control=CONTROL):
    """Clone the latest3250 eval coverage, not a stale pre-expansion template."""
    removed = [j for j in jobs if boundary(j) > START]
    validate_future(removed)
    removed_ids = {j.job_id for j in removed}
    # Retain historical DONE cleanup rows and their referenced IDs. Only unstarted
    # superseded rows become SKIPPED; no completed evidence is erased or reset.
    kept = [j.with_updates(status=JobStatus.SKIPPED,
            metadata={**j.metadata, 'superseded_by_dfm14_handoff': True})
            if j.job_id in removed_ids and j.status == JobStatus.PENDING else j for j in jobs]
    block = [j for j in kept if boundary(j) == START]
    template = [j for j in block if j.action != Action.TRAIN_UNTIL_STEP]
    for action in (Action.WAIT_CHECKPOINT, Action.EXPORT_HF):
        if sum(j.action == action for j in template) != 1:
            raise ValueError('Incomplete3250 lifecycle')
    if not any(j.action == Action.TEARDOWN_EVAL for j in template):
        raise ValueError('Missing3250 teardown')
    if not any(j.job_id == GATE for j in kept):
        raise ValueError('Arm transfer gate before installation')
    previous = tuple(j.job_id for j in block if j.status != JobStatus.SKIPPED) + (GATE,)
    generated = []
    resume = f'step_{START}'
    for target in run['eval_steps']:
        final = target == run['end_step']
        tag = 'epoch_1' if final else f'step_{target}'
        prefix = f'dfm14-xl-{tag}-'
        train_id = prefix + 'train'
        stop = target + 1 if final else target
        train = Job(job_id=train_id, action=Action.TRAIN_UNTIL_STEP, family='training', name=tag,
                    deps=previous, max_retries=0, gpu_policy='all', gpu_count=8,
                    log_dir=str(ROOT / 'logs/training/dfm14_XL' / tag), metadata=dict(
                        command=shlex.join([base.PYTHON, str(SCRIPT), 'segment', '--plan-dir', str(plan),
                                            '--control', str(control)]), workdir=str(ROOT),
                        ckpt_path=str(OUTPUT), ckpt_tag=f'step_{stop}', stop_after_step=stop,
                        completion_checkpoint_tag='epoch_1', checkpoint_carry_ranks=8,
                        resume_ckpt_path=str(SOURCE if resume == f'step_{START}' else OUTPUT),
                        resume_from_tag=resume, min_gpu_free_mib=178000,
                        xl_boundary=target, eval_step=target))
        mapping = {j.job_id: prefix + j.job_id for j in template}
        replacements = [(str(SOURCE), str(OUTPUT)), ('dfm13_XL', 'dfm14_XL'),
                        (f'step_{START}', tag)]
        batch = []
        for old in template:
            meta = replace_tree(copy.deepcopy(old.metadata), replacements)
            meta.update(ckpt_path=str(OUTPUT), ckpt_tag=tag, checkpoint_tag=tag,
                        xl_boundary=target, eval_step=target, plan_dir=str(plan),
                        model_prefix='hrm-dfm14-XL', dfm14_cursor_epoch_pending=True)
            # Existing wrappers/definitions remain pinned; only output/log paths move.
            for key in ('hf_export_dir', 'hrm_hf_export_dir', 'standard_hf_export_dir'):
                if key in meta:
                    meta[key] = str(ROOT / f'exports/dfm14_XL_{tag}_ema_hf')
            deps = (train_id,) if old.action == Action.WAIT_CHECKPOINT else tuple(mapping.get(d, d) for d in old.deps)
            batch.append(old.with_updates(job_id=mapping[old.job_id], deps=deps, metadata=meta,
                         attempt=0, status=JobStatus.SKIPPED if old.status == JobStatus.SKIPPED else JobStatus.PENDING,
                         log_dir=replace_tree(old.log_dir, replacements)))
        generated += [train, *batch]
        previous = tuple(j.job_id for j in batch if j.status != JobStatus.SKIPPED)
        resume = tag
    out = kept + generated
    check_graph(out)
    return out, removed, generated


def training_arguments(run, overrides):
    allowed = {'stop_after_step', 'resume_checkpoint_path', 'resume_checkpoint_tag'}
    if any('=' not in x or x.split('=', 1)[0] not in allowed for x in overrides):
        raise ValueError('Unexpected training override')
    args = base.training_arguments(dict(start_step=2877261, end_step=run['end_step']), [])
    changes = {'data': 'dfm14', 'data.path': str(prep.SAMPLE), 'epochs': '1',
               'lr': '3e-4', 'lr_auto': 'true', 'lr_min_ratio': '1', 'lr_warmup_steps': '0',
               'lr_rewarm_steps': '0', 'lr_rewarm_start_step': 'null',
               'lr_decay_start_step': 'null', 'lr_decay_end_step': 'null',
               'lr_cooldown_checkpoint': 'null', 'arch.bp_warmup_ratio': '0',
               'checkpoint_path': str(OUTPUT), **dict(x.split('=', 1) for x in overrides)}
    present = {x.split('=', 1)[0] for x in args if '=' in x}
    return [f'{x.split("=", 1)[0]}={changes.get(x.split("=", 1)[0], x.split("=", 1)[1])}'
            if '=' in x else x for x in args] + [f'{k}={v}' for k, v in changes.items() if k not in present]


def reset_state(original):
    if (original.get('step') != START or original.get('carry_policy') != 'none'
            or original.get('world_size') != 8 or original.get('gradient_accumulation_steps') != 2):
        raise ValueError('3250 checkpoint step/carry/world/GAS mismatch')
    state = dict(original, epoch=1, batch_in_epoch=0, batch_in_epoch_exact=True,
                 global_row_cursor_in_epoch=0, global_row_start_in_epoch=0, data_path=str(prep.SAMPLE))
    state.pop('lr_rewarm', None)
    return state


def fresh_resume(control=CONTROL):
    tag = f'step_{START}'
    if not complete(SOURCE, tag):
        raise ValueError('Source3250 checkpoint incomplete')
    original = load(SOURCE / f'checkpoint_state_{tag}.json')
    state = reset_state(original)
    target = control / 'resume'
    sha = file_hash(SOURCE / f'checkpoint_state_{tag}.json')
    if target.exists():
        if (load(target / 'handoff.json')['source_sha256'] != sha
                or load(target / f'checkpoint_state_{tag}.json') != state or not complete(target, tag)):
            raise ValueError('Existing isolated resume drift')
        return target
    temporary = control / 'resume.preparing'
    if temporary.exists():
        raise ValueError('Uncommitted resume preparation')
    preserve(SOURCE, temporary, tag)
    write_json(temporary / f'checkpoint_state_{tag}.json', state)
    write_json(temporary / 'handoff.json', dict(source_sha256=sha, original_state=original,
               resume_state=state, optimizer_ema='unchanged hardlinks', time=time.time()))
    os.rename(temporary, target)
    return target


def read_prepared(control):
    run = load(control / 'prepared.json')
    contract = prep.sample_contract()
    if contract is None or prep.proposal(contract, run['packing']) != run:
        raise ValueError('Prepared budget/data/policy drift')
    return run


def validate_eval_pins(jobs):
    for job in jobs:
        for path, sha in job.metadata.get('source_pins', {}).items():
            if file_hash(path) != sha:
                raise ValueError('Inherited evaluation pin drift: ' + job.job_id + ': ' + path)


def validate_extension(jobs):
    block = [j for j in jobs if boundary(j) == START and j.metadata.get('dfm14_eval_50_languages')]
    tasks = [j for j in block if j.action == Action.EVAL_DFM]
    names = {j.name for j in tasks}
    if (len(names) != 32 or len(tasks) != 128
            or any({j.shard for j in tasks if j.name == name} != set(range(4)) for name in names)
            or sum(j.action == Action.AVERAGE for j in block) != 1):
        raise ValueError('Parent32-task/50-language extension not fully installed')


def install(plan=PLAN, control=CONTROL):
    run = read_prepared(control)
    with PlanLock(plan):
        if (control / 'installed.json').exists():
            raise ValueError('Already installed; no automatic replacement')
        jobs = read_plan(plan / 'plan.tsv')
        validate_extension(jobs)
        out, removed, generated = build(jobs, run, plan, control)
        validate_eval_pins(generated)
        paths = [SCRIPT, Path(prep.__file__), Path(base.__file__),
                 ROOT / 'scripts/schedule_dfm13_xl_handoff.py',
                 ROOT / 'scripts/stop_training_at_complete_checkpoint.py',
                 ROOT / 'scripts/transfer_sampled_dfm14.py', ROOT / 'dfm12/prepare_xl_epoch11.py',
                 ROOT / 'multipack_sampler.py', ROOT / 'pretrain.py', ROOT / 'utils/training_wandb.py',
                 ROOT / 'config/data/dfm14.yaml']
        receipt = dict(prepared_sha256=file_hash(control / 'prepared.json'),
                       pins={str(p): file_hash(p) for p in paths}, start_step=START,
                       end_step=run['end_step'], removed_ids=[j.job_id for j in removed],
                       job_ids=[j.job_id for j in generated], time=time.time())
        write_plan(control / 'plan-before-install.tsv', jobs)
        write_json(control / 'install-intent.json', receipt)
        write_plan(plan / 'plan.tsv', out)
        write_json(control / 'installed.json', receipt)
    return receipt


def display_epoch(parent_epoch, state, rows, final=False):
    cursor = state['global_row_cursor_in_epoch']
    if not 0 <= cursor <= rows:
        raise ValueError('Invalid DFM14 row cursor')
    return float(parent_epoch) + (1.0 if final else cursor / rows)


def segment(plan, control, overrides):
    receipt = load(control / 'installed.json')
    if (receipt['prepared_sha256'] != file_hash(control / 'prepared.json')
            or any(file_hash(p) != sha for p, sha in receipt['pins'].items())):
        raise ValueError('Handoff implementation/budget drift')
    run = read_prepared(control)
    values = dict(x.split('=', 1) for x in overrides)
    target = int(values['stop_after_step'])
    with PlanLock(plan):
        jobs = read_plan(plan / 'plan.tsv'); by = {j.job_id: j for j in jobs}
        current = next(j for j in jobs if j.job_id.startswith('dfm14-xl-')
                       and j.action == Action.TRAIN_UNTIL_STEP and j.metadata['stop_after_step'] == target)
        if any(by[d].status != JobStatus.DONE for d in current.deps):
            raise ValueError('Prior evaluations not complete')
        parent = next(j for j in jobs if boundary(j) == START and j.action == Action.EXPORT_HF)
        if parent.status != JobStatus.DONE or parent.metadata.get('dfm13_cursor_epoch_pending'):
            raise ValueError('Actual3250 display epoch not finalized')
        parent_epoch = parent.metadata['eval_epoch']
    if values['resume_checkpoint_tag'] != current.metadata['resume_from_tag']:
        raise ValueError('Wrong resume tag')
    if Path(values['resume_checkpoint_path']).resolve() != Path(current.metadata['resume_ckpt_path']).resolve():
        raise ValueError('Wrong resume checkpoint path')
    if values['resume_checkpoint_tag'] == f'step_{START}':
        values['resume_checkpoint_path'] = str(fresh_resume(control))
    command = training_arguments(run, [f'{k}={v}' for k, v in values.items()])
    base.gpu_gate(subprocess.check_output(['nvidia-smi', '--query-gpu=index,memory.free',
                                          '--format=csv,noheader,nounits'], text=True))
    subprocess.run(command, cwd=ROOT, check=True)
    tag = 'epoch_1' if target > run['end_step'] else f'step_{target}'
    if not complete(OUTPUT, tag):
        raise ValueError('Output checkpoint incomplete')
    state = load(OUTPUT / f'checkpoint_state_{tag}.json')
    if state['step'] != min(target, run['end_step']):
        raise ValueError('Output optimizer step disagrees with exact packing budget')
    epoch = display_epoch(parent_epoch, state, run['packing']['packed_rows'], tag == 'epoch_1')
    with PlanLock(plan):
        jobs = read_plan(plan / 'plan.tsv')
        out = [j.with_updates(metadata={**j.metadata, 'eval_epoch': epoch,
               'dfm14_cursor_epoch_pending': False, 'dfm13_cursor_epoch_pending': False})
               if boundary(j) == min(target, run['end_step']) and j.action != Action.TRAIN_UNTIL_STEP
               else j for j in jobs]
        write_plan(plan / 'plan.tsv', out)


def wait_prepared(control):
    while not (control / 'prepared.json').exists():
        launch = load(control / 'prepare-launch.json')
        cmdline = Path(f"/proc/{launch['pid']}/cmdline")
        observed = cmdline.read_bytes().split(b'\0')[:-1] if cmdline.exists() else []
        if observed != [str(x).encode() for x in launch['command']]:
            if (control / 'prepared.json').exists():
                break
            raise ValueError('Preparation owner exited or changed before publishing budget')
        write_json(control / 'scheduler-progress.json', dict(
                   phase='waiting_existing_preparation_owner', pid=launch['pid'], time=time.time()))
        time.sleep(30)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('mode', choices=['preview', 'arm', 'install', 'watch', 'segment'])
    parser.add_argument('--plan-dir', type=Path, default=PLAN)
    parser.add_argument('--control', type=Path, default=CONTROL)
    args, rest = parser.parse_known_args()
    os.chdir(ROOT)
    os.environ['PATH'] = '/home/ucloud/miniforge3/envs/hrm/bin:/usr/local/cuda/bin:' + os.environ.get('PATH', '')
    os.environ['OMP_NUM_THREADS'] = os.environ['MKL_NUM_THREADS'] = '1'
    if args.mode == 'segment':
        return segment(args.plan_dir, args.control, rest)
    if rest:
        parser.error('Unexpected arguments')
    if args.mode == 'preview':
        with PlanLock(args.plan_dir):
            jobs = read_plan(args.plan_dir / 'plan.tsv')
        out = arm_rows(jobs, args.control)
        write_plan(args.control / 'gate-preview.tsv', out)
        write_json(args.control / 'preview.json', dict(old_jobs=len(jobs), gate=GATE,
                   future_training_rows=sum(boundary(j) > START and j.action == Action.TRAIN_UNTIL_STEP for j in jobs),
                   exact_budget_pending=not (args.control / 'prepared.json').exists(), live_plan_changed=False))
        return
    if args.mode == 'arm':
        return arm(args.plan_dir, args.control)
    with lock(args.control / '.watch.lock'):
        if args.mode == 'watch':
            wait_prepared(args.control)
        install(args.plan_dir, args.control)
        if args.mode == 'watch':
            while not complete(SOURCE, f'step_{START}'):
                time.sleep(30)
            read_prepared(args.control)
            fresh_resume(args.control)
            write_json(args.control / 'resume-ready.json', dict(time=time.time(), training_launched=False))


if __name__ == '__main__':
    main()
