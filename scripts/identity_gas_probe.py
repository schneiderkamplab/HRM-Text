"""Bounded GAS4 memory/speed probe, then resume the untouched full state."""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import re
import signal
import statistics
import sys
import time
from unittest.mock import patch

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import file_hash, load, lock, write_json
from dfm12.build_identity_adaptation import indices
from scripts import identity_corrective_supervisor as guard
from scripts.stop_training_at_complete_checkpoint import complete

END = 2897261


def configuration(spec, gas, mode, smoke):
    config = copy.deepcopy(yaml.safe_load((Path(spec['source']) / 'all_config.yaml').read_text()))
    if (config['ema'] != .9999 or config['reset_ema_on_resume']
            or config['global_batch_size'] != 262144 or config['lr'] != 1e-5
            or config['stop_after_step'] != END):
        raise ValueError('Unexpected source recipe')
    state = Path(spec['state'])
    config.update(gradient_accumulation_steps=gas, activation_checkpointing=mode,
        resume_checkpoint_path=spec['source'], resume_checkpoint_tag=spec['checkpoint_tag'],
        resume_epoch=None, resume_step=None, resume_batch_in_epoch=None,
        checkpoint_path=str(state / ('smoke-' + mode)) if smoke else spec['output'],
        stop_after_step=spec['start']+3 if smoke else END)
    if smoke:
        config.update(wandb_run_id=None, wandb_resume='never', log_interval=1,
            checkpoint_interval=1000000, checkpoint_step_interval=None,
            ephemeral_checkpoint_step_interval=None, resume_trace=True,
            experiment_metrics_output=str(state / ('smoke-' + mode + '.metrics.jsonl')))
    return config


def verify_probe(path):
    path = Path(path)
    config = yaml.safe_load(path.read_text())
    original = load(Path(config['resume_checkpoint_path']) / f"checkpoint_state_{config['resume_checkpoint_tag']}.json")
    steps = list(range(original['step']+1, original['step']+4))
    root = Path(config['checkpoint_path'])
    if not complete(root, f'step_{steps[-1]}'):
        raise RuntimeError('Probe checkpoint incomplete')
    final = load(root / f'checkpoint_state_step_{steps[-1]}.json')
    gas = config['gradient_accumulation_steps']
    expected = (steps[-1], original['epoch'], original['batch_in_epoch']+3*gas, gas, 262144)
    actual = tuple(final[k] for k in ('step','epoch','batch_in_epoch','gradient_accumulation_steps','global_batch_size'))
    if (actual != expected or final['local_batch_size'] != 262144 // (8*gas)
            or final['world_size'] != 8
            or final['global_row_cursor_in_epoch'] <= original['global_row_cursor_in_epoch']
            or final['data_path'] != original['data_path']):
        raise RuntimeError('Probe did not retain cursor/data or complete three updates')
    metrics = [json.loads(line) for line in Path(config['experiment_metrics_output']).read_text().splitlines()]
    if [r['step'] for r in metrics] != steps:
        raise RuntimeError('Probe metrics missing updates')
    for row in metrics:
        if (row['train/lr'] != 1e-5 or row['bp_steps'] != 8 or row['epoch'] != original['epoch']
                or row.get('train/optimizer_step_skipped', 0)
                or any(not math.isfinite(x) for x in row.values() if isinstance(x, (float, int)))):
            raise RuntimeError('Invalid probe metrics')
    log = path.with_suffix('.log').read_text()
    if 'Skipped optimizer step' in log or 'optimizer_step_skipped=True' in log or any(
            f'[resume_trace rank={rank}] optim_step_end step={step}' not in log
            for rank in range(8) for step in steps):
        raise RuntimeError('Missing all-rank optimizer traces')
    if gas != original['gradient_accumulation_steps'] and any(
            f'[resume_trace rank={rank}] set_start_row_cursor_begin row_cursor={original["global_row_cursor_in_epoch"]}' not in log
            for rank in range(8)):
        raise RuntimeError('Changed GAS did not resume the exact row cursor')
    result = dict(steps=steps, gas=gas, checkpointing=config['activation_checkpointing'],
        training_seconds=[r['training_seconds'] for r in metrics],
        third_step_seconds=metrics[-1]['training_seconds'],
        checkpoint=str(root / f'fsdp2_step_{steps[-1]}'), smoke_weights_reused=False,
        real_resume_tag=config['resume_checkpoint_tag'],
        sidecar_sha256=file_hash(root / f'checkpoint_state_step_{steps[-1]}.json'),
        metrics_sha256=file_hash(config['experiment_metrics_output']))
    write_json(path.with_suffix('.completion.json'), result)
    return result


