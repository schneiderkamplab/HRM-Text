"""Prepare a reproducible six-family calibration for all eleven wave-four languages."""
import json
from pathlib import Path

from . import wave4_synthetic_specs as provider
from .io import atomic, file_hash, load, lock, write_json
from .wave4_cpu import LANGUAGES


def main():
    root = Path('data/dfm13/wave4/calibration')
    seeds = Path('data/dfm13/wave4/seeds')
    pin = load(seeds/'receipt.json')
    if not pin['ready'] or file_hash(seeds/'seeds.sqlite') != pin['sha256']:
        raise ValueError('Seeds not ready or changed')
    with lock(root/'prepare.lock'):
        output = root/'generation-requests.jsonl'
        if (root/'prepared.json').exists():
            if file_hash(output) != load(root/'prepared.json')['sha256']:
                raise ValueError('Prepared requests changed')
            return
        allocator = provider.SourceProvider(seeds,root,
            dict(campaign='dfm13-wave4-calibration-v1',languages=list(LANGUAGES)))
        count = 0
        try:
            with atomic(output) as out:
                for language in LANGUAGES:
                    for family in ('multiturn','grounded-instruct','openhermes',
                                   'summary-rewrite','math-code','tool-dialogue'):
                        for slot in range(10):
                            spec = allocator.next_spec(language,family,slot)
                            out.write(json.dumps(dict(spec=spec,request=provider.request(spec)),ensure_ascii=False)+'\n')
                            count += 1
        finally:
            allocator.close()
        write_json(root/'prepared.json',dict(rows=count,sha256=file_hash(output),
            seeds_sha256=pin['sha256'],languages=list(LANGUAGES),production_approved=False))
        print(count, flush=True)


if __name__ == '__main__':
    main()
