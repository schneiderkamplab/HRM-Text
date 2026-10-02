"""CPU-only one-epoch DFM12 mix, without identity, and exact packed step budget."""
from pathlib import Path
import argparse
import subprocess
import sys
import time

import numpy as np
import yaml

from .build_training import combine, merge_epoch, FIELDS
from .io import file_hash, load, lock, write_json

ROOT = Path('data/dfm12/xl-epoch11-noidentity')
BUILD = Path('data/dfm12/training-build-completed-campaign-20260929')
TOKENS = Path('data/tokenized_dfm12_additions-completed-campaign-20260929')
ADDITIONS = Path('data/sampled_dfm12_xl_epoch11_noidentity_additions')
OUTPUT = Path('data/sampled_dfm12_xl_epoch11_noidentity')
SOURCE = Path('checkpoints/dfm11/XL-from-dfm10-epoch9')


def sampling_policy(sources):
    return [{'prefix': s['name'] + '__',
             'repeat': 0 if s['name'].startswith('dfm12-identity-') else s['repeat']}
            for s in sources]


def count_steps(directory, batch_tokens=16384, world_size=8, gas=2):
    from multipack_sampler import MultipackDistributedBatchSampler
    lengths = (np.load(directory / 'inst_len.npy', mmap_mode='r')
               + np.load(directory / 'resp_len.npy', mmap_mode='r') - 1)
    sampler = MultipackDistributedBatchSampler(batch_tokens, lengths,
                                               world_size, 0, drop_last_batch=True)
    batches = 0
    for _, info in sampler.iter_with_info():
        batches += 1
        if batches % 100000 == 0:
            print('packing', batches, 'microbatches; row', info['global_row_end'], '/', len(lengths), flush=True)
    return dict(microbatches=batches, optimizer_steps=batches // gas,
                dropped_accumulation_microbatches=batches % gas,
                packed_rows=len(lengths), packing_efficiency=sampler.efficiency())


def publish_run(budget, token_count):
    state = load(SOURCE / 'checkpoint_state_epoch_10.json')
    end = state['step'] + budget['optimizer_steps']
    if end <= 2950000:
        raise ValueError('Epoch too short for requested rewarm and cooldown')
    write_json(ROOT / 'run.json', dict(
        start_step=state['step'], end_step=end, epochs=11, dataset=str(OUTPUT),
        source_checkpoint=str(SOURCE), source_tag='epoch_10',
        checkpoint_path='checkpoints/dfm12/XL-from-dfm11-epoch10-noidentity',
        wandb_project='DFM5', wandb_run_id='dfm8-xl-from-dfm6-dfm7-epoch5-clean-full',
        lr=3e-4, lr_auto=True, lr_rewarm_steps=2900000-state['step'],
        lr_rewarm_start_step=state['step'], lr_rewarm_start_ratio=1/30,
        lr_min_ratio=1/30, lr_decay_start_step=3250000, lr_decay_end_step=end,
        identity_repeat=0, token_count=token_count, packing=budget,
        specification_sha256=file_hash(ROOT / 'specification.json'), completed=time.time()))


def prepare_budget():
    """Count the same deterministic indices while the large token file copies."""
    with lock(ROOT / '.budget.lock'):
        directory = ROOT / 'budget-indices'
        receipt = ROOT / 'budget-indices.json'
        if not receipt.exists():
            offset = len(np.load('data/sampled_dfm11/tokens.npy', mmap_mode='r'))
            report = merge_epoch(Path('data/sampled_dfm11/epoch_0'), ADDITIONS / 'epoch_0',
                                 directory, offset, 0)
            write_json(receipt, dict(report=report,
                hashes={field: file_hash(directory / (field + '.npy')) for field in FIELDS}))
        budget_path = ROOT / 'packed-steps.json'
        if not budget_path.exists():
            write_json(budget_path, count_steps(directory))
        report = load(receipt)['report']
        publish_run(load(budget_path), report['base'] + report['additions'])
        print('Exact budget ready:', load(ROOT / 'run.json')['end_step'], flush=True)


