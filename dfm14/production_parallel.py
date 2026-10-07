"""Run multiple independently locked synthesis chunks per shared endpoint."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path
import typer

from dfm12.io import file_hash, load, lock, write_json
from dfm14.production import ROOT, pins, worker

app = typer.Typer()


@app.command()
def run(root: Path = ROOT, concurrency: int = 256):
    if concurrency not in (128, 256):
        raise ValueError('Supported per-server concurrency: 128 or 256')
    with lock(root/'.controller.lock'):
        manifest = load(root/'manifest.json')
        if manifest['code_pins'] != pins():
            raise ValueError('Production code changed')
        if file_hash(root/'authorization.json') != manifest['authorization_sha256']:
            raise ValueError('Approval changed')
        if not load(root/'authorization.json')['production_authorized']:
            raise ValueError('No owner authorization')
        if not (root/'seed-manifest.json').exists():
            raise ValueError('Seeds not ready')
        streams = concurrency // 128
        write_json(root/'state.json',dict(phase='running',pid=os.getpid(),
            concurrency_per_endpoint=concurrency,streams_per_endpoint=streams,
            concurrency_per_stream=128,launcher_sha256=file_hash(Path(__file__))))
        with ProcessPoolExecutor(max_workers=8*streams) as pool:
            futures = [pool.submit(worker,root,f'http://127.0.0.1:{port}/v1',128)
                       for port in range(8800,8808) for _ in range(streams)]
            for future in futures: future.result()
        counts=Counter(); shortfall=0
        for path in (root/'jobs').glob('*/receipt.json'):
            receipt=load(path); counts.update(receipt['counts']); shortfall+=receipt['shortfall']
        write_json(root/'state.json',dict(phase='finished_attempts',counts=dict(counts),
            shortfall=shortfall,training_ready=False,
            remaining=['cross-shard/inherited deduplication','accepted-only export','tokenization']))


if __name__ == '__main__': app()
