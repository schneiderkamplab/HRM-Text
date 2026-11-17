"""Sequential DFM10 continuation: await HF unpack, map, stage, tokenize, verify.

Stops on incomplete mapping or any mismatch; never promotes production data.
Receipts keep completed stages from being restarted.
"""
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.acquire_dfm10_hf import DEFAULT, save


def busy(path):
    with path.open('a') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        return False


def sample_command(work):
    command = [sys.executable, str(ROOT/'data_io/sample_tokenized.py'),
               f'tokenized_path={work / "union"}', f'output_path={work / "sampled"}',
               f'prefix_config_path={work / "prefix_config.yaml"}',
               'epochs=10', 'seed=0', 'concat_workers=4', 'default_long_context=drop']
    if (work/'sampled/tokens.npy').exists():
        command.append('reuse_tokens=true')
    return command


def run():
    work = ROOT / 'data/rebuild_hf_dfm/serial-queue/dfm10-hf-v2'
    work.mkdir(exist_ok=True)
    receipt = work / 'continuation.json'
    state = json.loads(receipt.read_text()) if receipt.exists() else {'completed': []}
    with (work / 'continuation.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            while busy(DEFAULT / 'acquire.lock') or busy(DEFAULT / 'unpack.lock'):
                state['phase'] = 'awaiting_acquisition_and_unpack'
                save(receipt, state)
                time.sleep(20)
            if not json.loads((DEFAULT / 'acquisition-progress.json').read_text())['complete']:
                raise ValueError('Acquisition stopped before completion')
            commands = [('unpack', [sys.executable, str(ROOT/'scripts/unpack_dfm10_hf.py')]),
                        ('materialize', [sys.executable, str(ROOT/'scripts/materialize_dfm10_hf.py')])]
            commands += [(stage, [sys.executable, str(ROOT/'scripts/rebuild_dfm10.py'), stage, '--work', str(work), '--config', str(work/'hf_recipe.json')]) for stage in ('prepare','tokenize','assemble','verify')]
            index=next(i for i,(name,_) in enumerate(commands) if name=='verify')
            commands.insert(index,('restore-limits',[sys.executable,str(ROOT/'scripts/restore_dfm10_token_limits.py'),'--work',str(work),'--config',str(work/'hf_recipe.json')]))
            index=next(i for i,(name,_) in enumerate(commands) if name=='verify')
            commands.insert(index,('restore-swe-targets',[sys.executable,str(ROOT/'scripts/restore_dfm10_swe_targets.py'),'--work',str(work),'--config',str(work/'hf_recipe.json')]))
            commands += [('sample', sample_command(work)), ('compare', [sys.executable, str(ROOT/'scripts/compare_dfm10_hf.py')])]
            for stage, command in commands:
                if stage in state['completed']:
                    continue
                state.pop('error',None)
                state.update(phase=stage, status='running')
                save(receipt, state)
                if stage=='sample':save(work/'sample-command.json',command)
                subprocess.run(command, cwd=ROOT, check=True)
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
