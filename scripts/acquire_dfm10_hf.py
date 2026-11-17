"""Acquire DFM10 published exports into a fresh, pinned HF-only staging area.

No local export payload is read. The local manifest selects repository names only;
remote manifests and payload hashes provide acquisition evidence. This stage does
not certify historical equality or permit downstream tokenization automatically.
"""
import argparse
import fcntl
import hashlib
import json
import re
import sys
from pathlib import Path
from huggingface_hub import HfApi, hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEFAULT = ROOT / 'data/rebuild_hf_dfm/dfm10-hf-v2'


def save(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def safe_file(root, rel):
    p = root / rel
    if Path(rel).is_absolute() or '..' in Path(rel).parts or not p.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Unsafe HF file path: {rel}')
    return p


def run(work):
    work.mkdir(parents=True, exist_ok=True)
    with (work / 'acquire.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pin_path = work / 'hf-lock.json'
        if pin_path.exists():
            pins = json.loads(pin_path.read_text())
        else:
            names = [p['name'] for p in json.loads((ROOT / 'exports_dfm10/manifest.json').read_text())['packages']]
            from scripts.dfm10_export_scope import inherited
            names = [name for name in names if not inherited(name)]
            api = HfApi()
            pins = {'policy': 'HF-only; lexdk/DBC exceptions only', 'repositories': {}}
            for name in names:
                repo = 'schneiderkamplab/' + name
                revision = api.dataset_info(repo).sha
                if not re.fullmatch('[0-9a-f]{40}', revision):
                    raise ValueError(f'Unpinned revision: {repo}')
                pins['repositories'][repo] = revision
                print('Pinned', repo, revision, flush=True)
            save(pin_path, pins)
        receipts = []
        from scripts.dfm10_export_scope import inherited
        for repo, revision in pins['repositories'].items():
            if inherited(repo):
                continue
            if not re.fullmatch('[0-9a-f]{40}', revision):
                raise ValueError('Invalid pinned revision')
            dest = work / 'acquisitions' / (repo.replace('/', '--') + '--' + revision)
            manifest_path = Path(hf_hub_download(repo, 'metadata/manifest.json', repo_type='dataset', revision=revision, local_dir=dest))
            manifest = json.loads(manifest_path.read_text())
            files = []
            for item in manifest['data_files']:
                target = safe_file(dest, item['file'])
                hf_hub_download(repo, item['file'], repo_type='dataset', revision=revision, local_dir=dest)
                if target.stat().st_size != item['bytes'] or sha(target) != item['sha256']:
                    raise ValueError(f'Checksum mismatch: {repo}/{item["file"]}')
                files.append(item)
                print('Verified', repo, item['file'], flush=True)
            receipt = {'repo_id': repo, 'revision': revision, 'manifest_sha256': sha(manifest_path), 'files': files, 'download_path': str(dest), 'status': 'downloaded_sha256_verified'}
            save(dest / 'acquisition-receipt.json', receipt)
            receipts.append(receipt)
            save(work / 'acquisition-progress.json', {'complete': False, 'repositories': receipts})
        save(work / 'acquisition-progress.json', {'complete': True, 'repositories': receipts})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, default=DEFAULT)
    run(p.parse_args().work.resolve())
