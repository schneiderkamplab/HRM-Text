"""Fetch the registry-pinned DFM4 additions; regeneration is never implicit."""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys

from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.publish_dfm4_historical import COUNTS, FAMILIES, digest
from scripts.replay_dfm_serial import write_json


def validate(package, spec):
    if digest(package / 'manifest.json') != spec['manifest_sha256']:
        raise ValueError('Manifest checksum mismatch')
    manifest = json.loads((package / 'manifest.json').read_text())
    if manifest['version'] != 4 or manifest.get('inherited_payloads_included') is not False:
        raise ValueError('Wrong package scope')
    seen = set()
    counts = {k: 0 for k in COUNTS}
    families = {k: set() for k in COUNTS}
    for section in ('files', 'provenance'):
        for item in manifest[section]:
            rel = PurePosixPath(item['path'])
            if rel.is_absolute() or '..' in rel.parts or item['path'] in seen:
                raise ValueError('Invalid package path')
            seen.add(item['path'])
            if section == 'files':
                if len(rel.parts) < 4 or rel.parts[0] != 'data' or rel.parts[1] not in FAMILIES:
                    raise ValueError('Invalid payload path')
                kind = rel.parts[1]
                if rel.parts[2] not in FAMILIES[kind] or rel.suffix != '.parquet':
                    raise ValueError('Unexpected payload family')
                counts[kind] += 1
                families[kind].add(rel.parts[2])
            elif rel.parts[0] != 'provenance':
                raise ValueError('Invalid provenance path')
            path = package / rel
            if not path.resolve().is_relative_to(package.resolve()):
                raise ValueError('Escaping package path')
            if path.stat().st_size != item['size'] or digest(path) != item['sha256']:
                raise ValueError(f'Package checksum mismatch: {rel}')
    if counts != COUNTS or families != FAMILIES:
        raise ValueError('Incomplete family inventory')
    actual = {p.relative_to(package).as_posix() for p in (package / 'data').rglob('*') if p.is_file()}
    if actual != {x['path'] for x in manifest['files']}:
        raise ValueError('Unexpected payload files')
    return manifest


def fetch(work, registry):
    spec = json.loads(registry.read_text()).get('4', {})
    if not re.fullmatch('[0-9a-f]{40}', spec.get('revision', '')) or not spec.get('manifest_sha256'):
        raise ValueError('DFM4 publication pending: a verified pinned commit is required')
    work.mkdir(parents=True, exist_ok=True)
    package = Path(snapshot_download(spec['repo_id'], revision=spec['revision'], repo_type='dataset',
        local_dir=work / 'hf-additions-download', max_workers=4))
    manifest = validate(package, spec)
    for kind in COUNTS:
        dst = work / kind
        target = (package / 'data' / kind).resolve()
        if dst.exists() or dst.is_symlink():
            if not dst.is_symlink() or dst.resolve() != target:
                raise ValueError(f'Refusing existing output: {dst}')
    config = package / 'provenance/dfm4/prefix_config.yaml'
    dst_config = work / 'prefix_config.yaml'
    if dst_config.exists() and digest(dst_config) != digest(config):
        raise ValueError('Existing sampling configuration differs')
    for kind in COUNTS:
        if not (work / kind).is_symlink():
            (work / kind).symlink_to((package / 'data' / kind).resolve(), target_is_directory=True)
    shutil.copyfile(config, dst_config)
    write_json(work / 'package-input.json', spec | dict(status='downloaded_sha256_verified',
               files=len(manifest['files'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--registry', type=Path, default=ROOT / 'config/data/historical_rebuild_packages.json')
    args = p.parse_args()
    fetch(args.work.resolve(), args.registry.resolve())
