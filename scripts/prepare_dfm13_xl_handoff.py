"""Prepare a readiness-gated XL handoff budget; never launch or edit training."""
import argparse
from pathlib import Path
import time

from dfm12.io import file_hash, load, lock, write_json
from dfm12.prepare_xl_epoch11 import count_steps


REPO = Path(__file__).resolve().parents[1]
START = 3_150_000
CONTROL = REPO / 'data/dfm13/xl-from-dfm12-step3150000'
SAMPLE = REPO / 'data/sampled_dfm13'
COMPLETION = REPO / 'data/dfm13/sampling-20261005-v1/completion.json'


def sample_contract(receipt_path, sample):
    """Trust only the final scanner's receipt, pinned to the current composition."""
    if not receipt_path.is_file():
        return None
    receipt = load(receipt_path)
    validation = receipt.get('validation', {})
    if (receipt.get('complete') is not True or receipt.get('epochs') != 1
            or Path(receipt['output']).resolve() != sample.resolve()
            or validation.get('full_token_vocabulary_scan') is not True
            or validation.get('full_index_bounds_scan') is not True):
        raise ValueError('Sampling completion is not a full verified one-epoch publication')
    metadata = load(sample / 'metadata.json')
    if (metadata['total_length'] != validation['epoch_tokens']
            or metadata['max_seq_len'] != validation['max_seq_len']
            or metadata['max_seq_len'] != 4097):
        raise ValueError('Sample metadata disagrees with verified scanner output')
    files = [sample / 'tokens.npy', sample / 'metadata.json']
    files += [sample / 'epoch_0' / (name + '.npy')
              for name in ('inst_start', 'inst_len', 'resp_start', 'resp_len')]
    signatures = {}
    for path in files:
        stat = path.stat()
        signatures[str(path.resolve())] = [stat.st_size, stat.st_mtime_ns, stat.st_ino]
    return dict(completion_sha256=file_hash(receipt_path),
                metadata_sha256=file_hash(sample / 'metadata.json'),
                composition_sha256=receipt['composition_sha256'],
                assembly_sha256=receipt['assembly_sha256'],
                reconciliation_sha256=receipt['reconciliation_sha256'],
                validation=validation, file_signatures=signatures)


def require_current_provenance(contract):
    additions = load(REPO / 'data/dfm13/authoritative-additions.json')
    composition = load(REPO / 'data/dfm13/authoritative-composition.json')
    reconciliation = REPO / 'data/dfm13/all-source-finalization-20261004-v1/sampling-reconciliation.json'
    if (additions['assembly_sha256'] != contract['assembly_sha256']
            or composition['additions_sha256'] != contract['assembly_sha256']
            or composition['composition_sha256'] != contract['composition_sha256']
            or file_hash(Path(additions['root']) / 'assembly.json') != contract['assembly_sha256']
            or file_hash(Path(composition['root']) / 'composition.json') != contract['composition_sha256']
            or file_hash(reconciliation) != contract['reconciliation_sha256']):
        raise ValueError('Authoritative dataset provenance changed after sampling')
    from scripts.queue_dfm13_fo_instruct_successor import require_included
    require_included(Path(additions['root']))


def proposal(contract, budget):
    steps = budget['optimizer_steps']
    if steps <= 50_000:
        raise ValueError('Unexpectedly short DFM13 epoch')
    end = START + steps
    return dict(
        status='prepared_not_scheduled', start_step=START, end_step=end,
        source_checkpoint='checkpoints/dfm12/XL-from-dfm11-epoch10-noidentity',
        source_tag='step_3150000', dataset=str(SAMPLE), dataset_epoch_index=0,
        dataset_passes=1, packing=budget, sample_contract=contract,
        checkpoint_path='checkpoints/dfm13/XL-from-dfm12-step3150000',
        wandb_project='DFM5', wandb_run_id='dfm8-xl-from-dfm6-dfm7-epoch5-clean-full',
        global_batch_size=262144, gradient_accumulation_steps=2, world_size=8,
        proposed_lr=dict(lr=3e-4, lr_auto=True, rewarm_steps=0,
                         decay_start_step=end-50000, decay_end_step=end,
                         final_lr=1e-5),
        eval_steps=[*range(START+50000, end, 50000), end],
        resume_policy=dict(preserve_optimizer=True, preserve_ema=True,
                           dataset_cursor='reset_in_isolated_resume_metadata_only',
                           require_carry_policy='none',
                           eval_epoch='3150K fractional DFM12 epoch + DFM13 row fraction'),
        activation_gates=['3150K checkpoint completely written',
                          '3150K evaluation and averages completed and reviewed',
                          'sample provenance unchanged',
                          'isolated resume metadata and scheduler rows validated'],
        training_launched=False, active_plan_changed=False)


def prepare(watch=False):
    with lock(CONTROL / '.lock'):
        while True:
            contract = sample_contract(COMPLETION, SAMPLE)
            if contract is not None:
                break
            write_json(CONTROL / 'progress.json', dict(
                phase='waiting_verified_sample', receipt=str(COMPLETION),
                start_step=START, training_launched=False, time=time.time()))
            if not watch:
                return
            time.sleep(60)
        require_current_provenance(contract)
        write_json(CONTROL / 'progress.json', dict(phase='counting_exact_packing', time=time.time()))
        budget_path = CONTROL / 'packing.json'
        if budget_path.exists():
            cached = load(budget_path)
            if cached['sample_contract'] != contract:
                raise ValueError('Sample changed since packing; do not reuse budget')
            budget = cached['packing']
        else:
            budget = count_steps(SAMPLE / 'epoch_0', batch_tokens=16384, world_size=8, gas=2)
            if sample_contract(COMPLETION, SAMPLE) != contract:
                raise ValueError('Sample changed during packing')
            write_json(budget_path, dict(sample_contract=contract, packing=budget))
        require_current_provenance(contract)
        write_json(CONTROL / 'prepared.json', proposal(contract, budget))
        write_json(CONTROL / 'progress.json', dict(phase='prepared_not_scheduled', time=time.time()))
        print('Prepared DFM13 handoff; no training or scheduler changes:', CONTROL, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    try:
        prepare(args.watch)
    except Exception as exc:
        write_json(CONTROL / 'failure.json', dict(error=str(exc), time=time.time()))
        raise
