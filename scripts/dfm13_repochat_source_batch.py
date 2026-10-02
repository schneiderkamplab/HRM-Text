"""Small rate-budgeted CPU source batch; no inference or admission."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
from pathlib import Path

from scripts import dfm13_repochat_source_recovery as sources

r = sources.recovery
b = r.b
ROOT = Path('data/dfm13/repochat-source-batch-20261001-v1')


def select(plan, maximum):
    groups = {}
    for job in plan['jobs']:
        if job['kind'] != 'source':
            continue
        error = job['source_failure'].get('error', '')
        if not any(x in error for x in ('rate limit exceeded', 'RemoteDisconnected', 'HTTP Error 401')):
            continue
        task = job['task']; key = (task['repository'].lower(), tuple(task['source_suffix']))
        groups.setdefault(key, []).append(job)
    ordered = sorted(groups.values(), key=lambda g: ('rate limit exceeded' not in g[0]['source_failure'].get('error', ''), g[0]['id']))
    return ordered[:maximum]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--max-sources', type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.max_sources <= 12:
        parser.error('bounded batch allows 1..12 distinct sources')
    args.root.mkdir(parents=True, exist_ok=True)
    with (args.root / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = r.prepare(r.ROOT); groups = select(plan, args.max_sources)
        manifest = {'groups': groups, 'pins': [r.pin(__file__), r.pin(sources.__file__), r.pin(r.ROOT / 'plan.json')],
                    'workers': 2, 'maximum_api_calls_per_source_without_retries': 3,
                    'inference': False, 'admission': False}
        path = args.root / 'manifest.json'
        if path.exists() and b.load(path) != manifest:
            raise ValueError('source batch manifest drift')
        b.save(path, manifest)
        fetcher = sources.Fetcher(args.root)
        quota = json.loads(fetcher.fetch('https://api.github.com/rate_limit', 1_000_000))['resources']['core']
        b.save(args.root / 'quota-preflight.json', {'core': quota, 'environment_auth_available': bool(fetcher.token)})
        if quota['remaining'] < 3 * len(groups) + 5:
            raise ValueError('insufficient API budget; no source requests started')
        results = []
        with ThreadPoolExecutor(max_workers=2) as pool:
            for group, result in zip(groups, pool.map(lambda g: sources.resolve(g[0], args.root, fetcher), groups)):
                results.append({'task_ids': [j['id'] for j in group], 'source': result})
                b.save(args.root / 'progress.json', {'completed_sources': len(results), 'total_sources': len(groups),
                    'ready_sources': sum(x['source']['status'] == 'source_ready' for x in results),
                    'covered_tasks': sum(len(x['task_ids']) for x in results), 'inference': False, 'admission': False})
        b.save(args.root / 'completion.json', {'results': results, 'manifest_sha256': b.file_sha(path),
                                             'inference': False, 'admission': False})


if __name__ == '__main__':
    main()
