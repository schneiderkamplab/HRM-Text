"""Resolve HF-only inputs for serial DFM reconstruction; never reuse local data.

The reference tree is used ONLY to list the historical source families. No
payload, token arrays, indices, or local download cache are used as inputs.
This is a source preflight, not a completed reconstruction or match proof.
"""
import argparse
from dataclasses import asdict
from dataclasses import replace
from fnmatch import fnmatch
import json
import os
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

from scripts.download_training_datasets import HF_DATASETS


AGREEMENT_SOURCES = frozenset({'lexdk', 'dbc'})


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(temporary, path)


def source_specs(names):
    registry = {item.name: item for item in HF_DATASETS}
    unknown = set(names) - registry.keys() - AGREEMENT_SOURCES
    if unknown:
        raise ValueError(f'No HF source mapping (local fallback forbidden): {sorted(unknown)}')
    return [registry[name] for name in sorted(set(names) - AGREEMENT_SOURCES)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--reference-tree', type=Path)
    inputs.add_argument('--input-lock', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    if args.input_lock:
        locked = json.loads(args.input_lock.read_text())
        if any(s['status'] != 'resolved' for s in locked['hf_sources']):
            raise ValueError('Input lock contains unresolved sources')
        names = [s['name'] for s in locked['hf_sources']] + locked['local_agreement_sources']
        locked_sources = {s['name']: s for s in locked['hf_sources']}
        specs = []
        for spec in source_specs(names):
            entry = locked_sources[spec.name]
            if entry['repo_id'] != spec.repo_id:
                raise ValueError(f'Registry changed repository for {spec.name}')
            specs.append(replace(spec, revision=entry['resolved_revision'],
                                 allow_patterns=tuple(entry['allow_patterns'])))
    else:
        names = sorted({p.name.split('__')[0] for p in args.reference_tree.iterdir() if p.is_dir()})
        specs = source_specs(names)
    manifest = dict(
        version=1, status='resolving_hf_revisions', scope='source_access_preflight_only',
        reference_inventory=str(args.reference_tree.resolve()) if args.reference_tree else None,
        input_lock=str(args.input_lock.resolve()) if args.input_lock else None,
        input_policy='HF snapshots only; lexdk and dbc are the only local data exceptions',
        local_agreement_sources=sorted(set(names) & AGREEMENT_SOURCES),
        hf_sources=[], cold_rebuild_verified=False)
    api = HfApi()
    for spec in specs:
        entry = dict(asdict(spec), status='pending',
                     revision_basis=(locked_sources[spec.name]['revision_basis'] if args.input_lock else
                                     'registry_pin' if spec.revision else 'current_hf_head_not_historical_proof'))
        manifest['hf_sources'].append(entry)
        try:
            info = api.dataset_info(spec.repo_id, revision=spec.revision, files_metadata=True)
            entry.update(status='resolved', resolved_revision=info.sha, files=[
                dict(path=file.rfilename, size=file.size, blob_id=file.blob_id,
                     lfs_sha256=getattr(file.lfs, 'sha256', None))
                for file in info.siblings
                if any(fnmatch(file.rfilename, pattern) for pattern in spec.allow_patterns)])
            if not entry['files']:
                raise ValueError('No files matched configured download patterns')
            if args.download:
                destination = output / 'downloads' / spec.name
                snapshot_download(repo_id=spec.repo_id, repo_type='dataset', revision=info.sha,
                                  allow_patterns=list(spec.allow_patterns), local_dir=destination,
                                  cache_dir=output / 'hf-cache', force_download=True, max_workers=4)
                entry.update(status='downloaded', download_path=str(destination))
        except Exception as exc:
            entry.update(status='blocked', error=f'{type(exc).__name__}: {exc}')
        save(output / 'dfm1-hf-inputs.json', manifest)
        print(json.dumps({key: entry.get(key) for key in
                          ('name', 'repo_id', 'status', 'resolved_revision', 'error')}), flush=True)
    manifest['status'] = ('blocked' if any(s['status'] == 'blocked' for s in manifest['hf_sources'])
                          else 'inputs_downloaded' if args.download else 'hf_metadata_verified')
    save(output / 'dfm1-hf-inputs.json', manifest)
    print(manifest['status'], flush=True)


if __name__ == '__main__':
    main()
