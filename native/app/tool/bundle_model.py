#!/usr/bin/env python3
"""Add weights to a verified desktop package without rebuilding its native binaries."""
import argparse
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import zipfile

from package_archive import digest, write_archive


def bundle_model(archive, model, output):
    archive, model, output = archive.resolve(), model.resolve(), output.resolve()
    expected = archive.with_name(archive.name + '.sha256').read_text().split()[0]
    if digest(archive) != expected:
        raise ValueError('Source archive checksum mismatch')
    with model.open('rb') as stream:
        if stream.read(4) != b'GGUF':
            raise ValueError('Model is not a GGUF file')
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bundle-model-', dir=output) as temporary:
        root = Path(temporary)
        if archive.name.endswith('.tar.gz'):
            with tarfile.open(archive) as source:
                source.extractall(root, filter='data')
        elif archive.suffix == '.zip':
            with zipfile.ZipFile(archive) as source:
                source.extractall(root)
        else:
            raise ValueError('Expected a desktop tar.gz or ZIP')
        manifests = list(root.glob('*/manifest.json'))
        if len(manifests) != 1 or len(list(root.iterdir())) != 1:
            raise ValueError('Expected exactly one desktop bundle')
        stage = manifests[0].parent
        manifest = json.loads(manifests[0].read_text())
        if manifest['schemaVersion'] != 1 or manifest['platform'] not in ('linux', 'windows'):
            raise ValueError('Unsupported package manifest')
        actual = {p.relative_to(stage).as_posix(): digest(p)
                  for p in stage.rglob('*') if p.is_file() and p != manifests[0]}
        if actual != manifest['files']:
            raise ValueError('Source bundle contents do not match its manifest')
        asset = stage / 'data/flutter_assets/assets/model.gguf'
        if not asset.is_file():
            raise ValueError('Bundle has no declared model asset')
        shutil.copyfile(model, asset)
        readme = stage / 'README.txt'
        readme.write_text(readme.read_text(encoding='utf-8') +
                          '\nMimir weights are included; first launch works offline.\n', encoding='utf-8')
        manifest['modelSHA256'] = digest(asset)
        manifest['repackedFromSHA256'] = expected
        manifest['files'] = {p.relative_to(stage).as_posix(): digest(p)
                             for p in sorted(stage.rglob('*')) if p.is_file() and p != manifests[0]}
        manifests[0].write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        return write_archive(stage, output, manifest['platform'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path, help='CI archive with adjacent .sha256 file')
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(bundle_model(args.archive, args.model, args.output))


if __name__ == '__main__':
    main()
