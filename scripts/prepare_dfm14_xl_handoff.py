"""CPU-only verified-transfer gate and exact one-pass DFM14 packing budget."""
import argparse
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import file_hash, load, lock, write_json
from dfm12.prepare_xl_epoch11 import count_steps
from scripts.transfer_sampled_dfm14 import EXPECTED, PINS, SOURCE as REMOTE_SOURCE

START = 3250000
ROWS = 406830651
SAMPLE = ROOT / 'data/sampled_dfm14'
CONTROL = ROOT / 'data/dfm14/xl-from-dfm13-step3250000'
OUTPUT = ROOT / 'checkpoints/dfm14/XL-from-dfm13-step3250000'
SOURCE = ROOT / 'checkpoints/dfm13/XL-from-dfm12-step3150000'
RUN = 'dfm8-xl-from-dfm6-dfm7-epoch5-clean-full'


def sample_contract(sample=SAMPLE):
    receipt_path = sample / 'local-transfer-verified.json'
    if not receipt_path.exists():
        return None
    receipt = load(receipt_path)
    if (receipt.get('source') != REMOTE_SOURCE or receipt.get('host') != 'ssh.cloud.sdu.dk'
            or receipt.get('port') != 6768 or receipt.get('epoch_tokens') != EXPECTED
            or receipt.get('pins') != PINS):
        raise ValueError('Unexpected verified DFM14 transfer identity')
    for name, sha in PINS.items():
        path = sample / name if name == 'metadata.json' else ROOT / name
        if file_hash(path) != sha:
            raise ValueError('Transfer/tokenizer pin drift: ' + name)
    metadata = load(sample / 'metadata.json')
    if metadata['max_seq_len'] != 4097:
        raise ValueError('Wrong sampled context')
    import numpy as np
    for field in ('inst_start', 'inst_len', 'resp_start', 'resp_len'):
        if len(np.load(sample / 'epoch_0' / (field + '.npy'), mmap_mode='r')) != ROWS:
            raise ValueError('Wrong epoch0 row count')
    paths = [receipt_path, sample / 'metadata.json', sample / 'tokens.npy',
             sample / 'build-receipt.json']
    paths += [sample / 'epoch_0' / (f + '.npy')
              for f in ('inst_start', 'inst_len', 'resp_start', 'resp_len')]
    return dict(receipt_sha256=file_hash(receipt_path), epoch_tokens=EXPECTED[0], rows=ROWS,
                metadata_sha256=file_hash(sample / 'metadata.json'),
                file_signatures={str(p.resolve()): [p.stat().st_size, p.stat().st_mtime_ns,
                                                     p.stat().st_ino] for p in paths},
                transport=receipt['transport'], independent_full_token_hash=False)


def proposal(contract, budget):
    if budget['packed_rows'] != ROWS or budget['optimizer_steps'] <= 50000:
        raise ValueError('Unexpected exact one-epoch packing budget')
    end = START + budget['optimizer_steps']
    return dict(start_step=START, end_step=end, packing=budget, sample_contract=contract,
                dataset=str(SAMPLE), dataset_epoch_index=0, dataset_passes=1,
                identity_repeat=0, identity_policy_basis='owner corrected remote sample authorization',
                checkpoint_path=str(OUTPUT), source_checkpoint=str(SOURCE),
                source_tag=f'step_{START}', wandb_run_id=RUN, wandb_project='DFM5',
                lr=dict(base=3e-4, lr_auto=True, warmup_steps=0, rewarm_steps=0,
                        min_ratio=1.0, decay_start_step=None, decay_end_step=None),
                eval_steps=[*range(START + 50000, end, 50000), end],
                training_launched=False)


def prepare(control=CONTROL, watch=False):
    with lock(control / '.prepare.lock'):
        while (contract := sample_contract()) is None:
            write_json(control / 'progress.json', dict(phase='waiting_verified_transfer',
                       receipt=str(SAMPLE / 'local-transfer-verified.json'), time=time.time()))
            if not watch:
                return None
            time.sleep(30)
        budget_path = control / 'packing.json'
        if budget_path.exists():
            cached = load(budget_path)
            if cached['sample_contract'] != contract:
                raise ValueError('Sample changed after packing')
            budget = cached['packing']
        else:
            write_json(control / 'progress.json', dict(phase='counting_exact_packing', time=time.time()))
            budget = count_steps(SAMPLE / 'epoch_0', batch_tokens=16384, world_size=8, gas=2)
            if sample_contract() != contract:
                raise ValueError('Sample changed during exact packing')
            write_json(budget_path, dict(sample_contract=contract, packing=budget))
        run = proposal(contract, budget)
        write_json(control / 'prepared.json', run)
        write_json(control / 'progress.json', dict(phase='prepared_not_training',
                   end_step=run['end_step'], time=time.time()))
        return run


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--control', type=Path, default=CONTROL)
    args = parser.parse_args()
    prepare(args.control, args.watch)
