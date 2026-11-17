"""Run the prepared DFM11 recipe only after exact corrected DFM10 verification."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.acquire_dfm10_hf import save
from scripts.dfm_hf_gate import require_dfm10, digest
from scripts import rebuild_dfm11 as recipe
from scripts import queue_dfm_hf_rebuild as queue_driver


def run():
    work = recipe.QUEUE / 'dfm11'
    schedule_path = work / 'schedule.json'
    schedule = json.loads(schedule_path.read_text())
    receipt = work / 'scheduled-progress.json'
    state = json.loads(receipt.read_text()) if receipt.exists() else {'completed': []}
    with (work / 'scheduled-runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            while True:
                if digest(recipe.CONFIG) != schedule['config_sha256']:
                    raise ValueError('Prepared DFM11 recipe changed after scheduling')
                try:
                    predecessor = require_dfm10(recipe.QUEUE)
                except FileNotFoundError:
                    state.update(status='waiting', phase='DFM10 exact HF-only verification')
                    save(receipt, state)
                    time.sleep(30)
                    continue
                break
            if 'predecessor' in state and state['predecessor'] != predecessor:
                raise ValueError('Verified predecessor changed since DFM11 began')
            state['predecessor'] = predecessor
            for stage in schedule['stages']:
                if require_dfm10(recipe.QUEUE) != predecessor:
                    raise ValueError('DFM10 predecessor changed')
                if stage in state['completed']:
                    continue
                state.update(status='running', phase=stage)
                state.pop('error', None)
                save(receipt, state)
                if stage == 'compare':
                    queue_driver.compare(recipe.QUEUE, 11)
                else:
                    if stage == 'acquire':
                        cmd=[sys.executable, str(ROOT/'scripts/rebuild_dfm11.py'), stage, '--work', str(work)]
                    else:
                        cmd=queue_driver.dfm11_command(recipe.QUEUE, stage)
                    subprocess.run(cmd, cwd=ROOT, check=True, env=dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1'))
                state['completed'].append(stage)
                save(receipt, state)
            state.update(status='matched', phase='complete')
            save(receipt, state)
        except Exception as exc:
            state.update(status='blocked', error=str(exc))
            save(receipt, state)
            raise


if __name__ == '__main__':
    run()
