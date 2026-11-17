"""Fetch pinned historical transformations; never silently regenerate."""
import argparse
import json
from pathlib import Path
import sys

from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.publish_verified_dfm_transforms import digest
from scripts.replay_dfm_serial import write_json


def fetch(work, version):
    registry = json.loads((ROOT / 'config/data/historical_rebuild_packages.json').read_text())
    spec = registry[str(version)]
    if not spec['revision']:
        raise ValueError('Verified package publication is pending; no pinned revision. '
                         'Wait or explicitly enable --regenerate-transforms.')
    package = Path(snapshot_download(
        spec['repo_id'], revision=spec['revision'], repo_type='dataset',
        local_dir=work / 'hf-package-download', max_workers=4))
    manifest = json.loads((package / 'manifest.json').read_text())
    if manifest['version'] != version:
        raise ValueError('Wrong package version')
    destination = work / 'converted'
    if destination.exists() and not destination.is_symlink():
        raise ValueError(f'Refusing to replace an existing generation directory: {destination}')
    for item in manifest['files']:
        path = package / item['path']
        if not path.resolve().is_relative_to((package / 'data').resolve()):
            raise ValueError('Invalid package path')
        if path.stat().st_size != item['size'] or digest(path) != item['sha256']:
            raise ValueError(f'Package checksum mismatch: {path}')
    if not destination.exists():
        destination.symlink_to((package / 'data').resolve(), target_is_directory=True)
    if destination.resolve() != (package / 'data').resolve():
        raise ValueError('Existing converted link points to another package')
    write_json(work / 'package-input.json', spec | dict(
        status='downloaded_sha256_verified', files=len(manifest['files'])))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--version', type=int, choices=(2, 3), required=True)
    args = p.parse_args()
    fetch(args.work.resolve(), args.version)


if __name__ == '__main__':
    main()
