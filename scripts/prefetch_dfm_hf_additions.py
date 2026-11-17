"""Prefetch declared later-DFM Hub inputs independently of serial rebuilds.

Only repository inventories/registries are consulted, never local data payloads.
This inventory is not proof of a complete historical dependency closure.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import json
from pathlib import Path
import subprocess
import sys

from huggingface_hub import HfApi, snapshot_download

from scripts.download_training_datasets import HF_DATASETS
from scripts.replay_dfm_serial import write_json

ROOT = Path(__file__).resolve().parents[1]


def inventory(base_manifest):
    entries = {}

    def add(repo, revision, origin, patterns=None):
        if not repo or '/' not in repo:
            raise ValueError(f'Invalid Hub repository: {repo}')
        key = (repo, revision)
        row = entries.setdefault(key, dict(repo_id=repo, requested_revision=revision,
                                          origins=[], allow_patterns=patterns, status='pending'))
        row['origins'].append(origin)
        if row['allow_patterns'] != patterns:
            row['allow_patterns'] = None

    collections = json.loads(subprocess.check_output(
        [sys.executable, 'scripts/build_mimir_collection_manifest.py'], cwd=ROOT))
    for collection in collections['collections']:
        for repo in collection['datasets']:
            add(repo, None, collection['title'])
    for spec in HF_DATASETS:
        if any(group.startswith('dfm') and group[3:].isdigit()
               and 2 <= int(group[3:]) <= 15 for group in spec.groups):
            add(spec.repo_id, spec.revision, f'downloader:{spec.name}', list(spec.allow_patterns))
    for version in (13, 14, 15):
        registry = json.loads((ROOT / f'config/dfm{version}_sources.json').read_text())
        for source in registry['additions']:
            repo = source.get('hf_repo_id') or source.get('repo_id')
            revision = source.get('hf_revision') if source.get('hf_repo_id') else source.get('revision')
            add(repo, revision, f'dfm{version}:{source["name"]}')
    base = json.loads(base_manifest.read_text())
    for row in entries.values():
        for done in base['hf_sources']:
            if (done['status'] == 'downloaded' and row['repo_id'] == done['repo_id']
                    and row['requested_revision'] == done['resolved_revision']
                    and row['allow_patterns'] == done['allow_patterns']):
                row.update(status='reused_fresh_download', download_path=done['download_path'],
                           resolved_revision=done['resolved_revision'])
    return dict(scope='declared_candidates_not_complete_historical_closure',
                base_manifest=str(base_manifest.resolve()), repository_workers=2, file_workers=16,
                entries=list(entries.values()))


def fetch(entry, root, file_workers):
    entry = dict(entry)
    print(json.dumps(dict(repo_id=entry['repo_id'], status='starting_download')), flush=True)
    try:
        info = HfApi().dataset_info(entry['repo_id'], revision=entry['requested_revision'])
        entry['resolved_revision'] = info.sha
        entry['revision_basis'] = ('registry_pin' if entry['requested_revision'] else
                                   'current_hf_head_not_historical_proof')
        name = entry['repo_id'].replace('/', '--') + '--' + info.sha[:12]
        destination = root / 'downloads' / name
        snapshot_download(repo_id=entry['repo_id'], repo_type='dataset', revision=info.sha,
                          local_dir=destination, cache_dir=root / 'hf-cache',
                          allow_patterns=entry['allow_patterns'], max_workers=file_workers)
        entry.update(status='downloaded', download_path=str(destination))
    except Exception as exc:
        entry.update(status='blocked', error=f'{type(exc).__name__}: {exc}')
    return entry


def run(root):
    with (root / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = json.loads((root / 'manifest.json').read_text())
        entries = manifest['entries']
        # Metadata and state are written by this coordinator only.
        with ThreadPoolExecutor(max_workers=manifest['repository_workers']) as pool:
            futures = {pool.submit(fetch, entry, root, manifest['file_workers']): i
                       for i, entry in enumerate(entries) if entry['status'] not in
                       ('downloaded', 'reused_fresh_download')}
            for future in as_completed(futures):
                row = future.result()
                entries[futures[future]] = row
                write_json(root / 'manifest.json', manifest)
                print(json.dumps({key: row.get(key) for key in
                                  ('repo_id', 'resolved_revision', 'status', 'error')}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('init', 'run'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--base-manifest', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.action == 'init':
        if args.base_manifest is None:
            parser.error('--base-manifest required')
        manifest = inventory(args.base_manifest)
        root.mkdir(parents=True, exist_ok=False)
        write_json(root / 'manifest.json', manifest)
        print(f"Queued {len(manifest['entries'])} repository/revision entries")
    else:
        run(root)


if __name__ == '__main__':
    main()
