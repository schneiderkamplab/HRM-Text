"""Finalize terminal languages absent from the first DaLA compact release."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import os
from pathlib import Path
from dfm12 import dala_compact_finalize as f


def run(root, previous, workers):
    os.environ.update(CUDA_VISIBLE_DEVICES='', TOKENIZERS_PARALLELISM='false', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    with f.lock(root/'.lock'):
        old = f.load(previous/'registry.json')
        covered = {e['language'] for e in old['additions']}
        config = f.load(f.AUDITS[1]/'config.json')
        if f.file_hash(config['manifest']) != config['manifest_sha256']:
            raise ValueError('Audit manifest drift')
        groups = {}
        for source in f.sources_from(f.load(config['manifest'])):
            if source['language'] not in covered:
                groups.setdefault(source['language'], []).append(source)
        plan = dict(previous=f.pin(previous/'registry.json'), languages=sorted(groups),
                    workers=workers, code=f.pin(__file__), finalizer=f.pin(f.__file__),
                    deferred_duplicate_pools=['nl:baseline', 'fa:baseline'])
        if (root/'plan.json').exists() and f.load(root/'plan.json') != plan:
            raise ValueError('Resume plan drift')
        f.write_json(root/'plan.json', plan)
        universe = f.load(f.ALL_INPUTS)['sources']
        completed, errors = [], []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {}
            for language, sources in sorted(groups.items()):
                target = root/'groups'/(language+'-baseline')
                if (target/'integration.json').exists():
                    completed.append(f.load(target/'integration.json'))
                    continue
                if not (target/'snapshot.json').exists():
                    if f.snapshot(f.AUDITS[1], sources, target) is None:
                        raise ValueError('Nonterminal source: '+language)
                print('SNAPSHOT', language, flush=True)
                futures[pool.submit(f.finalize, (str(target.resolve()), universe, True))] = language
            for future in as_completed(futures):
                language = futures[future]
                try:
                    completed.append(future.result())
                except Exception as exc:
                    errors.append(dict(language=language, error=repr(exc)))
                entries = [e for result in completed for e in result['components']]
                f.write_json(root/'registry.json', dict(schema=f.CONTRACT, additions=entries, local_only=True))
                f.write_json(root/'progress.json', dict(completed=len(completed), selected=len(groups), errors=errors))
                print('PROGRESS', len(completed), len(groups), errors, flush=True)
        f.write_json(root/'complete.json', dict(success=not errors, completed=len(completed), errors=errors,
                     registry=f.pin(root/'registry.json'), waiting=[], gpu_actions=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--previous', type=Path, required=True)
    p.add_argument('--workers', type=int, choices=range(1, 9), default=8)
    a = p.parse_args()
    run(a.root, a.previous, a.workers)
