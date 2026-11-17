"""Pinned, resumable acquisition of approved DFM16 candidates; no sampling."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import time

from huggingface_hub import HfApi, snapshot_download
from dfm12.io import load, lock, write_json

ROOT = Path('data/dfm16/expansion-v1')
CONFIG = Path('config/dfm16_expansion.json')


def acquire(repo, root):
    out = root/'downloads'/repo.replace('/', '__')
    with lock(out/'.acquire.lock'):
        pin = out/'source.json'
        try:
            if pin.exists():
                info = load(pin)
            else:
                source = HfApi().dataset_info(repo, files_metadata=True)
                info = dict(repo_id=repo, revision=source.sha,
                    files=[dict(path=f.rfilename, bytes=f.size) for f in source.siblings],
                    license_reported=(source.card_data or {}).get('license'))
                write_json(pin, info)
            write_json(out/'status.json', dict(phase='downloading', time=time.time()))
            path = snapshot_download(repo, repo_type='dataset', revision=info['revision'],
                local_dir=out/'snapshot', max_workers=4,
                allow_patterns=['*.parquet', '*.jsonl', '*.json', '*.jsonl.gz', '*.csv', '*.tsv',
                                '*.txt', '*.md', '*.yaml', '*.yml', '*.py', 'LICENSE*'])
            result = dict(phase='downloaded', repo_id=repo, snapshot=path,
                          revision=info['revision'], training_ready=False, time=time.time())
        except Exception as exc:
            result = dict(phase='blocked', repo_id=repo, error=f'{type(exc).__name__}: {exc}',
                          training_ready=False, time=time.time())
        write_json(out/'status.json', result)
        print(result, flush=True)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--only', nargs='*')
    args = parser.parse_args()
    config = load(CONFIG)
    repos = config['simple_stories']['sources'] + [s['repo_id'] for s in config['sources']]
    if args.only:
        if set(args.only)-set(repos):
            parser.error('Unknown source requested')
        repos = args.only
    with lock(args.root/'.acquisition.lock'):
        results = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(acquire, repo, args.root) for repo in repos]
            for future in as_completed(futures):
                results.append(future.result())
                write_json(args.root/'acquisition.json', dict(results=results, pending=len(repos)-len(results)))


if __name__ == '__main__':
    main()
