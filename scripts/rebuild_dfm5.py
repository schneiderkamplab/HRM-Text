"""Fail-closed DFM5 reselection from pinned HF payloads and verified rebuilds.

Production trees supply comparison data and historical partition sizes only.
Every emitted text row comes from an acquired HF payload; no reference token
backing is reused. Reference partition counts are frozen as recipe metadata.
"""
import argparse
from collections import Counter
import fcntl
import fnmatch
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_tokenized_dfm5_tree import DANISH_MIXED_PREFIXES, EXTRA_MIXED_PREFIXES
from scripts.rebuild_dfm5_acquire import candidates, digest, load
from scripts.replay_dfm_serial import FIELDS, equal_arrays, write_json

CONFIG = ROOT / 'config/data/dfm5_hf_rebuild.json'
REFERENCE = ROOT / 'data/tokenized_dfm5'
ACQUISITION = ROOT / 'data/rebuild_hf_dfm/dfm5-acquisition'


def allowed(path, roots):
    resolved = path.resolve(strict=True)
    if not any(resolved.is_relative_to(root.resolve(strict=True)) for root in roots):
        raise ValueError(f'Forbidden rebuild payload: {path} -> {resolved}')
    return resolved


def link(source, target, roots):
    source = allowed(source, roots)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if not target.is_symlink() or target.resolve() != source:
            raise ValueError(f'Refusing conflicting output: {target}')
    else:
        target.symlink_to(source)


def array_length(path):
    # Read only the NPY header when recovering historical shard boundaries.
    with path.open('rb') as f:
        version = np.lib.format.read_magic(f)
        if version == (1, 0):
            shape, _, _ = np.lib.format.read_array_header_1_0(f)
        elif version == (2, 0):
            shape, _, _ = np.lib.format.read_array_header_2_0(f)
        else:
            raise ValueError(f'Unexpected NPY version: {path}')
    if len(shape) != 1:
        raise ValueError(f'Non-vector reference: {path}')
    return shape[0]


def require_predecessors(queue):
    for version in range(1, 5):
        if load(queue / f'dfm{version}/verified.json').get('status') != 'matched':
            raise ValueError(f'DFM{version} has not passed comparison')


def selected_sapient(source, policy):
    result = []
    for item in source['files']:
        rel = item['path']
        if not rel.endswith(('.parquet', '.jsonl')):
            continue
        name = 'sapient_cleaned/' + rel
        matches = lambda rules: any(fnmatch.fnmatch(name, p) for p in rules)
        if not matches(policy.get('include', ['**/*'])):
            continue
        if not matches(policy.get('allow_overrides', [])) and matches(policy.get('deny', [])):
            continue
        task = '__'.join(Path(rel).parts[1:])
        result.append(dict(task=task, **item))
    if len({x['task'] for x in result}) != len(result):
        raise ValueError('Colliding Sapient task names')
    return sorted(result, key=lambda x: x['task'])


def verify_snapshot_file(path, item):
    if path.stat().st_size != item['size']:
        raise ValueError(f'Snapshot size mismatch: {path}')
    if item.get('lfs_sha256'):
        matches = digest(path) == item['lfs_sha256']
    elif item.get('blob_id'):
        h = hashlib.sha1(f"blob {item['size']}\0".encode())
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
                h.update(chunk)
        matches = h.hexdigest() == item['blob_id']
    else:
        raise ValueError(f'Missing remote hash provenance: {path}')
    if not matches:
        raise ValueError(f'Snapshot checksum mismatch: {path}')


