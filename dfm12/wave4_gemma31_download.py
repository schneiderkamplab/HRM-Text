"""CPU-only authenticated snapshot download with upstream hash verification."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import time

from huggingface_hub import HfApi, hf_hub_download, snapshot_download, constants
from .io import load, write_json, lock, file_hash

MODEL = 'google/gemma-4-31B-it'
ROOT = Path('data/dfm13/wave4/gemma31-download')


def verify_file(path, item):
    if path.stat().st_size != item['size']:
        raise ValueError('File size mismatch: ' + item['name'])
    sha = file_hash(path)
    if item.get('sha256'):
        if sha != item['sha256']:
            raise ValueError('Upstream LFS SHA256 mismatch: ' + item['name'])
    elif item.get('blob_id'):
        git = hashlib.sha1(f"blob {item['size']}\0".encode())
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b''):
                git.update(chunk)
        if git.hexdigest() != item['blob_id']:
            raise ValueError('Upstream git blob mismatch: ' + item['name'])
    else:
        raise ValueError('Missing upstream hash')
    return dict(item, local_sha256=sha, path=str(path))


def run(root):
    root.mkdir(parents=True, exist_ok=True)
    with lock(root / 'download.lock'):
        started = time.time()
        write_json(root / 'status.json', dict(pid=os.getpid(), phase='resolving', time=started))
        try:
            if (root / 'revision.json').exists():
                receipt = load(root / 'revision.json')
            else:
                info = HfApi().model_info(MODEL, files_metadata=True)
                files = [dict(name=s.rfilename, size=s.size, blob_id=s.blob_id,
                    sha256=getattr(s.lfs, 'sha256', None)) for s in info.siblings]
                receipt = dict(model=MODEL, revision=info.sha, files=files, resolved_at=time.time())
                write_json(root / 'revision.json', receipt)
            cache = Path(constants.HF_HUB_CACHE)
            cache.mkdir(parents=True, exist_ok=True)
            needed = sum(f['size'] for f in receipt['files'])
            free = shutil.disk_usage(cache).free
            if free < needed * 2 + 5 * 1024**3:
                raise ValueError('Insufficient disk space including download/verification margin')
            write_json(root / 'disk.json', dict(cache=str(cache), free_bytes=free, snapshot_bytes=needed))
            # Fetch a gated payload first; public metadata alone does not prove access.
            hf_hub_download(MODEL, 'config.json', revision=receipt['revision'])
            write_json(root / 'status.json', dict(pid=os.getpid(), phase='downloading',
                revision=receipt['revision'], authenticated_payload_access=True, time=time.time()))
            snapshot = Path(snapshot_download(MODEL, revision=receipt['revision'], max_workers=4))
            verified = []
            for item in receipt['files']:
                write_json(root / 'status.json', dict(pid=os.getpid(), phase='verifying',
                    file=item['name'], verified_files=len(verified), total_files=len(receipt['files']), time=time.time()))
                verified.append(verify_file(snapshot / item['name'], item))
            from .wave4_gemma31_transition import model_files
            pins = model_files(snapshot)
            write_json(root / 'ready.json', dict(model=MODEL, revision=receipt['revision'],
                snapshot=str(snapshot), files=verified, model_files=pins,
                all_files_verified=True, cpu_only=True, production_approved=False, time=time.time()))
            write_json(root / 'status.json', dict(pid=None, previous_pid=os.getpid(), phase='ready',
                verified_files=len(verified), time=time.time()))
        except Exception as exc:
            # Avoid URLs, headers or credentials in exception representations.
            write_json(root / 'status.json', dict(pid=None, previous_pid=os.getpid(), phase='failed',
                error_type=type(exc).__name__, http_status=getattr(getattr(exc, 'response', None), 'status_code', None),
                time=time.time()))
            raise SystemExit('Download failed; sanitized status.json records error type/status') from None


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    a = p.parse_args()
    run(a.root)
