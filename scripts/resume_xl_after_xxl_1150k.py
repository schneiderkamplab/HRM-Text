"""Full-stop the parked XXL workers, then resume the transferred XL checkpoint."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from training_suspend.protocol import atomic_write, validate_process
from stop_training_at_complete_checkpoint import complete
from run_dfm15_xl_extension import command as extension_command

ARCHIVE = ROOT / 'incoming/mimir-xl-20261015'
SOURCE = ARCHIVE / 'checkpoints/dfm15/XL-from-dfm14-epoch1'
DATA = ARCHIVE / 'data/sampled_dfm15'
OUTPUT = ROOT / 'checkpoints/dfm15/XL-from-dfm14-epoch1'
CONTROL = ROOT / 'logs/training/dfm14_XXL_wide/cooperative_1m_to_epoch3'
CONTROL_CHECKPOINTS = ROOT / 'checkpoints/hrm_v2/hrm-control-XL-from-3800000'


def resume_source():
    candidates = []
    for sidecar in CONTROL_CHECKPOINTS.glob('checkpoint_state_*.json'):
        tag = sidecar.stem.removeprefix('checkpoint_state_')
        state = json.loads(sidecar.read_text())
        step = state.get('step', 0)
        if 3800000 < step <= 3820000 and complete(CONTROL_CHECKPOINTS, tag):
            candidates.append((step, tag))
    if candidates:
        return CONTROL_CHECKPOINTS, max(candidates)[1]
    return SOURCE, 'step_3800000'


def command():
    source, tag = resume_source()
    changes = {
        'data.path': str(DATA), 'checkpoint_path': str(OUTPUT),
        'resume_checkpoint_path': str(source), 'resume_checkpoint_tag': tag,
        'stop_after_step': '3850000', 'training_total_steps': '3850000',
    }
    return [f'{arg.split("=", 1)[0]}={changes[arg.split("=", 1)[0]]}'
            if '=' in arg and arg.split('=', 1)[0] in changes else arg
            for arg in extension_command(SOURCE)]


def preflight():
    import numpy as np
    source, tag = resume_source()
    if not complete(source, tag):
        raise RuntimeError('Selected XL continuation checkpoint is incomplete')
    state = json.loads((source / f'checkpoint_state_{tag}.json').read_text())
    assert 3800000 <= state['step'] <= 3820000
    assert (state['epoch'], state['world_size'],
            state['gradient_accumulation_steps'], state['carry_policy']) == (1, 8, 2, 'none')
    metadata = json.loads((DATA / 'metadata.json').read_text())
    assert metadata['total_length'] == 134516139170
    for name in ('local-transfer-verified.json', 'full-mixture-verified.json',
                 'math-answer-conditioning-verified.json'):
        assert (DATA / name).is_file(), name
    lengths = [len(np.load(DATA / 'epoch_0' / f'{name}.npy', mmap_mode='r'))
               for name in ('inst_start', 'inst_len', 'resp_start', 'resp_len')]
    assert len(set(lengths)) == 1 and lengths[0] > state['global_row_cursor_in_epoch']
    tokens = np.load(DATA / 'tokens.npy', mmap_mode='r')
    assert tokens.ndim == 1 and tokens.size > 0
    print(f'XL checkpoint and transferred data preflight passed: {source}:{tag}', flush=True)


def alive(identity):
    try:
        validate_process(identity)
        return True
    except (FileNotFoundError, ProcessLookupError, RuntimeError):
        return False


def stop_xxl():
    checkpoint = ROOT / 'checkpoints/dfm14/XXL-wide-from-dfm13-step870000'
    if not complete(checkpoint, 'step_1150000'):
        raise RuntimeError('Refusing to stop XXL before its complete 1.15M checkpoint')
    identity = json.loads((CONTROL / 'launcher.json').read_text())['identity']
    # The owning supervisor performs identity-checked descendant cleanup.
    atomic_write(CONTROL / 'stop.request', 'Full stop after 1150K evaluations; switch to XL\n')
    deadline = time.monotonic() + 300
    while alive(identity):
        if time.monotonic() >= deadline:
            raise RuntimeError('XXL supervisor has not completed full shutdown')
        time.sleep(2)


def main():
    preflight()
    if '--preview' in sys.argv:
        print(json.dumps(command(), indent=2))
        return
    stop_xxl()
    os.environ['OMP_NUM_THREADS'] = os.environ['MKL_NUM_THREADS'] = '1'
    os.environ['PATH'] = '/home/ucloud/miniforge3/envs/hrm/bin:' + os.environ['PATH']
    # This handoff selects the latest completed control checkpoint at launch time.
    allowed = {'stop_after_step=3850000'}
    if not set(sys.argv[1:]) <= allowed:
        raise ValueError('Unexpected scheduler overrides')
    subprocess.run(command(), cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
