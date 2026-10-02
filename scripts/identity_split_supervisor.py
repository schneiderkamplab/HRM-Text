"""Resume the authorized 10K course with a verified fresh 95/2.5/2.5 mixture."""
import argparse
import copy
import os
from pathlib import Path
import signal
import sys
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12 import build_identity_split as builder
from dfm12.io import file_hash, load, lock, write_json
from scripts import identity_corrective_supervisor as guard
from scripts.stop_training_at_complete_checkpoint import complete, preserve


def verify_mixture(root):
    root = Path(root).resolve()
    receipt = load(root / 'build-receipt.json')
    if (receipt['schema'] != 'dfm12-split-identity-mixture-v1'
            or receipt['recipe'] != {'DFM11': .95, 'identity-corrective': .025, 'identity-synthetic': .025}
            or receipt['stop_after_step'] != builder.END
            or receipt['steps'] != builder.END - receipt['start_step']
            or receipt['budgets'] != builder.budgets(receipt['start_step'])
            or (receipt['gas'], receipt['world_size'], receipt['global_batch']) != (8, 8, 262144)
            or not receipt['target_only'] or not receipt['heldout_and_validation_excluded']
            or receipt['packing']['available_optimizer_steps'] < receipt['steps']):
        raise ValueError('Split mixture recipe/coverage mismatch')
    for relative, sha in receipt['output_files'].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or file_hash(path) != sha:
            raise ValueError('Mixture output drift')
    for path, sha in receipt['source_receipts'].items():
        if file_hash(path) != sha:
            raise ValueError('Source receipt drift')
    return receipt


def training_config(spec):
    config = yaml.safe_load((Path(spec['source']) / 'all_config.yaml').read_text())
    if (config['ema'] != .9999 or config['reset_ema_on_resume']
            or config['global_batch_size'] != 262144
            or config['gradient_accumulation_steps'] != 8
            or config['activation_checkpointing'] != 'none'
            or config['lr'] != 1e-5 or config['arch']['bp_max_steps'] != 8):
        raise ValueError('Source no longer has the approved training geometry')
    config = copy.deepcopy(config)
    config.update(data=dict(path=spec['mixture'], target_only=True, validation_path=None),
        epochs=spec['data_epoch'] + 1, checkpoint_path=spec['output'],
        resume_checkpoint_path=str(Path(spec['state']) / 'resume'),
        resume_checkpoint_tag=spec['checkpoint_tag'], resume_epoch=None, resume_step=None,
        resume_batch_in_epoch=None, training_total_steps=builder.END, stop_after_step=builder.END,
        project_name='DFM5', wandb_run_id='dfm12-xl-identity-da-en-1000', wandb_resume='must')
    return config


def resume_view(spec):
    source, target = Path(spec['source']), Path(spec['state']) / 'resume'
    tag = spec['checkpoint_tag']
    original = load(source / f'checkpoint_state_{tag}.json')
    if original['step'] != spec['start'] or original['carry_policy'] != 'none':
        raise ValueError('Wrong stopped checkpoint or carry mode')
    if target.exists():
        raise FileExistsError(target)
    preserve(source, target, tag)
    state = dict(original, epoch=spec['data_epoch'] + 1, batch_in_epoch=0,
        batch_in_epoch_exact=True, global_row_cursor_in_epoch=0,
        global_row_start_in_epoch=0, data_path=spec['mixture'])
    write_json(target / f'checkpoint_state_{tag}.json', state)
    unchanged = []
    for path in (source / f'fsdp2_{tag}').rglob('*'):
        if path.is_file():
            if not os.path.samefile(path, target / path.relative_to(source)):
                raise ValueError('Checkpoint payload changed')
            unchanged.append(str(path.relative_to(source)))
    write_json(target / 'fresh-dataset-transition.json', dict(original=original, resume=state,
        source=str(source), unchanged_payloads=unchanged,
        weights_optimizer_ema='Unchanged full-state hard links; only isolated data cursor metadata changed'))


