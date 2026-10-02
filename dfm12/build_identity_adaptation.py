"""Compact DA/EN identity rehearsal corpus; no training or GPU work."""
import argparse
from pathlib import Path
import os
import re

import numpy as np

from .build_training import FIELDS
from .io import file_hash, load, lock, write_json


def indices(path):
    arrays = {key: np.load(path / f'{key}.npy', mmap_mode='r') for key in FIELDS}
    if len({len(a) for a in arrays.values()}) != 1:
        raise ValueError(f'Mismatched source indices: {path}')
    return arrays


def select_rows(arrays, budget, rng, repeat, mean_length=None):
    """Random coverage, without a full permutation of a huge inherited epoch."""
    n = len(arrays['inst_len'])
    if n == 0 or budget <= 0:
        raise ValueError('Empty supply or nonpositive budget')
    if repeat:
        lengths = np.asarray(arrays['inst_len'] + arrays['resp_len'], dtype=np.int64)
        full_passes = int(budget // int(lengths.sum()))
        selections = [rng.permutation(n) for _ in range(full_passes)]
        remaining = budget - full_passes * int(lengths.sum())
        if remaining:
            order = rng.permutation(n)
            count = int(np.searchsorted(np.cumsum(lengths[order]), remaining)) + 1
            selections.append(order[:count])
        selected = np.concatenate(selections)
    else:
        if mean_length is None or mean_length <= 0:
            raise ValueError('A positive mean length is required for broad sampling')
        count = min(n, max(32, int(budget / mean_length * 1.2)))
        while True:
            selected = rng.choice(n, size=count, replace=False)
            lengths = (arrays['inst_len'][selected] + arrays['resp_len'][selected]).astype(np.int64)
            cumulative = np.cumsum(lengths)
            if cumulative[-1] >= budget:
                selected = selected[:int(np.searchsorted(cumulative, budget)) + 1]
                break
            if count == n:
                raise ValueError('Insufficient broad replay supply')
            count = min(n, count * 2)
    total = int(arrays['inst_len'][selected].sum() + arrays['resp_len'][selected].sum())
    return selected.astype(np.int64), total


def check_tokenizer(base_info, identity_info):
    for key in ('vocab_size', 'enable_thinking', 'template_mode'):
        if base_info.get(key) != identity_info.get(key):
            raise ValueError(f'Tokenizer mismatch: {key}')
    for key in ('tokenizer_path', 'chat_template_path'):
        if file_hash(base_info[key]) != file_hash(identity_info[key]):
            raise ValueError(f'Tokenizer bytes mismatch: {key}')


def compact_copy(sources, output, rng):
    """Copy only selected spans, in storage order; repeat rows reuse token spans."""
    for source in sources:
        unique, inverse = np.unique(source['selected'], return_inverse=True)
        source['unique'], source['inverse'] = unique, inverse
    stored = sum(int(s['arrays']['inst_len'][s['unique']].sum()
                     + s['arrays']['resp_len'][s['unique']].sum()) for s in sources)
    tokens = np.lib.format.open_memmap(output / 'tokens.npy', mode='w+', dtype=np.uint32, shape=(stored,))
    chunks = {key: [] for key in FIELDS}
    labels, cursor = [], 0
    for label, source in enumerate(sources):
        a, unique = source['arrays'], source['unique']
        mapped = {key: np.empty(len(unique), dtype=np.uint64) for key in FIELDS}
        order = np.argsort(a['inst_start'][unique])
        for position in order:
            row = unique[position]
            for part in ('inst', 'resp'):
                start, length = int(a[part + '_start'][row]), int(a[part + '_len'][row])
                if start < 0 or length < 1 or start + length > len(source['tokens']):
                    raise ValueError('Invalid source token span')
                mapped[part + '_start'][position] = cursor
                mapped[part + '_len'][position] = length
                tokens[cursor:cursor + length] = source['tokens'][start:start + length]
                cursor += length
        for key in FIELDS:
            chunks[key].append(mapped[key][source['inverse']])
        labels.append(np.full(len(source['selected']), label, dtype=np.uint8))
        print('copied', source['name'], 'unique rows', len(unique), 'tokens written', cursor, flush=True)
    tokens.flush()
    del tokens
    if cursor != stored:
        raise ValueError('Token copy accounting mismatch')
    order = rng.permutation(sum(len(x) for x in labels))
    result = {key: np.concatenate(value)[order] for key, value in chunks.items()}
    return result, np.concatenate(labels)[order], stored


def packing_report(arrays, labels, steps, global_batch, gas, world_size):
    from multipack_sampler import MultipackDistributedBatchSampler
    if global_batch % (gas * world_size):
        raise ValueError('Global batch not divisible by GAS * world size')
    lengths = (arrays['inst_len'] + arrays['resp_len'] - 1).astype(np.int64)
    sampler = MultipackDistributedBatchSampler(
        global_batch // (gas * world_size), lengths, num_replicas=world_size,
        rank=0, drop_last_batch=True)
    batches, boundary = 0, None
    for _, info in sampler.iter_with_info():
        batches += 1
        if batches == steps * gas:
            boundary = info['global_row_end']
    if boundary is None:
        raise ValueError(f'Only {batches // gas} packed steps available; need {steps}')
    used = lengths[:boundary]
    return dict(available_optimizer_steps=batches // gas, planned_optimizer_steps=steps,
                world_size=world_size, gas=gas, global_batch=global_batch,
                row_end_at_stop=boundary, nonpadding_tokens_at_stop=int(used.sum()),
                identity_nonpadding_tokens_at_stop=int(used[labels[:boundary] != 0].sum()),
                identity_fraction_at_stop=float(used[labels[:boundary] != 0].sum() / used.sum()))


def continuation_contract(start_step, steps, start_checkpoint, data_epoch):
    if start_step < 0 or steps < 1 or data_epoch < 0:
        raise ValueError('Invalid continuation step/epoch')
    match = re.fullmatch(r'(epoch|step|ephemeral_step)_(\d+)', start_checkpoint)
    if not match:
        raise ValueError('Invalid start checkpoint tag')
    kind, number = match.group(1), int(match.group(2))
    if kind != 'epoch' and number != start_step:
        raise ValueError('Checkpoint tag/start step mismatch')
    if kind == 'epoch' and number != data_epoch:
        raise ValueError('Epoch checkpoint/data epoch mismatch')
    return dict(start_checkpoint=start_checkpoint, start_step=start_step,
                stop_after_step=start_step + steps, data_epoch_index=data_epoch,
                trainer_epoch=data_epoch + 1, fresh_data_start=True,
                required_batch_in_epoch=0, required_global_row_cursor_in_epoch=0,
                requires_isolated_zero_cursor_resume_metadata=kind != 'epoch')


def verify_identity_manifest(path):
    from . import identity_expansion, identity_repair_expansion, identity_correction
    manifest = load(path)
    verifiers = {identity_expansion.SCHEMA: identity_expansion.verify,
                 identity_repair_expansion.SCHEMA: identity_repair_expansion.verify,
                 identity_correction.SCHEMA: identity_correction.verify}
    if manifest.get('schema') not in verifiers:
        raise ValueError('Unsupported identity manifest schema')
    if Path(path).name != 'manifest.json':
        raise ValueError('Identity manifest must be manifest.json')
    verifiers[manifest['schema']](Path(path).parent)
    return manifest


def build(base, tokenized, output, steps=1000, global_batch=262144, seed=20260926,
          start_step=2877261, start_checkpoint='epoch_10', data_epoch=10,
          gas=2, world_size=8, identity_manifest=None):
    contract = continuation_contract(start_step, steps, start_checkpoint, data_epoch)
    if seed < 0 or global_batch <= 0 or gas < 1 or world_size < 1:
        raise ValueError('Invalid sampling or packing parameters')
    if global_batch % (gas * world_size):
        raise ValueError('Global batch not divisible by GAS * world size')
    identity_manifest_data = None
    if identity_manifest is not None:
        identity_manifest_data = verify_identity_manifest(identity_manifest)
    output.mkdir(parents=True, exist_ok=True)
    with lock(output / '.build.lock'):
        if (output / 'tokens.npy').exists() or (output / 'metadata.json').exists():
            raise FileExistsError('Refusing to overwrite an existing/partial adaptation build')
        metadata = load(base / 'metadata.json')
        check_tokenizer(metadata['tokenizer_info'], load(tokenized / 'tokenizer_info.json'))
        rng = np.random.default_rng(seed)
        budget = steps * global_batch
        broad = indices(base / 'epoch_0')
        chosen, total = select_rows(broad, round(budget * .95), rng, False,
                                   metadata['total_length'] / len(broad['inst_len']))
        sources = [dict(name='DFM11', path=str(base), arrays=broad, selected=chosen,
                        rendered_tokens=total, tokens=np.load(base / 'tokens.npy', mmap_mode='r'))]
        identity = []
        for language in ('da', 'en'):
            path = tokenized / f'dfm12-identity-xl-full-bp-{language}__train-00000.jsonl.gz'
            a = indices(path)
            supply = int(a['inst_len'].sum() + a['resp_len'].sum())
            if identity_manifest_data is not None:
                expected = identity_manifest_data['languages'][language]['counts']['merged']
                if len(a['inst_len']) != expected['assistant_targets'] or supply != expected['rendered_tokens']:
                    raise ValueError('Tokenized identity counts do not match sealed source')
                source_info = identity_manifest_data
                for key, pin in (('tokenizer_path', 'tokenizer'), ('chat_template_path', 'template')):
                    if file_hash(metadata['tokenizer_info'][key]) != source_info[pin]['sha256']:
                        raise ValueError('Identity manifest tokenizer/template mismatch')
            identity.append((language, path, a, supply))
        identity_supply = sum(x[3] for x in identity)
        for language, path, a, supply in identity:
            selected, total = select_rows(a, round(budget * .05 * supply / identity_supply), rng, True)
            sources.append(dict(name='identity-' + language, path=str(path), arrays=a, selected=selected,
                                rendered_tokens=total, unique_supply_tokens=supply,
                                tokens=np.load(path / 'tokens.npy', mmap_mode='r')))
        for s in sources:
            lengths = s['arrays']['inst_len'][s['selected']] + s['arrays']['resp_len'][s['selected']]
            if np.any(lengths > metadata['max_seq_len']) or np.any(lengths < 2):
                raise ValueError('Out-of-context source row; do not silently truncate')
            np.save(output / (s['name'] + '-source-rows.npy'), s['selected'])
        arrays, labels, stored = compact_copy(sources, output, rng)
        packed = packing_report(arrays, labels, steps, global_batch, gas=gas, world_size=world_size)
        epoch = output / 'epoch_0'
        epoch.mkdir()
        for key, a in arrays.items():
            np.save(epoch / (key + '.npy'), a)
        np.save(output / 'source-labels.npy', labels)
        # Trainer epoch is one-based; its data index is zero-based.
        if data_epoch:
            (output / f'epoch_{data_epoch}').symlink_to('epoch_0', target_is_directory=True)
        total = sum(s['rendered_tokens'] for s in sources)
        report = dict(steps=steps, global_batch=global_batch, nominal_tokens=budget,
            rendered_tokens=total, identity_fraction=sum(s['rendered_tokens'] for s in sources[1:]) / total,
            identity_unique_tokens=identity_supply, stored_tokens=stored, seed=seed,
            sources=[{k: s[k] for k in ('name','path','rendered_tokens')} | dict(
                sampled_rows=len(s['selected']), unique_rows=len(s['unique'])) for s in sources],
            source_metadata_sha256=file_hash(base / 'metadata.json'), packing=packed,
            **contract,
            training_launched=False, identity_repeat_10_applied=False)
        report['builder_sha256'] = file_hash(Path(__file__))
        report['tokenized_source_files'] = {
            str(path / filename): file_hash(path / filename)
            for _, path, _, _ in identity
            for filename in ('tokens.npy', *(f'{key}.npy' for key in FIELDS), 'metadata.json')}
        report['tokenizer_info_sha256'] = file_hash(tokenized / 'tokenizer_info.json')
        if identity_manifest is not None:
            report['identity_manifest'] = str(identity_manifest.resolve())
            report['identity_manifest_sha256'] = file_hash(identity_manifest)
        report['data_config'] = dict(path=str(output.resolve()), target_only=True)
        report['training_overrides_required'] = dict(
            epochs=data_epoch + 1, training_total_steps=start_step + steps,
            stop_after_step=start_step + steps, resume_checkpoint_tag=start_checkpoint)
        report['output_files'] = {str(path.relative_to(output)): file_hash(path)
                                  for path in [output / 'tokens.npy', output / 'source-labels.npy',
                                               *sorted(epoch.glob('*.npy')),
                                               *sorted(output.glob('*-source-rows.npy'))]}
        write_json(output / 'build-receipt.json', report)
        metadata['total_length'] = total
        for key in ('tokenizer_path', 'chat_template_path'):
            metadata['tokenizer_info'][key] = os.path.relpath(Path(metadata['tokenizer_info'][key]).resolve())
        metadata['tokenizer_info']['tokenizer_path_base'] = 'repo_root'
        write_json(output / 'metadata.json', metadata)
        print(report, flush=True)
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--base', type=Path, default=Path('data/sampled_dfm11'))
    parser.add_argument('--tokenized', type=Path, default=Path('data/tokenized_dfm12_additions'))
    parser.add_argument('--output', type=Path, default=Path('data/sampled_dfm11_identity_da_en_1000steps'))
    parser.add_argument('--steps', type=int, default=1000)
    parser.add_argument('--global-batch', type=int, default=262144)
    parser.add_argument('--seed', type=int, default=20260926)
    parser.add_argument('--start-step', type=int, default=2877261)
    parser.add_argument('--start-checkpoint', default='epoch_10')
    parser.add_argument('--data-epoch', type=int, default=10)
    parser.add_argument('--gas', type=int, default=2)
    parser.add_argument('--world-size', type=int, default=8)
    parser.add_argument('--identity-manifest', type=Path)
    args = parser.parse_args()
    if args.steps < 1:
        parser.error('Steps must be positive')
    build(**vars(args))