def prepare(work):
    config = load(CONFIG)
    queue = work.parent
    require_predecessors(queue)
    policy_bytes = subprocess.check_output(['git', 'show',
        config['source_filter_revision'] + ':config/data/source_filter.yaml'], cwd=ROOT)
    policy = yaml.safe_load(policy_bytes)
    provenance = load(queue / 'dfm1/input-provenance.json')
    source = next(s for s in provenance['acquisition_manifest']['hf_sources']
                  if s['name'] == 'sapient_cleaned')
    if source['status'] != 'downloaded' or not re.fullmatch('[0-9a-f]{40}', source['resolved_revision']):
        raise ValueError('Missing pinned Sapient snapshot')
    snapshot = Path(source['download_path'])
    acquisition = Path(load(queue / 'plan.json')['acquisition']) / 'downloads'
    allowed(snapshot, [acquisition])
    selection = selected_sapient(source, policy)
    if len(selection) != config['sapient_tasks']:
        raise ValueError(f"Historical Sapient filter selected {len(selection)}, expected 4891")
    # Selection is computed from the pinned policy, then checked against the
    # preserved union. The production symlink targets are never rebuild inputs.
    actual = {x['task'] for x in selection}
    expected = {p.name for p in REFERENCE.iterdir() if p.is_dir()
                and p.resolve().parent == ROOT / 'data/tokenized_original_sapient'}
    if actual != expected:
        raise ValueError('Pinned Sapient source selection differs from DFM5')
    work.mkdir(parents=True, exist_ok=True)
    (work / 'source_filter.yaml').write_bytes(policy_bytes)
    config_source = ROOT / 'data_io/prefix_config_dfm5.yaml'
    config_target = work / 'prefix_config.yaml'
    if config_target.exists() and digest(config_target) != digest(config_source):
        raise ValueError('Sampling policy changed after recipe was frozen')
    shutil.copyfile(config_source, config_target)
    inherited = {}
    for path in sorted((queue / 'dfm1/tokenized').iterdir()):
        if path.is_dir() and path.name.startswith(DANISH_MIXED_PREFIXES + EXTRA_MIXED_PREFIXES):
            inherited[path.name] = str(allowed(path, [queue / 'dfm1/tokenized']))
    if len(inherited) != config['mixed_tasks']:
        raise ValueError('Selected mixed-source inventory differs')
    for path in sorted((queue / 'dfm4/tokenized_summary').iterdir()):
        if path.is_dir():
            if path.name in inherited:
                raise ValueError('Duplicate inherited task')
            inherited[path.name] = str(allowed(path, [queue / 'dfm4/tokenized_summary']))
    if len(inherited) != config['mixed_tasks'] + config['summary_tasks']:
        raise ValueError('DFM4 summary inventory differs')
    reused = 0
    for i, item in enumerate(selection, 1):
        raw = allowed(snapshot / item['path'], [acquisition])
        # The earlier reconstruction did not necessarily use every raw source.
        verify_snapshot_file(raw, item)
        old_name = 'sapient_cleaned__' + item['path'].replace('/', '__')
        old = queue / 'dfm1/tokenized' / old_name
        if old.is_dir():
            inherited[item['task']] = str(allowed(old, [queue / 'dfm1/tokenized']))
            reused += 1
        else:
            link(raw, work / 'sapient' / item['task'], [acquisition])
        if i % 100 == 0:
            print(f'Sapient snapshot checked {i}/{len(selection)}', flush=True)
    epochs = sorted(p.name for p in (ROOT / 'data/sampled_dfm5').glob('epoch_*'))
    if epochs != [f'epoch_{i}' for i in range(config['epochs'])]:
        raise ValueError('Preserved epoch inventory changed')
    write_json(work / 'recipe.json', dict(config=config, source=source,
        selection=selection, inherited=inherited, sapient_reused=reused,
        source_filter_sha256=digest(work / 'source_filter.yaml'),
        prefix_config_sha256=digest(config_target), epochs=epochs,
        tokenizer_sha256=digest(ROOT / 'data_io/trained_tokenizers/bpe/tokenizer.json')))


def acquired(wait=True):
    deadline = time.monotonic() + 24 * 3600
    while True:
        manifest = load(ACQUISITION / 'manifest.json')
        if manifest.get('status') == 'downloaded_sha256_verified':
            break
        if not wait or time.monotonic() > deadline:
            raise ValueError('DFM5 HF acquisitions incomplete')
        # An abandoned acquisition must block, not silently wait forever.
        with (ACQUISITION / 'runner.lock').open('a') as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise ValueError('DFM5 acquisition stopped before completing')
        print('Waiting for isolated pinned DFM5 acquisition', flush=True)
        time.sleep(30)
    wanted = {x['repo_id']: x for x in candidates()}
    if {x['repo_id'] for x in manifest['entries']} != wanted.keys() or len(manifest['entries']) != 82:
        raise ValueError('Acquisition identity inventory differs')
    for entry in manifest['entries']:
        if any(entry.get(k) != v for k, v in wanted[entry['repo_id']].items()):
            raise ValueError('Acquisition source identity changed')
        if entry['status'] != 'downloaded_sha256_verified' or not re.fullmatch('[0-9a-f]{40}', entry['revision']):
            raise ValueError('Unverified or unpinned acquisition')
        for item in entry['files']:
            path = allowed(Path(entry['download_path']) / item['path'], [ACQUISITION / 'downloads'])
            if path.stat().st_size != item['size'] or digest(path) != item['verified_sha256']:
                raise ValueError(f'Downloaded HF payload changed: {path}')
    return manifest


