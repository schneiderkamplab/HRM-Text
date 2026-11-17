import os
from pathlib import Path
import subprocess
import sys


def test_scheduler_import_and_cli_from_repo_root():
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    subprocess.run([sys.executable, '-c',
                    'from eval_scheduler.model import Job; '
                    'from eval_scheduler.store import SQLiteJobStore; '
                    'from scripts.b_dfm15_epoch2_switch import command'],
                   cwd=root, env=env, check=True, capture_output=True, timeout=60)
    result = subprocess.run([sys.executable, '-m', 'eval_scheduler', '--help'],
                            cwd=root, env=env, check=True, capture_output=True,
                            text=True, timeout=60)
    assert 'run' in result.stdout