def verify_ready():
    with lock(ROOT / '.ready.lock'):
        while not all(p.exists() for p in (OUTPUT / 'metadata.json', ROOT / 'budget-indices.json', ROOT / 'run.json')):
            print('Waiting for complete sampled token/index publication', flush=True)
            time.sleep(30)
        receipt = load(ROOT / 'budget-indices.json')
        for field, checksum in receipt['hashes'].items():
            if file_hash(OUTPUT / 'epoch_10' / (field + '.npy')) != checksum:
                raise ValueError('Published index differs from exact packing budget: ' + field)
        if load(OUTPUT / 'epoch-mapping.json') != load(ROOT / 'specification.json'):
            raise ValueError('Published epoch mapping mismatch')
        config = load(ROOT / 'run.json')
        if load(OUTPUT / 'metadata.json')['total_length'] != config['token_count']:
            raise ValueError('Published token count mismatch')
        write_json(ROOT / 'ready.json', dict(dataset=str(OUTPUT), end_step=config['end_step'],
            metadata_sha256=file_hash(OUTPUT / 'metadata.json'), indices=receipt['hashes'],
            specification_sha256=config['specification_sha256'], completed=time.time()))
        print('Training data READY', OUTPUT, flush=True)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    with lock(ROOT / '.lock'):
        checkpoint = SOURCE / 'checkpoint_state_epoch_10.json'
        state = load(checkpoint)
        if state['epoch'] != 10 or state['step'] != 2877261 or state['batch_in_epoch'] != 0:
            raise ValueError('Unexpected XL epoch_10 checkpoint')
        sources = load(BUILD / 'sources.json')
        policy = sampling_policy(sources)
        specification = dict(source_manifest_sha256=file_hash(BUILD / 'sources.json'),
                             source_checkpoint_sha256=file_hash(checkpoint),
                             identity_repeat=0, base_epoch_index=0, output_epoch_index=10,
                             global_batch_size=262144, world_size=8, gradient_accumulation_steps=2,
                             sampling_seed=10, policy=policy)
        spec_path = ROOT / 'specification.json'
        if spec_path.exists() and load(spec_path) != specification:
            raise ValueError('Build specification changed')
        write_json(spec_path, specification)
        prefix = ROOT / 'prefix_config.yaml'
        prefix.write_text(yaml.safe_dump(policy, sort_keys=False))
        if not (ADDITIONS / 'metadata.json').exists():
            subprocess.run([sys.executable, '-u', 'data_io/sample_tokenized.py',
                            f'tokenized_path={TOKENS}', f'output_path={ADDITIONS}',
                            f'prefix_config_path={prefix}', 'epochs=1', 'seed=10',
                            'concat_workers=1', 'skip_unmatched=true'], check=True)
        staging = OUTPUT.with_name(OUTPUT.name + '.building')
        if not OUTPUT.exists():
            if not (staging / 'metadata.json').exists():
                combine(Path('data/sampled_dfm11'), ADDITIONS, staging, 1)
            if (staging / 'epoch_0').exists():
                (staging / 'epoch_0').rename(staging / 'epoch_10')
            if not (staging / 'epoch_10/inst_len.npy').exists():
                raise ValueError('Missing dataset epoch index 10')
            write_json(staging / 'epoch-mapping.json', specification)
            staging.rename(OUTPUT)
        if load(OUTPUT / 'epoch-mapping.json') != specification:
            raise ValueError('Published dataset specification mismatch')
        budget_path = ROOT / 'packed-steps.json'
        if not budget_path.exists():
            budget = count_steps(OUTPUT / 'epoch_10')
            write_json(budget_path, budget)
        budget = load(budget_path)
        end = state['step'] + budget['optimizer_steps']
        if budget['optimizer_steps'] <= 60000:
            raise ValueError('Epoch too short for requested rewarm and cooldown')
        publish_run(budget, load(OUTPUT / 'metadata.json')['total_length'])
        print('READY', ROOT / 'run.json', 'steps', budget['optimizer_steps'], 'end', end, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--budget-only', action='store_true')
    modes.add_argument('--verify-ready', action='store_true')
    args = parser.parse_args()
    if args.budget_only:
        prepare_budget()
    elif args.verify_ready:
        verify_ready()
    else:
        main()
