"""Serial, fail-closed replay from local tokenized reservoirs (not HF recovery).

Each boundary rebuilds its tree, verifies every concatenated token, resamples
all epochs, and compares all index values. A verified token backing may be
reused read-only to avoid terabytes of duplicate writes. No later boundary
may start after a mismatch or an unavailable recipe.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("inst_start", "inst_len", "resp_start", "resp_len")
CHUNK = 8_000_000


def write_json(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(tmp, path)


def read(path):
    return json.loads(path.read_text())


def tasks(root):
    result = {}
    for directory, children, files in os.walk(root, followlinks=True):
        if 'tokens.npy' in files and 'metadata.json' in files:
            path = Path(directory)
            result[str(path.relative_to(root))] = path
            children[:] = []
    return dict(sorted(result.items()))


def materialize_links(root):
    # Historical builders use rglob, which does not descend directory symlinks.
    # Real task directories with read-only input links preserve serial reuse.
    for path in tasks(root).values():
        if path.is_symlink():
            source = path.resolve()
            path.unlink()
            path.mkdir()
            for child in source.iterdir():
                (path / child.name).symlink_to(child.resolve())


def equal_arrays(left, right, label):
    if left.shape != right.shape or left.dtype != right.dtype:
        raise ValueError(f'{label}: shape/dtype mismatch: '
                         f'{left.shape}/{left.dtype} != {right.shape}/{right.dtype}')
    for start in range(0, len(left), CHUNK):
        if not np.array_equal(left[start:start+CHUNK], right[start:start+CHUNK]):
            raise ValueError(f'{label}: values differ in rows {start}:{start+CHUNK}')


def check_backing(tree, reference, progress):
    actual = np.load(reference / 'tokens.npy', mmap_mode='r')
    inventory = tasks(tree)
    if not inventory:
        raise ValueError('Empty tokenized tree')
    sizes = {}
    for i, (name, path) in enumerate(inventory.items(), 1):
        sizes[name] = len(np.load(path / 'tokens.npy', mmap_mode='r'))
        if i == 1 or i % 50 == 0 or i == len(inventory):
            progress(dict(phase='checking_source_headers', tasks_checked=i,
                          total_tasks=len(inventory), task=name))
    if sum(sizes.values()) != len(actual):
        raise ValueError(f'Token backing length mismatch: rebuilt {sum(sizes.values())}, '
                         f'reference {len(actual)}')
    offset = 0
    digest = hashlib.sha256()
    last_report = 0.0
    for name, path in inventory.items():
        source = np.load(path / 'tokens.npy', mmap_mode='r')
        # Match the sampler's offset calculation, not merely source lengths.
        declared = sum(int(np.load(path / f'{f}.npy', mmap_mode='r').sum())
                       for f in ('inst_len', 'resp_len'))
        if declared != len(source):
            raise ValueError(f'{name}: lengths do not span source backing')
        for start in range(0, len(source), CHUNK):
            block = np.asarray(source[start:start+CHUNK], dtype=actual.dtype)
            if not np.array_equal(block, actual[offset+start:offset+start+len(block)]):
                raise ValueError(f'Token mismatch: {name}, offset {start}')
            digest.update(block.tobytes())
            if time.monotonic() - last_report > 30:
                progress(dict(phase='checking_token_payload', task=name,
                              tokens_checked=offset+start+len(block), total_tokens=len(actual)))
                last_report = time.monotonic()
        offset += len(source)
    return dict(tokens=offset, payload_sha256=digest.hexdigest(), tasks=len(inventory))


def tree_command(version, output):
    tree = lambda v: output / f'dfm{v}' / 'tokenized'
    script = ROOT / f'scripts/build_tokenized_dfm{version}_tree.py'
    command = [sys.executable, str(script), '--output', str(tree(version))]
    if version == 2:
        command += ['--base-tokenized', str(tree(1))]
    elif version == 3:
        command += ['--roots', str(tree(2)), str(ROOT / 'data/tokenized_dfm3_common_pile_tasks')]
    elif version == 4:
        command += ['--roots', str(tree(3)),
                    str(ROOT / 'data/tokenized_dfm4_paragraph_reorder_dynaword_windows'),
                    str(ROOT / 'data/tokenized_dfm4_paragraph_reorder_common_existing'),
                    str(ROOT / 'data/tokenized_dfm4_summarization')]
    elif version == 5:
        # Historical reselection, not an append to DFM4.
        command += ['--mixed-tokenized', str(tree(1))]
    elif version == 6:
        # Tokenizer migration: do not reuse old-tokenizer payloads as Gemma.
        command += ['--raw-tokenized', str(ROOT / 'data/tokenized_dfm6_direct_jinja')]
    elif version in (7, 8):
        command += ['--base-tokenized', str(tree(version-1))]
    elif version in (10, 11):
        command += ['--base', str(tree(version-1))]
    else:
        raise RuntimeError(f'DFM{version} serial recipe not yet recovered; '
                           'refusing to substitute the production predecessor')
    return command


def replay_boundary(version, output, progress):
    name = 'dfm' if version == 1 else f'dfm{version}'
    work = output / f'dfm{version}'
    work.mkdir(exist_ok=True)
    tree, sample = work / 'tokenized', work / 'sampled'
    reference = ROOT / 'data' / f'sampled_{name}'
    policy = ROOT / 'data_io' / f'prefix_config_{name}.yaml'
    if version == 1:
        if not tree.exists():
            tree.mkdir()
            source = ROOT / 'data/tokenized_mixed'
            for key, path in tasks(source).items():
                target = tree / key
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(path.resolve())
            (tree / 'tokenizer_info.json').symlink_to((source / 'tokenizer_info.json').resolve())
    else:
        command = tree_command(version, output)
        if not tree.exists():
            write_json(work / 'tree-command.json', command)
            with (work / 'tree.log').open('w') as log:
                subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    materialize_links(tree)
    progress(dict(phase='checking_token_payload'))
    backing = check_backing(tree, reference, progress)
    write_json(work / 'backing-verified.json', backing)
    sample.mkdir(exist_ok=True)
    target = sample / 'tokens.npy'
    if not target.exists():
        target.symlink_to((reference / 'tokens.npy').resolve())
    epochs = sorted(reference.glob('epoch_*'), key=lambda p: int(p.name.split('_')[-1]))
    if [p.name for p in epochs] != [f'epoch_{i}' for i in range(len(epochs))] or not epochs:
        raise ValueError('Reference epochs missing or noncontiguous')
    frozen_policy = work / 'prefix_config.yaml'
    if not frozen_policy.exists():
        shutil.copyfile(policy, frozen_policy)
    command = [sys.executable, str(ROOT / 'data_io/sample_tokenized.py'),
               f'tokenized_path={tree}', f'output_path={sample}',
               f'prefix_config_path={frozen_policy}', f'epochs={len(epochs)}',
               'seed=0', 'concat_workers=1', 'reuse_tokens=true']
    write_json(work / 'sample-command.json', command)
    progress(dict(phase='resampling', epochs=len(epochs)))
    with (work / 'sampling.log').open('w') as log:
        subprocess.run(command, cwd=ROOT / 'data_io', stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    progress(dict(phase='comparing_all_indices'))
    for epoch in epochs:
        for field in FIELDS:
            rel = Path(epoch.name) / f'{field}.npy'
            equal_arrays(np.load(sample / rel, mmap_mode='r'),
                         np.load(reference / rel, mmap_mode='r'), str(rel))
    if read(sample / 'metadata.json') != read(reference / 'metadata.json'):
        raise ValueError('Metadata mismatch; inspect both metadata.json files')
    return dict(status='matched', scope='local_reservoir_full_payload_and_all_epoch_indices',
                cold_hf_rebuild_verified=False, backing=backing, epochs=len(epochs))


def run_serial(output, through, boundary=replay_boundary):
    for version in range(1, through+1):
        work = output / f'dfm{version}'
        done = work / 'verified.json'
        if done.exists():
            raise RuntimeError('Existing verification receipt: use a fresh output directory '
                               'until input fingerprint resume validation is implemented')
        def progress(value):
            value = dict(version=version, time=time.time(), **value)
            write_json(output / 'progress.json', value)
            print(json.dumps(value), flush=True)
        progress(dict(phase='starting'))
        try:
            result = boundary(version, output, progress)
            if result.get('status') != 'matched':
                raise ValueError(f'Boundary did not match: {result}')
            work.mkdir(exist_ok=True)
            write_json(done, result)
        except Exception as exc:
            progress(dict(phase='blocked', error=f'{type(exc).__name__}: {exc}'))
            raise
        progress(dict(phase='matched'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--through', type=int, choices=range(1, 16), default=15)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        write_json(output / 'scope.json', dict(
            mode='serial-local-reservoir-replay', cold_hf_rebuild_verified=False,
            production_data_modified=False, through=args.through,
            pid=os.getpid(), inputs='existing tokenized additions; predecessor trees rebuilt serially'))
        run_serial(output, args.through)


if __name__ == '__main__':
    main()
