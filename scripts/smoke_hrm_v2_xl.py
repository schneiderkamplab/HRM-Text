"""Full-size, five-step v2 migration/FA4/compile smoke without W&B logging."""
import os
from pathlib import Path
import subprocess

from prepare_hrm_v2_xl import ROOT, command
from stop_training_at_complete_checkpoint import complete


def main():
    output = ROOT / 'logs/training/hrm_v2/cuda_smoke/checkpoints'
    if output.exists():
        raise RuntimeError('Smoke output already exists; inspect it before retrying')
    argv = command('v2', 3800005)
    changes = {'checkpoint_path': str(output), 'memory_log_interval': '1'}
    argv = [f'{arg.split("=", 1)[0]}={changes[arg.split("=", 1)[0]]}'
            if '=' in arg and arg.split('=', 1)[0] in changes else arg for arg in argv]
    env = dict(os.environ, WANDB_MODE='disabled', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
               PATH='/home/ucloud/miniforge3/envs/hrm/bin:' + os.environ['PATH'])
    subprocess.run(argv, cwd=ROOT, env=env, check=True)
    if not complete(output, 'step_3800005'):
        raise RuntimeError('Smoke did not save its full final checkpoint')
    print('Full-size CUDA smoke completed and final checkpoint verified.', flush=True)


if __name__ == '__main__':
    main()
