"""Finish an isolated pilot and export its EMA before releasing evaluation jobs."""
import argparse
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--tokenizer-reference', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command[:1] == ['--']:
        command = command[1:]
    if not command:
        parser.error('Training command required after --')
    root = Path(__file__).resolve().parents[1]
    subprocess.run(command, cwd=root, check=True)
    env = {**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'OMP_NUM_THREADS': '1'}
    subprocess.run([
        '/home/ucloud/miniforge3/envs/mimir2/bin/python',
        str(root / 'scripts/export_mimir2_dcp.py'),
        '--checkpoint', args.checkpoint, '--tag', 'step_3820000',
        '--output', args.output, '--tokenizer-reference', args.tokenizer_reference,
    ], cwd=root, env=env, check=True)


if __name__ == '__main__':
    main()