def prepare(state, source, mixture, old_state, output):
    state, source, mixture, old_state, output = [Path(p).resolve() for p in (state, source, mixture, old_state, output)]
    stopped = load(source / 'handoff-stopped.json')
    if not stopped['all_recorded_owned_processes_exited'] or not complete(source, stopped['tag']):
        raise ValueError('Complete stopped checkpoint required')
    for identity in [stopped['supervisor'], stopped['trainer'], *stopped['workers']]:
        if guard.same_process(identity):
            raise ValueError('Old owned process remains live')
    receipt = verify_mixture(mixture)
    if receipt['start_step'] != stopped['step'] or receipt['start_checkpoint'] != stopped['tag']:
        raise ValueError('Mixture does not start at stopped checkpoint')
    smoke = old_state / 'configs/smoke-none.completion.json'
    proof = load(smoke)
    if proof['optimizer_updates'] != 3 or proof['smoke_weights_reused']:
        raise ValueError('Require the previous clean three-step memory smoke')
    state.mkdir(parents=True, exist_ok=False)
    paths = [Path(__file__), Path(guard.__file__), Path(builder.__file__),
        ROOT / 'scripts/identity_corrective_worker.py', ROOT / 'pretrain.py',
        ROOT / 'dfm12/build_identity_adaptation.py', mixture / 'build-receipt.json',
        source / 'handoff-stopped.json', source / 'all_config.yaml',
        source / f"checkpoint_state_{stopped['tag']}.json", smoke, old_state / 'gpu-release.json']
    spec = dict(schema='identity-split-supervisor-v1', state=str(state), source=str(source),
        mixture=str(mixture), output=str(output), checkpoint_tag=stopped['tag'],
        start=stopped['step'], end=builder.END, data_epoch=receipt['data_epoch_index'],
        release_receipt=str(old_state / 'gpu-release.json'),
        allocator_fraction=.43, nvml_stop_fraction=.48, user_gpu_ceiling=.5,
        ema=.9999, reset_ema=False, export_eval_mode='EMA_ONLY',
        previous_smoke=str(smoke), smoke_reuse_reason='Same model, GAS8, 4096 context, none checkpointing and memory caps',
        pins={str(p): file_hash(p) for p in paths})
    write_json(state / 'spec.json', spec)
    return spec


def supervise(spec_path):
    spec = load(spec_path)
    state = Path(spec['state'])
    with lock(state / '.supervisor.lock'):
        guard.check_pins(spec)
        write_json(state / 'supervisor-process.json', guard.process_identity(os.getpid()))
        verify_mixture(spec['mixture'])
        resume_view(spec)
        config = training_config(spec)
        from pretrain import PretrainConfig, resolve_resume_state
        resolved = resolve_resume_state(PretrainConfig(**config), 4096)
        if ((resolved.step, resolved.start_epoch, resolved.skip_batches) != (spec['start'], spec['data_epoch']+1, 0)
                or resolved.start_row_cursor not in (0, None)):
            raise ValueError('Production resolver did not honor fresh cursor')
        write_json(state / 'resume-preflight.json', vars(resolved))
        while not guard.released(spec) or not guard.has_headroom(guard.ownership_snapshot(spec)):
            time.sleep(5)
        guard.check_pins(spec)
        if Path(spec['output']).exists():
            raise FileExistsError(spec['output'])
        configs = state / 'configs'
        configs.mkdir()
        path = configs / 'train.yaml'
        path.write_text(yaml.safe_dump(config))
        guard.run_guarded(spec, path, False)
        if not complete(Path(spec['output']), f'step_{builder.END}'):
            raise RuntimeError('Final complete checkpoint absent')
        write_json(state / 'complete.json', dict(step=builder.END, evaluation_export='EMA_ONLY'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    for name in ('state', 'source', 'mixture', 'old-state', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    sub.add_parser('supervise').add_argument('--spec', type=Path, required=True)
    args = vars(parser.parse_args())
    command = args.pop('command')
    if command == 'prepare':
        print(prepare(**args))
    else:
        def terminate(_signum, _frame):
            raise KeyboardInterrupt('Split supervisor termination requested')
        signal.signal(signal.SIGTERM, terminate)
        supervise(args['spec'])