def hf_rows(entry):
    for item in sorted(entry['files'], key=lambda x: x['path']):
        with gzip.open(Path(entry['download_path']) / item['path'], 'rt', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def synthetic_row(row, entry):
    source = row['source']
    if source['group'] != entry['group'] or source['task_name'] != entry['task_name']:
        raise ValueError('Synthetic HF source identity mismatch')
    if row['synthetic_audit']['keep'] is not True:
        raise ValueError('Unaccepted synthetic row')
    messages = row['messages']
    if [x['role'] for x in messages] != ['user', 'assistant']:
        raise ValueError('Synthetic payload is not an invertible HRM pair')
    # These exports wrap original HRM fields, unlike the chat-native exports.
    return dict(condition=row.get('condition') or 'direct',
                instruction=messages[0]['content'], response=messages[1]['content'])


def recover_synth(work):
    manifest = acquired()
    stage = Path(tempfile.mkdtemp(prefix='.synth-', dir=work))
    counts = Counter()
    try:
        for entry in manifest['entries']:
            if entry['kind'] != 'synth':
                continue
            slug = entry['task_name'].replace('__', '_')
            name = f"synth_{entry['group']}__{slug}__train.jsonl.gz"
            output = stage / name
            rows = 0
            with gzip.open(output, 'wt', encoding='utf-8') as f:
                for row in hf_rows(entry):
                    f.write(json.dumps(synthetic_row(row, entry), ensure_ascii=False) + '\n')
                    rows += 1
            expected = array_length(REFERENCE / name / 'inst_len.npy')
            if rows != expected:
                raise ValueError(f'{name}: HF rows {rows}, preserved rows {expected}')
            counts[entry['group']] += rows
            print(f'Recovered {name}: {rows}', flush=True)
        if dict(counts) != dict(high40=190464, repeat30=63783):
            raise ValueError(f'Synthetic accepted-row totals differ: {counts}')
        publish_directory(stage, work / 'synth')
        write_json(work / 'synth-recovery.json', dict(status='rows_recovered_not_token_verified',
                   rows=dict(counts), acquisition_manifest_sha256=digest(ACQUISITION / 'manifest.json')))
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def publish_directory(stage, output):
    if output.exists():
        raise ValueError(f'Refusing to replace existing recovery output: {output}')
    os.replace(stage, output)


def repartition(rows, partitions, output):
    """Repartition HF rows; counts are recipe metadata, never reference text."""
    rows = iter(rows)
    count = 0
    for name, size in partitions:
        if Path(name).name != name or size < 0:
            raise ValueError('Invalid historical partition')
        with gzip.open(output / name, 'wt', encoding='utf-8') as f:
            for _ in range(size):
                row = next(rows, None)
                if row is None:
                    raise ValueError(f'HF accepted rows exhausted at {name}, row {count}')
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                count += 1
    if next(rows, None) is not None:
        raise ValueError('HF accepted rows exceed preserved partition total')
    return count


def recover_exports(work):
    manifest = acquired()
    stage = Path(tempfile.mkdtemp(prefix='.exports-', dir=work))
    receipt = []
    try:
        for entry in manifest['entries']:
            if entry['kind'] != 'export':
                continue
            prefix = entry['name'] + '__'
            refs = sorted(p for p in REFERENCE.iterdir() if p.is_dir() and p.name.startswith(prefix))
            partitions = [(p.name, array_length(p / 'inst_len.npy')) for p in refs]
            if not partitions:
                raise ValueError(f'No historical export tasks: {prefix}')
            # The native exports are single-turn user/assistant conversations.
            # One HF row must remain one HRM example for these partition counts.
            def checked_rows():
                for row in hf_rows(entry):
                    if [m['role'] for m in row['messages']] != ['user', 'assistant']:
                        raise ValueError('Unexpected export message structure')
                    if not row['messages'][1]['content'].strip():
                        raise ValueError('Empty exported response cannot preserve partition sizes')
                    yield row
            count = repartition(checked_rows(), partitions, stage)
            receipt.append(dict(repo_id=entry['repo_id'], revision=entry['revision'],
                                partitions=partitions, rows=count))
            print(f"Recovered {entry['name']}: {len(partitions)} tasks / {count} rows", flush=True)
        if sum(len(r['partitions']) for r in receipt) != load(CONFIG)['export_tasks']:
            raise ValueError('Export task inventory differs')
        publish_directory(stage, work / 'exports')
        write_json(work / 'export-recovery.json', dict(status='repartitioned_requires_token_comparison',
                   method='sorted pinned HF rows split at preserved NPY row counts', datasets=receipt))
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def verify_tasks(work, kind):
    root = work / ('tokenized' if kind == 'all' else 'tokenized_' + kind)
    actual = {p.name: p for p in root.iterdir() if p.is_dir()}
    if kind == 'all':
        expected = {p.name for p in REFERENCE.iterdir() if p.is_dir()}
    elif kind == 'sapient':
        expected = {p.name for p in (work / 'sapient').iterdir() if p.is_file()}
    else:
        expected = {p.name for p in (work / kind).iterdir() if p.is_file()}
    if actual.keys() != expected:
        raise ValueError(f'{kind} task inventory mismatch')
    for i, (name, path) in enumerate(sorted(actual.items()), 1):
        allowed(path, [work, work.parent / 'dfm1/tokenized', work.parent / 'dfm4/tokenized_summary'])
        for field in ('tokens', *FIELDS):
            payload = allowed(path / f'{field}.npy',
                [work, work.parent / 'dfm1/tokenized', work.parent / 'dfm4/tokenized_summary'])
            equal_arrays(np.load(payload, mmap_mode='r'),
                         np.load(REFERENCE / name / f'{field}.npy', mmap_mode='r'), f'{name}/{field}')
        if i % 25 == 0 or i == len(actual):
            print(f'Compared {kind} {i}/{len(actual)}', flush=True)
    write_json(work / f'{kind}-token-comparison.json', dict(status='matched', tasks=len(actual),
               arrays=len(actual) * 5, scope='all token/index values'))


def assemble(work):
    recipe = load(work / 'recipe.json')
    require_predecessors(work.parent)
    for kind in ('sapient', 'synth', 'exports'):
        if load(work / f'{kind}-token-comparison.json')['status'] != 'matched':
            raise ValueError(f'Unverified DFM5 addition: {kind}')
    inventory = dict(recipe['inherited'])
    for kind in ('sapient', 'synth', 'exports'):
        for path in (work / f'tokenized_{kind}').iterdir():
            if not path.is_dir():
                continue
            if path.name in inventory:
                raise ValueError('Duplicate union task')
            inventory[path.name] = str(path)
    if len(inventory) != recipe['config']['expected_tasks']:
        raise ValueError(f'Incomplete DFM5 union: {len(inventory)}')
    expected = {p.name for p in REFERENCE.iterdir() if p.is_dir()}
    if inventory.keys() != expected:
        raise ValueError('Final selected source list differs')
    stage = Path(tempfile.mkdtemp(prefix='.union-', dir=work))
    try:
        roots = [work, work.parent / 'dfm1/tokenized', work.parent / 'dfm4/tokenized_summary']
        for name, source in sorted(inventory.items()):
            link(Path(source), stage / name, roots)
        info = load(work / 'tokenized_sapient/tokenizer_info.json')
        if info.pop('template_mode', None) != 'Hrm':
            raise ValueError('Wrong tokenizer template')
        if info != load(REFERENCE / 'tokenizer_info.json'):
            raise ValueError('Historical tokenizer metadata mismatch')
        write_json(stage / 'tokenizer_info.json', info)
        write_json(stage / 'union_manifest.json', dict(tasks=inventory, total_tasks=len(inventory)))
        publish_directory(stage, work / 'tokenized')
        write_json(work / 'selected-sources.json', dict(status='matched', tasks=sorted(inventory)))
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('prepare', 'recover-synth', 'recover-exports',
                                   'verify-sapient', 'verify-synth', 'verify-exports', 'assemble', 'verify-all'))
    p.add_argument('--work', type=Path, required=True)
    args = p.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    with (work / 'stage.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.stage.startswith('verify-'):
            verify_tasks(work, args.stage.removeprefix('verify-'))
        else:
            {'prepare': prepare, 'recover-synth': recover_synth,
             'recover-exports': recover_exports, 'assemble': assemble}[args.stage](work)


if __name__ == '__main__':
    main()
