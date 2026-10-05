"""Serialize remaining-language integration after Baltic/TLPC promotion."""
from pathlib import Path
import time
from dfm12.io import load, write_json
from scripts.queue_dala_compact_assembly import run


def main():
    finalized = Path('data/dfm13/dala-baseline-delta-finalized-20261004-v1')
    output = Path('data/dfm13/verified-all-finished-additions-dala-baseline-20261004-v1')
    control = output.with_name(output.name+'-control')
    while True:
        reference = load('data/dfm13/authoritative-additions.json')
        ready = Path(reference['root']).name == 'verified-all-finished-additions-wave4-20261004-v1'
        complete = (finalized/'complete.json').exists()
        write_json(control/'waiting.json', dict(predecessor_ready=ready, finalization_ready=complete,
                                               time=time.time(), gpu_actions=False))
        if ready and complete:
            if not load(finalized/'complete.json')['success']:
                raise ValueError('Remaining DaLA finalization failed; preserve predecessor')
            break
        time.sleep(30)
    run(finalized, output)


if __name__ == '__main__':
    main()
