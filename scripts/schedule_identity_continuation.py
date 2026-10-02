"""Checkpoint-safe identity continuation and bounded parent-reviewed eval gate."""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
sys.path.insert(0, str(ROOT))
from dfm12.io import file_hash, load, lock, write_json
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import Action, Job, JobStatus, read_plan, write_plan
from scripts import schedule_xl_identity_interlude as old
from scripts.stop_training_at_complete_checkpoint import alive, complete, preserve
from scripts.handoff_dfm12_multilingual_pilot import wait_until, gpu_free

START, END = 2878261, 2879261
TAG = f'step_{START}'
JOB = 'xl-identity-expanded-2000steps'
BARRIER = JOB + '-terminal'
PREFIX = JOB + '-full-'
STATE = ROOT / 'logs/training/dfm12_XL_identity_expanded_2000steps'
OUTPUT = ROOT / 'checkpoints/dfm12/XL-identity-expanded-from-step2878261'
SOURCE = old.OUTPUT
TRAINER_EPOCH = 12
IDENTITY_STEPS = 2000
EVAL_ROOT = 'dfm12_XL_identity_2000'


def configure(spec):
    """Select a subsequent interlude without changing previous run artifacts."""
    global START, END, TAG, JOB, BARRIER, PREFIX, STATE, OUTPUT, SOURCE
    global TRAINER_EPOCH, IDENTITY_STEPS, EVAL_ROOT
    campaign = spec.get('campaign')
    if campaign is None:
        return
    start, end = spec['start_step'], spec['end_step']
    epoch = campaign['trainer_epoch']
    job = campaign['job_id']
    if (type(start) is not int or type(end) is not int or end - start != 1000
            or type(epoch) is not int or epoch < 2
            or not re.fullmatch(r'[a-z0-9-]+', job)):
        raise ValueError('Invalid identity continuation campaign')
    source, output, state = (Path(campaign[k]).resolve()
                             for k in ('source', 'output', 'state'))
    for path, parent in ((source, ROOT / 'checkpoints'), (output, ROOT / 'checkpoints/dfm12'),
                         (state, ROOT / 'logs/training')):
        if not path.is_relative_to(parent) or path == parent:
            raise ValueError('Campaign path outside its repository ownership boundary')
    if source == output or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('Source and output checkpoint roots must be disjoint')
    START, END, TAG = start, end, f'step_{start}'
    JOB, BARRIER, PREFIX = job, job + '-terminal', job + '-full-'
    SOURCE, OUTPUT, STATE = source, output, state
    TRAINER_EPOCH = epoch
    IDENTITY_STEPS = end - old.START
    EVAL_ROOT = job.replace('-', '_')


def identity(pid):
    path = Path(f'/proc/{pid}')
    stat = (path / 'stat').read_text().rsplit(') ', 1)[1].split()
    if stat[0] == 'Z':
        raise RuntimeError('Process is a zombie')
    return {'pid': pid, 'start_ticks': stat[19],
            'cmdline': (path / 'cmdline').read_bytes().hex(), 'pgid': os.getpgid(pid)}


def same_process(saved):
    try:
        return identity(saved['pid']) == saved
    except (FileNotFoundError, ProcessLookupError, RuntimeError):
        return False