def preflight(spec, config):
    from pretrain import PretrainConfig, resolve_resume_state
    original = load(Path(spec['source']) / f"checkpoint_state_{spec['checkpoint_tag']}.json")
    with patch('pretrain.dist.is_initialized', return_value=True), patch('pretrain.dist.get_world_size', return_value=8):
        resolved = resolve_resume_state(PretrainConfig(**config), 262144 // (8*config['gradient_accumulation_steps']))
    if resolved.step != spec['start'] or resolved.start_epoch != original['epoch']:
        raise ValueError('Incorrect checkpoint/epoch')
    if config['gradient_accumulation_steps'] != original['gradient_accumulation_steps']:
        if resolved.start_row_cursor != original['global_row_cursor_in_epoch'] or resolved.resume_mode != 'row_cursor':
            raise ValueError('GAS change requires exact row-cursor continuation')
    return vars(resolved)


def packing(spec, gas):
    from multipack_sampler import MultipackDistributedBatchSampler
    sidecar = load(Path(spec['source']) / f"checkpoint_state_{spec['checkpoint_tag']}.json")
    config = yaml.safe_load((Path(spec['source']) / 'all_config.yaml').read_text())
    arrays = indices(Path(config['data']['path']) / f"epoch_{sidecar['epoch']-1}")
    lengths = (arrays['inst_len'] + arrays['resp_len'] - 1).astype(np.int64)
    sampler = MultipackDistributedBatchSampler(262144 // (8*gas), lengths, num_replicas=8, rank=0, drop_last_batch=True)
    batches = sum(1 for _ in sampler.iter_with_info(start_index=sidecar['global_row_cursor_in_epoch']))
    result = dict(gas=gas, available_updates=batches//gas, required_updates=END-spec['start'],
        start_row=sidecar['global_row_cursor_in_epoch'])
    if result['available_updates'] < result['required_updates']:
        raise ValueError('Insufficient remaining packed updates')
    return result


def run(state, source, previous_state, output):
    state, source, previous_state, output = [Path(p).resolve() for p in (state, source, previous_state, output)]
    state.mkdir(parents=True, exist_ok=False)
    with lock(state / '.supervisor.lock'):
        stopped = load(source / 'handoff-stopped.json')
        if not stopped['all_recorded_owned_processes_exited'] or not complete(source, stopped['tag']):
            raise ValueError('Require preserved complete checkpoint and stopped owners')
        if any(guard.same_process(p) for p in [stopped['supervisor'], stopped['trainer'], *stopped['workers']]):
            raise ValueError('Old owner remains live')
        old_spec = load(previous_state / 'spec.json')
        from scripts.identity_split_supervisor import verify_mixture
        verify_mixture(old_spec['mixture'])
        paths = [Path(__file__), Path(guard.__file__), ROOT / 'scripts/identity_corrective_worker.py',
            ROOT / 'pretrain.py', source / 'all_config.yaml', source / f"checkpoint_state_{stopped['tag']}.json",
            source / 'handoff-stopped.json', Path(old_spec['release_receipt']),
            Path(old_spec['mixture']) / 'build-receipt.json']
        spec = dict(schema='identity-gas-probe-v1', state=str(state), source=str(source), output=str(output),
            checkpoint_tag=stopped['tag'], start=stopped['step'], end=END,
            release_receipt=old_spec['release_receipt'],
            allocator_fraction=.43, nvml_stop_fraction=.48, user_gpu_ceiling=.5,
            pins={str(p): file_hash(p) for p in paths})
        write_json(state / 'spec.json', spec)
        write_json(state / 'supervisor-process.json', guard.process_identity(os.getpid()))
        old_log = (previous_state / 'configs/train.log').read_text()
        speeds = [float(x) for x in re.findall(r'([0-9.]+)s/it', old_log)]
        baseline = statistics.median(speeds[-10:]) if speeds else None
        configs = state / 'configs'
        configs.mkdir()
        chosen, trials = (8, 'none'), []
        for mode in ('none', 'full'):
            guard.check_pins(spec)
            config = configuration(spec, 4, mode, True)
            path = configs / ('smoke-' + mode + '.yaml')
            path.write_text(yaml.safe_dump(config))
            try:
                write_json(path.with_suffix('.preflight.json'), preflight(spec, config))
                write_json(path.with_suffix('.packing.json'), packing(spec, 4))
                while not guard.has_headroom(guard.ownership_snapshot(spec)):
                    time.sleep(5)
                guard.run_guarded(spec, path, True, smoke_verifier=verify_probe)
                result = load(path.with_suffix('.completion.json'))
                trials.append(result)
                if baseline is None or result['third_step_seconds'] <= baseline * 1.10:
                    chosen = (4, mode)
                break
            except guard.MemoryCandidateFailure as error:
                trials.append(dict(mode=mode, memory_failure=str(error)))
                write_json(path.with_suffix('.failure.json'), trials[-1])
            except Exception as error:
                # Infrastructure/verification errors do not justify another probe geometry.
                trials.append(dict(mode=mode, probe_error=repr(error), resume_known_gas8=True))
                write_json(path.with_suffix('.failure.json'), trials[-1])
                break
        write_json(state / 'selection.json', dict(gas=chosen[0], checkpointing=chosen[1], trials=trials,
            gas8_recent_smoothed_seconds=baseline, comparison='Indicative third probe step versus recent GAS8 log; not a controlled benchmark',
            real_resume_tag=spec['checkpoint_tag'], smoke_weights_reused=False, end_step=END))
        guard.check_pins(spec)
        config = configuration(spec, *chosen, False)
        write_json(state / 'resume-preflight.json', preflight(spec, config))
        write_json(state / 'remaining-packing.json', packing(spec, chosen[0]))
        if output.exists():
            raise FileExistsError(output)
        path = configs / 'train.yaml'
        path.write_text(yaml.safe_dump(config))
        while not guard.has_headroom(guard.ownership_snapshot(spec)):
            time.sleep(5)
        guard.run_guarded(spec, path, False)
        if not complete(output, f'step_{END}'):
            raise RuntimeError('Final checkpoint missing')
        write_json(state / 'complete.json', dict(step=END, evaluation_export='EMA_ONLY'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('state', 'source', 'previous-state', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    def terminate(_signum, _frame):
        raise KeyboardInterrupt('Operator requested stop; do not automatically resume')
    signal.signal(signal.SIGTERM, terminate)
    run(**vars(parser.parse_args()))
