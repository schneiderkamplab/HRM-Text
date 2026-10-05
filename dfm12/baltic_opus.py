"""CPU-only Baltic translation discovery and audited-candidate preparation."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
from pathlib import Path

from . import opus
from .european_expansion import configuration as european_configuration
from .european_opus import review
from .io import file_hash, load, lock, write_json
from .prepare import Renderer


class BridgeRenderer:
    """Auxiliary English legs are not training examples; validate only final joins."""
    info = {'bridge_only': True, 'native_rendering': 'deferred_until_pivot_candidate'}

    def count(self, messages):
        return 0


def prepare_one(job):
    root,pair,item,cfg=job
    requested={tuple(p) for p in cfg['requested_pairs']}
    bridge_only=tuple(pair.split('-')) not in requested
    if item.get('error'):
        state=dict(state='discovery_failed',error=item['error'])
    elif not any(e.get('status')=='approved' for e in item['corpora']):
        state=dict(state='english_pivot_required',audit='pending')
    else:
        try:
            receipt=root/'candidates'/('opus-'+pair)/'receipt.json'
            if receipt.exists():
                result=load(receipt)
                if file_hash(receipt.parent/'candidates.jsonl')!=result['sha256']:
                    raise ValueError('Candidate checksum mismatch')
            else:
                render=BridgeRenderer() if bridge_only else Renderer(load('data/sampled_dfm11/metadata.json')['tokenizer_info'],4096)
                result=opus.prepare_pair(root,pair,cfg,render)
            state=dict(state='bridge_only' if bridge_only else 'direct_candidates_ready',
                       counts=result['counts'],audit='pending')
        except Exception as exc:
            state=dict(state='preparation_failed',error=str(exc))
    write_json(root/'opus/progress'/(pair+'.json'),state)
    print(pair,state,flush=True)
    return state


def configuration():
    cfg = european_configuration()
    cfg['languages'].update(lt='Lithuanian', lv='Latvian')
    requested = [list(p) for p in combinations(sorted(cfg['languages']), 2)
                 if {'lt', 'lv'} & set(p)]
    # English legs are required even when the requested edge is non-English.
    legs = [sorted(['en', lang]) for lang in cfg['languages'] if lang != 'en']
    cfg.update(sources={}, requested_pairs=requested,
               opus_pairs=sorted({tuple(p) for p in requested + legs}))
    cfg['pair_budgets'] = {
        '-'.join(pair): {
            'baseline': 'sampled repaired English-Danish tokens',
            'fraction': cfg['english_translation_fraction'] if 'en' in pair else cfg['other_translation_fraction'],
            'directions': 'combined',
            'routes': 'direct and English-pivot combined',
            'shortfall': 'report; do not increase repeats',
        } for pair in requested
    }
    return cfg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/dfm13/baltic/translations'))
    args = parser.parse_args()
    root = args.root
    cfg = configuration()
    with lock(root / '.campaign.lock'):
        write_json(root / 'config.json', cfg)
        opus.discover(root, cfg)
        review(root)
        inventory = load(root / 'opus/inventory.json')
        inventory['policy'] = 'direct preferred; English pivot fallback authorized; audit required'
        write_json(root / 'opus/inventory.json', inventory)
        with ProcessPoolExecutor(max_workers=8) as pool:
            result=list(pool.map(prepare_one,[(root,pair,item,cfg) for pair,item in inventory['pairs'].items()]))
        write_json(root/'preparation.json',dict(pairs=result,complete=not any(s['state'].endswith('failed') for s in result)))


if __name__ == '__main__':
    main()