def fresh_resume(source, target, data_path):
    """Immutable DCP payload links, isolated cursor metadata; never mutate source."""
    if target.exists():
        state = load(target / f'checkpoint_state_{TAG}.json')
        transition = load(target / 'fresh-dataset-transition.json')
        if (Path(transition['source']).resolve() != source.resolve()
                or transition['source_sidecar_sha256'] != file_hash(source / f'checkpoint_state_{TAG}.json')
                or transition['resume_state'] != state):
            raise ValueError('Existing resume view provenance differs')
        if (state['step'], state['epoch'], state['batch_in_epoch'],
                state['global_row_cursor_in_epoch'], state['data_path']) != (START, TRAINER_EPOCH, 0, 0, str(data_path)):
            raise ValueError('Existing resume view differs')
        if not complete(target, TAG):
            raise ValueError('Incomplete resume view')
        return
    if not complete(source, TAG):
        raise ValueError('Source checkpoint incomplete')
    original = load(source / f'checkpoint_state_{TAG}.json')
    if original['step'] != START or original.get('carry_policy') != 'none':
        raise ValueError('Unexpected source step/carry policy')
    preserve(source, target, TAG)
    state = dict(original, epoch=TRAINER_EPOCH, batch_in_epoch=0, batch_in_epoch_exact=True,
                 global_row_cursor_in_epoch=0, global_row_start_in_epoch=0, data_path=str(data_path))
    write_json(target / f'checkpoint_state_{TAG}.json', state)
    write_json(target / 'fresh-dataset-transition.json', {
        'source': str(source), 'source_sidecar_sha256': file_hash(source / f'checkpoint_state_{TAG}.json'),
        'original_state': original, 'resume_state': state, 'weights_optimizer': 'unchanged hard links',
        'dataset_epoch_zero_based': TRAINER_EPOCH - 1})


def overrides(spec):
    replacements = {'data': spec['data_config'], 'epochs': str(TRAINER_EPOCH),
                    'checkpoint_path': str(OUTPUT), 'resume_checkpoint_path': str(STATE / 'resume'),
                    'resume_checkpoint_tag': TAG, 'training_total_steps': str(END),
                    'stop_after_step': str(END)}
    return [f'{key}={replacements.get(key, value)}'
            for arg in old.overrides() for key, value in [arg.split('=', 1)]] + [f"data.path={spec['data_path']}"]


def evaluation_environment(spec):
    devices = spec.get('evaluation_gpus', '7')
    if (not isinstance(devices, str) or not re.fullmatch(r'[0-7](,[0-7])*', devices)
            or len(set(devices.split(','))) != len(devices.split(','))):
        raise ValueError('Evaluation GPUs must be unique physical indices 0..7')
    return dict(os.environ, CUDA_VISIBLE_DEVICES=devices,
                WANDB_MODE='disabled', WANDB_DISABLED='true')


def review_settings(spec):
    mode = spec.get('review_mode', 'bounded')
    timeout = spec.get('review_timeout', 900)
    if mode not in ('bounded', 'deferred'):
        raise ValueError('Unknown review mode')
    if type(timeout) not in (int, float) or not 0 < timeout <= 1800:
        raise ValueError('Review deadline must be 1..1800 seconds')
    return mode, timeout


def insert(jobs, spec_path, stop_tag):
    if any(j.job_id == JOB for j in jobs):
        raise ValueError('Continuation already inserted')
    original = next(j for j in jobs if j.job_id == old.XXL_JOB)
    command = [sys.executable, str(Path(__file__).resolve()), 'segment', '--spec', str(spec_path), '--',
               str(Path(sys.executable).parent / 'torchrun'), '--nproc_per_node=8', 'pretrain.py',
               *overrides(load(spec_path))]
    train = Job(JOB, Action.TRAIN_UNTIL_STEP, 'training', JOB,
        deps=original.deps, max_retries=0, gpu_policy='all', log_dir=str(STATE / 'xl'),
        metadata={'command': shlex.join(command), 'workdir': str(ROOT), 'ckpt_path': str(OUTPUT),
                  'ckpt_tag': f'step_{END}', 'stop_after_step': END, 'resume_from_tag': TAG,
                  'resume_ckpt_path': str(STATE / 'resume'), 'wandb_project': 'DFM5',
                  'wandb_run_id': old.RUN_ID, 'start_step': START})
    barrier = Job(BARRIER, Action.TERMINAL_BARRIER, 'control', 'XXL-after-reviewed-identity',
                  deps=(JOB,), deps_mode='terminal', log_dir=str(STATE / 'barrier'))
    tokens = shlex.split(original.metadata['command'])
    if sum(t.startswith('resume_checkpoint_tag=') for t in tokens) != 1:
        raise ValueError('Unexpected XXL command')
    tokens = [f'resume_checkpoint_tag={stop_tag}' if t.startswith('resume_checkpoint_tag=') else t for t in tokens]
    resumed = original.with_updates(status=JobStatus.PENDING, attempt=0,
        deps=original.deps + (BARRIER,), log_dir=str(STATE / 'xxl-resume'),
        metadata={**original.metadata, 'command': shlex.join(tokens), 'resume_from_tag': stop_tag})
    result = []
    for job in jobs:
        result.extend([train, barrier, resumed] if job.job_id == old.XXL_JOB else [job])
    return result


