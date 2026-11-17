"""Install DFM3 after the active coordinator releases its lock, then run guarded."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    queue = ROOT / 'data/rebuild_hf_dfm/serial-queue'
    env = {**os.environ, 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
           'OPENBLAS_NUM_THREADS': '1', 'TOKENIZERS_PARALLELISM': 'false'}
    subprocess.run([sys.executable, '-m', 'scripts.queue_dfm_hf_rebuild',
                    'enable-dfm3', '--queue', str(queue)], cwd=ROOT, env=env, check=True)
    subprocess.run([sys.executable, '-u', str(ROOT / 'scripts/watch_dfm_rebuild_io.py'),
                    '--queue', str(queue), '--log-dir',
                    str(ROOT / 'logs/analysis/dfm3-hf-rebuild-20261020')],
                   cwd=ROOT, env=env, check=True)


if __name__ == '__main__':
    main()
