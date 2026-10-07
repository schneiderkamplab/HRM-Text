"""Create a fresh versioned calibration, preserving the first-pass evidence."""
from pathlib import Path

from dfm12.io import atomic, digest, file_hash, load, rows, write_json
from dfm12 import multilingual_generation_v4 as generation
from dfm14.generation_prepare import factory
from dfm14.calibrate import configure
import json


def prepare():
    old = Path('data/dfm14/generation-calibration-v1')
    root = Path('data/dfm14/generation-calibration-v2')
    if (root/'manifest.json').exists():
        return root
    configure()
    eligible = []
    for source in load(old/'modernized-openhermes-seeds.json'):
        spec = dict(source=source, family='openhermes', subtype='translate')
        try:
            generation._source_preflight(spec)
        except ValueError:
            continue
        eligible.append(source)
    if not eligible:
        raise ValueError('No complete, untruncated OpenHermes seeds fit the contract')
    manifest = load(old/'manifest.json')
    groups = []
    for group in manifest['groups']:
        path = root/group['language']/(group['family']+'.jsonl')
        with atomic(path) as handle:
            for row in rows(group['path']):
                spec = dict(row['spec'])
                if spec['family'] == 'openhermes':
                    spec['source'] = eligible[spec['slot'] % len(eligible)]
                # Same problems permit direct first/second-pass comparison.
                row = dict(row, id=digest(['dfm14-calibration-v2', row['id']]),
                           spec=spec, previous_id=row['id'])
                row.pop('request', None)
                handle.write(json.dumps(row, ensure_ascii=False)+'\n')
        groups.append(dict(group, path=str(path.resolve()), sha256=file_hash(path)))
    write_json(root/'manifest.json', dict(manifest, groups=groups,
        previous_manifest_sha256=file_hash(old/'manifest.json'),
        eligible_openhermes_seeds=len(eligible),
        production_requires='Per-language/family calibration approval and broad production seed preparation'))
    return root


if __name__ == '__main__':
    print(prepare())