def preflight(spec_path):
    spec = load(spec_path)
    if OUTPUT.exists():
        raise ValueError('Identity output must be fresh; refusing an existing checkpoint directory')
    for path, sha in spec['pins'].items():
        if file_hash(path) != sha:
            raise ValueError('Pinned input drift: ' + path)
    if spec['start_step'] != START or spec['end_step'] != END:
        raise ValueError('Wrong continuation span')
    receipt = load(spec['mix_receipt'])
    if receipt['steps'] != 1000 or receipt['packing']['available_optimizer_steps'] < 1000:
        raise ValueError('Insufficient verified optimizer steps')
    if (receipt['start_step'], receipt['stop_after_step'], receipt['data_epoch_index']) != (
            START, END, TRAINER_EPOCH - 1):
        raise ValueError('Mixture continuation contract differs from launch')
    if (receipt['packing']['world_size'], receipt['packing']['gas'], receipt['global_batch']) != (8, 2, 262144):
        raise ValueError('Mixture packing differs from training geometry')
    if abs(receipt['identity_fraction'] - .05) > .0001:
        raise ValueError('Wrong identity fraction')
    if {s['name'] for s in receipt['sources']} != {'DFM11','identity-da','identity-en'}:
        raise ValueError('Wrong source scope')
    for relative, sha in receipt['output_files'].items():
        if file_hash(Path(spec['data_path']) / relative) != sha:
            raise ValueError('Mix artifact drift: '+relative)
    if not (Path(spec['data_path']) / f'epoch_{TRAINER_EPOCH - 1}/inst_start.npy').exists():
        raise ValueError('Missing fresh dataset epoch')
    if not isinstance(spec['evaluation_command'], list) or not spec['evaluation_command']:
        raise ValueError('Evaluation command required')
    evaluation_environment(spec)
    review_settings(spec)
    fresh_resume(SOURCE, STATE / 'resume', spec['data_path'])
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='')
    result = subprocess.run([sys.executable, 'pretrain.py', *overrides(spec), '--cfg', 'job'],
                            cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    (STATE / 'resolved-config.yaml').write_text(result.stdout)
    import yaml
    resolved = yaml.safe_load(result.stdout)
    if Path(resolved['data']['path']).resolve() != Path(spec['data_path']).resolve():
        raise ValueError('Resolved data path mismatch')
    # Use the production resolver on CPU to prove the metadata cursor transition.
    from pretrain import PretrainConfig, resolve_resume_state
    resume = resolve_resume_state(PretrainConfig(**resolved), 16384)
    if (resume.step, resume.start_epoch, resume.skip_batches, resume.start_row_cursor) != (START, TRAINER_EPOCH, 0, 0):
        # Unchanged world size uses the batch cursor, where None is correct.
        if (resume.step, resume.start_epoch, resume.skip_batches, resume.start_row_cursor) != (START, TRAINER_EPOCH, 0, None):
            raise ValueError('Fresh dataset resume resolution failed')
    write_json(STATE / 'preflight.json', {'time': time.time(), 'spec_sha256': file_hash(spec_path),
        'resume': vars(resume), 'start': START, 'end': END, 'overrides': overrides(spec)})
    return spec


def approval_valid(approval, report):
    return (approval.get('decision') == 'approve_full_suite' and approval.get('assessor') == 'parent'
            and bool(approval.get('rationale')) and approval.get('checkpoint_step') == END
            and approval.get('report_sha256') == file_hash(report))


def full_suite(jobs, eval_epoch):
    if any(j.job_id.startswith(PREFIX) for j in jobs):
        raise ValueError('Full suite already inserted')
    start = next(i for i,j in enumerate(jobs) if j.job_id == 'wait-600289')
    end = next(i for i,j in enumerate(jobs) if j.job_id == 'campaign-teardown-dfm10-epoch2')
    template = jobs[start:end+1]
    mapping = {j.job_id: PREFIX+j.job_id for j in template}
    additions = []
    def remap(value):
        if isinstance(value,dict):
            return {mapping.get(k,k):remap(v) for k,v in value.items()}
        if isinstance(value,list):
            return [remap(v) for v in value]
        if isinstance(value,str):
            if value in mapping:
                return mapping[value]
            for oldroot in ('dfm10_XXL_restart520k_half_lr/epoch_2','dfm10_XXL_epoch2_from_dfm8_epoch1/epoch_2'):
                value = value.replace(oldroot, f'{EVAL_ROOT}/step_{END}')
        return value
    for job in template:
        meta = remap(copy.deepcopy(job.metadata))
        meta.update(ckpt_path=str(OUTPUT), ckpt_tag=f'step_{END}', checkpoint_tag=f'step_{END}',
            eval_epoch=eval_epoch, no_ema=True, wandb_project='DFM5', wandb_run_id=old.RUN_ID,
            wandb_run_name='DFM12-XL identity DA-EN 5pct 1000steps', model_prefix=JOB,
            checkpoint_wait_max_seconds=600)
        for key in ('hf_export_dir','standard_hf_export_dir','hrm_hf_export_dir'):
            if key in meta:
                meta[key] = str(ROOT / f'exports/{EVAL_ROOT}_nonema_hf')
        log = str(STATE / 'full-eval' / job.job_id)
        deps = (JOB,) if job.action == Action.WAIT_CHECKPOINT else tuple(mapping[d] for d in job.deps)
        additions.append(job.with_updates(job_id=mapping[job.job_id], deps=deps, attempt=0,
            status=JobStatus.SKIPPED if job.status == JobStatus.SKIPPED else JobStatus.PENDING,
            metadata=meta, log_dir=log))
    result = []
    for job in jobs:
        if job.job_id == BARRIER:
            result.extend(additions)
            job = job.with_updates(deps=(mapping[template[-1].job_id],), deps_mode='terminal')
        result.append(job)
    return result


def apply_full_suite(spec):
    report = Path(spec['evaluation_report'])
    if not approval_valid(load(STATE / 'parent-assessment.json'), report):
        raise ValueError('Explicit parent approval bound to current report required')
    if not complete(OUTPUT, f'step_{END}'):
        raise ValueError('Final checkpoint incomplete')
    # Approximate epoch in original DFM11 token units, never synthetic replay epoch 12.
    total_tokens = load(ROOT / 'data/sampled_dfm11/metadata.json')['total_length']
    epoch = 10 + IDENTITY_STEPS * 262144 / total_tokens
    with PlanLock(old.PLAN):
        jobs = read_plan(old.PLAN / 'plan.tsv')
        if next(j for j in jobs if j.job_id == BARRIER).status != JobStatus.PENDING:
            raise ValueError('Review window closed; refusing late insertion')
        write_plan(old.PLAN / 'plan.tsv', full_suite(jobs, epoch))
    write_json(STATE / 'full-suite-inserted.json', {'eval_epoch': epoch, 'time': time.time(),
        'checkpoint': str(OUTPUT), 'step': END, 'run_id': old.RUN_ID,
        'epoch_basis':f'10 + {IDENTITY_STEPS} * 262144 / DFM11 total_length; nominal token approximation'})


def segment(spec_path, command):
    spec = load(spec_path)
    code = subprocess.run(command, cwd=ROOT).returncode
    if code:
        return code
    try:
        if not complete(OUTPUT, f'step_{END}'):
            raise ValueError('Training did not produce complete final checkpoint')
        write_json(STATE / 'phase.json', {'phase': 'identity_evaluation', 'time': time.time()})
        with (STATE / 'identity-evaluation.log').open('a') as stream:
            evaluation = subprocess.Popen(spec['evaluation_command'], cwd=ROOT,
                stdout=stream, stderr=subprocess.STDOUT, start_new_session=True,
                env=evaluation_environment(spec))
            owned = identity(evaluation.pid)
            write_json(STATE / 'evaluation-process.json', owned)
            try:
                code = evaluation.wait(timeout=spec.get('evaluation_timeout', 7200))
            except subprocess.TimeoutExpired:
                if same_process(owned):
                    os.killpg(evaluation.pid, signal.SIGTERM)
                try:
                    evaluation.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    if same_process(owned):
                        os.killpg(evaluation.pid, signal.SIGKILL)
                    evaluation.wait(timeout=30)
                raise
            if code not in (0, 4):
                raise RuntimeError(f'Identity evaluation exited {code}')
        report = Path(spec['evaluation_report'])
        if not report.exists():
            raise ValueError('Evaluation report missing')
        if load(report).get('status') not in ('complete', 'complete_with_length_stops'):
            raise ValueError('Incomplete evaluation cannot enter approval gate')
        mode, timeout = review_settings(spec)
        if mode == 'deferred':
            write_json(STATE / 'review-deferred.json', {
                'report': str(report), 'report_sha256': file_hash(report),
                'checkpoint_step': END, 'time': time.time(),
                'full_suite': 'Not approved; later review requires a separate safe handoff'})
            return 0
        deadline = time.time() + timeout
        write_json(STATE / 'phase.json', {'phase':'awaiting_parent_assessment', 'deadline':deadline,
                   'report':str(report), 'report_sha256':file_hash(report)})
        while time.time() < deadline:
            decision = STATE / 'parent-assessment.json'
            if decision.exists():
                approval = load(decision)
                if approval_valid(approval, report):
                    apply_full_suite(spec)
                else:
                    write_json(STATE / 'full-suite-not-approved.json', {'assessment':approval})
                break
            time.sleep(3)
        else:
            write_json(STATE / 'review-timeout.json', {'deadline':deadline})
    except Exception as exc:
        write_json(STATE / 'evaluation-error.json', {'error':repr(exc), 'time':time.time()})
    finally:
        write_json(STATE / 'phase.json', {'phase':'scheduler_barrier_released', 'time':time.time()})
    return 0


def handoff(spec_path, arm):
    STATE.mkdir(parents=True, exist_ok=True)
    with lock(STATE / '.handoff.lock'):
        if (STATE / 'scheduler-resumed.json').exists():
            raise ValueError('Already handed off')
        spec = preflight(spec_path)
        spec_sha256 = file_hash(spec_path)
        jobs = read_plan(old.PLAN / 'plan.tsv')
        current = next(j for j in jobs if j.job_id == old.XXL_JOB)
        if current.status != JobStatus.RUNNING:
            raise ValueError('XXL must be the current running job')
        process = load(Path(current.log_dir) / 'train_until_step_700000.process.json')
        owned = identity(process['process_group'])
        if owned['pgid'] != owned['pid'] or b'schedule_dfm11_epoch3.py' not in bytes.fromhex(owned['cmdline']):
            raise ValueError('Unexpected XXL process')
        runners = []
        for p in Path('/proc').glob('[0-9]*/cmdline'):
            try:
                argv = p.read_bytes().split(b'\0')
                if b'eval_scheduler' in argv and b'run' in argv and any(old.PLAN.name.encode() in x for x in argv):
                    runners.append(identity(int(p.parent.name)))
            except (FileNotFoundError, ProcessLookupError, RuntimeError):
                pass
        if len(runners) != 1 or (old.PLAN / 'stop.request').exists():
            raise ValueError('Unexpected scheduler state')
        stop_tag = spec['xxl_stop_tag']
        if not re.fullmatch(r'ephemeral_step_\d+', stop_tag):
            raise ValueError('Ephemeral stop tag required')
        stop_step = int(stop_tag.rsplit('_', 1)[1])
        if stop_step % 500 or (old.XXL / f'checkpoint_state_{stop_tag}.json').exists():
            raise ValueError('Choose a future unwritten 500-step checkpoint boundary')
        insert(jobs, spec_path, stop_tag)
        if not arm:
            print('Preflight passed; scheduler and processes unchanged', flush=True)
            return
        release = load(spec['teacher_release'])
        if not (release.get('released') or
                (release.get('only_exact_owned_pids') is True and release.get('survivors') == [])):
            raise ValueError('Teacher owner release not confirmed')
        subprocess.run([sys.executable,'-m','eval_scheduler','stop','--plan-dir',str(old.PLAN)],check=True)
        own_stop = (old.PLAN / 'stop.request').read_bytes()
        write_json(STATE / 'handoff.json', {'phase':'waiting_checkpoint','tag':stop_tag,
                   'training':owned,'runner':runners[0]})
        deadline = time.monotonic() + 7200
        while not complete(old.XXL, stop_tag):
            if not same_process(owned) or time.monotonic() > deadline:
                raise RuntimeError('Checkpoint wait timed out or XXL identity changed')
            time.sleep(2)
        backup = ROOT / 'checkpoints/preserved' / f'xxl-before-identity-expanded-{stop_tag}'
        if not complete(backup, stop_tag):
            preserve(old.XXL, backup, stop_tag)
        if file_hash(spec_path) != spec_sha256:
            raise RuntimeError('Launch specification changed during checkpoint wait; XXL not signalled')
        # Recheck artifact pins after the wait, before stopping the live training.
        preflight(spec_path)
        if file_hash(spec_path) != spec_sha256:
            raise RuntimeError('Launch specification changed during final preflight; XXL not signalled')
        if (old.PLAN / 'stop.request').read_bytes() != own_stop:
            raise RuntimeError('Stop ownership changed before signal')
        if not same_process(owned):
            raise RuntimeError('XXL identity changed before signal')
        os.killpg(owned['pid'], signal.SIGTERM)
        wait_until(lambda: not same_process(owned) and not same_process(runners[0]),300,'XXL/scheduler exit timeout')
        wait_until(gpu_free,300,'GPU release timeout; no unrelated processes signalled')
        if (old.PLAN / 'stop.request').read_bytes() != own_stop:
            raise RuntimeError('Stop ownership changed')
        with PlanLock(old.PLAN):
            jobs = read_plan(old.PLAN / 'plan.tsv')
            shutil.copy2(old.PLAN / 'plan.tsv', STATE / 'plan.before.tsv')
            write_plan(old.PLAN / 'plan.tsv', insert(jobs,spec_path,stop_tag))
        subprocess.run([sys.executable,'-m','eval_scheduler','clear-stop','--plan-dir',str(old.PLAN)],check=True)
        with (STATE / 'runner.log').open('a') as stream:
            proc = subprocess.Popen([sys.executable,'-u','-m','eval_scheduler','run','--plan-dir',str(old.PLAN),
                '--gpus','0,1,2,3,4,5,6,7','--persistent-vllm'],stdin=subprocess.DEVNULL,
                stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        write_json(STATE / 'scheduler-resumed.json', {'runner':identity(proc.pid),'next_job':JOB,'tag':stop_tag})


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('mode',choices=['handoff','segment','insert-full-eval'])
    parser.add_argument('--spec',type=Path,required=True)
    parser.add_argument('--arm',action='store_true')
    args, command = parser.parse_known_args()
    os.chdir(ROOT)
    os.environ['PATH'] = str(Path(sys.executable).parent) + ':' + os.environ['PATH']
    configure(load(args.spec))
    if args.mode == 'segment':
        return segment(args.spec,command[1:] if command[:1]==['--'] else command)
    if args.mode == 'insert-full-eval':
        apply_full_suite(load(args.spec))
    else:
        handoff(args.spec.resolve(),args.arm)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
