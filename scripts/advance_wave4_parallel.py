"""Resume direct preparation, then freeze English legs and queue audited pivots."""
from pathlib import Path
import subprocess
import sys

from dfm12.baltic_pivots import main as build_pivots
from dfm12.io import file_hash, load, lock, write_json
from dfm12.wave4_cpu import enqueue


def main():
    root = Path('data/dfm13/wave4')
    with lock(root / 'advance-parallel.lock'):
        for stage in ('parallel', 'institutional'):
            print('RESUME', stage, flush=True)
            subprocess.run([sys.executable, '-u', '-m', 'dfm12.wave4_cpu', stage,
                '--root', str(root), '--workers', '8'], check=True)
        print('BUILD exact English pivots', flush=True)
        build_pivots(root)
        queued = []
        for receipt in sorted((root / 'pivots/candidates').glob('opus-*/receipt.json')):
            state = load(receipt)
            if state['state'] != 'pivot_candidates_ready':
                continue
            path = receipt.parent / 'candidates.jsonl'
            if file_hash(path) != state['sha256']:
                raise ValueError('Pivot output changed')
            component = 'pivot-' + state['pair']
            enqueue(root, component, path)
            queued.append(component)
        from dfm12.wave_job_coverage import reconcile
        reconcile(root)
        write_json(root / 'parallel-preparation.json', dict(
            status='direct_and_pivot_preparation_finished', queued_pivots=queued,
            coverage_report=str(root / 'pivots/manifest.json'),
            remaining=['audit', 'accepted-only combined token budgets', 'export/upload/integration']))


if __name__ == '__main__':
    main()
