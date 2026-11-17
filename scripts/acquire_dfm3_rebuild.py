"""Acquire historical DFM3 Common Pile inputs from pinned HF revisions.

Historical conversion receipts provide filenames/sizes only, never payloads.
"""
import argparse
import json
from pathlib import Path
import sys

from huggingface_hub import HfApi, hf_hub_download

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.download_training_datasets import HF_DATASETS
from scripts.replay_dfm_serial import write_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    lock_path = work / 'hf-input-lock.json'
    if lock_path.exists():
        sources = json.loads(lock_path.read_text())
    else:
        api = HfApi()
        sources = []
        for source in HF_DATASETS:
            if not source.name.startswith('common_pile_'):
                continue
            receipts = sorted((ROOT / 'data/converted_sources' / source.name).rglob(
                '*.convert_meta.json'))
            if not receipts:
                raise ValueError(f'Missing historical input inventory: {source.name}')
            info = api.dataset_info(source.repo_id)
            available = api.list_repo_files(source.repo_id, repo_type='dataset', revision=info.sha)
            files = []
            for receipt in receipts:
                meta = json.loads(receipt.read_text())
                rel = Path(meta['source_relpath'])
                matches = [p for p in available if Path(p).name == rel.name]
                if len(matches) != 1:
                    raise ValueError(f'Ambiguous/missing HF input: {rel}: {matches}')
                files.append(dict(remote=matches[0], relative=str(rel), size=meta['source_size']))
            sources.append(dict(name=source.name, repo_id=source.repo_id, revision=info.sha,
                                revision_basis='current_head_pending_historical_comparison',
                                files=files))
        write_json(lock_path, sources)
    for source in sources:
        for item in source['files']:
            downloaded = Path(hf_hub_download(
                source['repo_id'], item['remote'], repo_type='dataset',
                revision=source['revision'], local_dir=work / 'downloads' / source['name']))
            if downloaded.stat().st_size != item['size']:
                raise ValueError(f'Historical size mismatch: {downloaded}')
            destination = work / 'inputs' / item['relative']
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                destination.symlink_to(downloaded.resolve())
            print(f"Acquired {item['relative']}", flush=True)
    write_json(work / 'acquisition-complete.json',
               dict(sources=len(sources), files=sum(len(s['files']) for s in sources)))


if __name__ == '__main__':
    main()
