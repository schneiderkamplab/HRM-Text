"""Bounded XXS/64-token parity smoke using only explicitly selected GPUs."""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from .controller import Controller, CudaBackend
from .protocol import atomic_write, read_json


def make_data(root, full_size=False):
    import numpy as np
    root.mkdir(parents=True)
    epoch = root / 'epoch_0'
    epoch.mkdir()
    rows, length, vocab = (1024, 4097, 262144) if full_size else (256, 65, 256)
    prefix = (length - 1) // 4
    rng = np.random.default_rng(42)
    np.save(root / 'tokens.npy', rng.integers(1, vocab, rows * length, dtype=np.uint32))
    for name, array in {
        'inst_start': np.arange(rows) * length, 'inst_len': np.full(rows, prefix),
        'resp_start': np.arange(rows) * length + prefix, 'resp_len': np.full(rows, length - prefix),
    }.items():
        np.save(epoch / f'{name}.npy', array.astype(np.int64))
    atomic_write(root / 'metadata.json', {'max_seq_len': length, 'total_length': rows * (length - 1),
                 'tokenizer_info': {'vocab_size': vocab}})


def assert_state_equal(a, b):
    import torch
    if isinstance(a, torch.Tensor):
        torch.testing.assert_close(a, b, rtol=0, atol=0)
    elif isinstance(a, dict):
        assert a.keys() == b.keys()
        for key in a:
            assert_state_equal(a[key], b[key])
    elif isinstance(a, (tuple, list)):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            assert_state_equal(x, y)
    else:
        assert a == b, (a, b)


def compare(root):
    import torch
    summaries = read_json(root / 'progress.json')
    baseline = torch.load(root / 'baseline/checkpoints/unsharded_step_6.pt', weights_only=False, map_location='cpu')
    candidate = torch.load(root / 'suspended/checkpoints/unsharded_step_6.pt', weights_only=False, map_location='cpu')
    for key in ('model', 'optim'):
        assert_state_equal(baseline[key], candidate[key])
    assert_state_equal(summaries['baseline']['benchmark']['metric_history'],
                       summaries['suspended']['benchmark']['metric_history'])
    summaries['parity'] = 'exact model, optimizer/EMA and per-step metrics match'
    atomic_write(root / 'result.json', summaries)
    return summaries['parity']


def wait_offloaded(proc, backend, controller, seconds, deadline, resume_request=None):
    """Check continued CPU liveness and released GPU memory during long pauses."""
    ready, generation = controller.ready()
    pids = {rank['pid'] for rank in ready['ranks']}
    end = time.monotonic() + seconds
    while True:
        if proc.poll() is not None:
            raise RuntimeError('Worker launcher exited during offloaded pause')
        if resume_request is not None and resume_request.exists():
            controller.journal(generation, {'phase': 'early_resume_requested',
                               'request': str(resume_request)})
            return
        controller.ready()  # Revalidate every worker's process identity.
        states = {pid: backend.state(pid) for pid in pids}
        memory = sum(mib for (pid, _), mib in backend.memory().items() if pid in pids)
        if set(states.values()) != {'checkpointed'} or memory > 64 * len(pids):
            raise RuntimeError(f'Offloaded state changed: {states}, {memory} MiB')
        remaining = max(0, end - time.monotonic())
        controller.journal(generation, {'phase': 'pause_health', 'states': states,
                           'owned_gpu_mib': memory, 'remaining_seconds': remaining})
        print(f'pause: {remaining:.0f}s remaining, {len(pids)} ranks checkpointed, {memory} MiB GPU memory', flush=True)
        if not remaining:
            return
        if time.monotonic() >= deadline:
            raise TimeoutError('Smoke deadline exceeded during offloaded pause')
        time.sleep(min(30, remaining, max(0, deadline - time.monotonic())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--gpus', required=True, help='Explicit physical GPU indices, e.g. 1 or 1,2')
    parser.add_argument('--compile', action='store_true')
    parser.add_argument('--embla-kernels', action='store_true', help='Enable validated fused Embla attention candidates')
    parser.add_argument('--embla', action='store_true', help='Bounded four-loop Embla PrefixLM architecture smoke')
    parser.add_argument('--ouro', action='store_true', help='Bounded fixed-loop Ouro architecture smoke')
    parser.add_argument('--sandwich', action='store_true', help='Bounded single-state sandwich architecture smoke')
    parser.add_argument('--cycle-budget', type=int, choices=[15,16], help='Test full-budget cycle sampling on the small baseline')
    parser.add_argument('--full-size', action='store_true',
                        help='Dedicated eight-GPU XXL-wide/4K/262144-vocab BP8 GAS4 test')
    parser.add_argument('--nccl-shim', action='store_true',
                        help='Experimental preloaded NCCL checkpoint shim; requires external Redis rendezvous')
    parser.add_argument('--legacy-nccl', action='store_true',
                        help='Test-only: disable cuMem device/host allocations and NVLS')
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--pause-seconds', type=float, default=2,
                        help='Host-only wait in each of the two offload cycles')
    args = parser.parse_args()
    if args.embla_kernels and not args.embla:
        parser.error('--embla-kernels requires --embla')
    if args.pause_seconds < 0 or args.timeout <= 0:
        parser.error('pause-seconds must be nonnegative and timeout positive')
    if args.nccl_shim and args.legacy_nccl:
        parser.error('Test the shim independently from legacy-nccl')
    if args.nccl_shim:
        from .nccl_shim import NcclCheckpointShim
        NcclCheckpointShim()  # Fail before starting workers if launch configuration is missing.
    gpu_ids = [int(g) for g in args.gpus.split(',')]
    if not gpu_ids or len(set(gpu_ids)) != len(gpu_ids):
        parser.error('GPU IDs must be unique')
    if args.full_size and len(gpu_ids) != 8:
        parser.error('Full-size profile requires eight GPUs')
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    make_data(root / 'data', args.full_size)
    backend = CudaBackend('/home/ucloud/miniforge3/envs/cuda-checkpoint-test/bin/cuda-checkpoint',
                          action_timeout=300 if args.full_size else 60)
    repo = Path(__file__).resolve().parents[1]
    summaries = {}
    for mode in ('baseline', 'suspended'):
        # Recheck before each allocation. No production process is signalled.
        output = subprocess.check_output(['nvidia-smi', '--query-gpu=index,memory.free',
                                          '--format=csv,noheader,nounits'], text=True)
        free = {int(a): int(b) for a, b in (line.split(',') for line in output.splitlines())}
        required_free = 178000 if args.full_size else 8192
        if any(free[g] < required_free for g in gpu_ids):
            raise RuntimeError(f'Require at least {required_free} MiB free on each selected GPU')
        directory = root / mode
        directory.mkdir()
        checkpoints = directory / 'checkpoints'
        checkpoints.mkdir()
        command = [sys.executable, '-m', 'torch.distributed.run', '--standalone',
                   f'--nproc_per_node={len(gpu_ids)}', str(repo / 'pretrain.py'),
                   'arch/size@arch=XXS', f'data.path={root / "data"}', 'epochs=1',
                   f'global_batch_size={128 * len(gpu_ids)}', 'gradient_accumulation_steps=2',
                   'distributed_strategy=fsdp', 'fsdp_reshard_after_forward=false',
                   'fsdp_accumulation_sync_mode=no_sync', 'max_steps=6', 'training_total_steps=6',
                   'checkpoint_step_interval=2', 'checkpoint_format=unsharded',
                   f'checkpoint_path={checkpoints}', 'log_interval=1', 'lr=1e-4', 'lr_warmup_steps=0',
                   'arch.bp_warmup_ratio=0', 'arch.bp_max_steps=5',
                   'benchmark_state_fingerprint=true', 'memory_log_interval=1',
                   f'compile_train_batch={str(args.compile).lower()}', 'run_name=suspend-smoke',
                   f'hydra.run.dir={directory}', 'dataloader_prefetch_factor=1']
        if args.embla:
            if args.full_size or args.cycle_budget or args.ouro or args.sandwich or args.compile:
                raise ValueError('Embla smoke uses its dedicated eager small profile')
            command = [x for x in command if not x.startswith('arch.bp_')]
            command += ['arch/net@arch=embla', 'arch.decoder_loops=4', '+arch.attn_type=prefixlm',
                        'lr_auto=false', 'fsdp_wrap_policy=single_unit']
            fields = dict(hidden_size=128, head_dim=16, num_attention_heads=8, num_key_value_heads=2,
                          sliding_num_attention_heads=8, sliding_num_key_value_heads=2,
                          intermediate_size=128, num_experts=4, num_experts_per_tok=2,
                          moe_intermediate_size=64, shared_expert_intermediate_size=64,
                          engram_pages=4, engram_head_dim=64, engram_heads=4, engram_page_heads=4,
                          sparse_topk=8, sparse_recent=4)
            if args.embla_kernels:
                fields.update(head_dim=64,num_attention_heads=2,num_key_value_heads=1,sliding_num_attention_heads=2,sliding_num_key_value_heads=1)
                command += ['++arch.embla_fa4_window=true','++arch.embla_fused_relu=true','++arch.embla_fused_sparse=true','++arch.embla_single_topk=true']
            command += [f'++arch.embla_config.{key}={value}' for key,value in fields.items()]
        if args.sandwich:
            if args.full_size or args.cycle_budget or args.ouro:
                raise ValueError('Sandwich smoke cannot combine other architecture profiles')
            command = [x for x in command if not x.startswith('arch.bp_')]
            command += ['arch/net@arch=sandwich', 'arch.n_layers=4',
                        'arch.prelude_layers=1', 'arch.core_layers=2', 'arch.coda_layers=1',
                        'arch.recurrence=3', 'arch.hidden_size=128', 'arch.num_heads=1',
                        'lr_auto=false', 'fsdp_wrap_policy=single_unit']
        if args.ouro:
            if args.full_size or args.cycle_budget:
                raise ValueError('Ouro smoke cannot combine other architecture profiles')
            command = [x for x in command if not x.startswith('arch.bp_')]
            command += ['arch/net@arch=ouro', 'arch.n_layers=2', 'arch.recurrence=4',
                        'arch.hidden_size=128', 'arch.num_heads=1',
                        'lr_auto=false', 'fsdp_wrap_policy=single_unit']
        if args.cycle_budget:
            if args.full_size:
                raise ValueError('Cycle smoke uses the bounded small model; use the separate full-recipe qualifier')
            command += ['arch.cycle_variants=full_budget', f'arch.bp_max_steps={args.cycle_budget}',
                        'arch.n_layers=2', 'arch.hidden_size=128', 'arch.num_heads=1']
        if args.full_size:
            overrides = {'arch/size@arch': 'XXL_wide', 'global_batch_size': '262144',
                         'gradient_accumulation_steps': '4', 'arch.bp_max_steps': '8',
                         'lr': '3e-4'}
            command = [arg.split('=', 1)[0] + '=' + overrides[arg.split('=', 1)[0]]
                       if '=' in arg and arg.split('=', 1)[0] in overrides else arg
                       for arg in command]
        if mode == 'suspended':
            command += [f'suspend_control_dir={directory / "control"}',
                        'suspend_after_steps=[2,4]', 'suspend_poll_interval_steps=1',
                        'suspend_wait_poll_seconds=0.1']
            command = [sys.executable, '-m', 'training_suspend.controller', 'launch',
                       '--control-root', str(directory / 'control'), '--', *command]
        env = os.environ | {'CUDA_VISIBLE_DEVICES': args.gpus, 'OMP_NUM_THREADS': '1',
                            'MKL_NUM_THREADS': '1', 'WANDB_MODE': 'disabled',
                            'WANDB_DISABLED': 'true', 'BENCH_OUTPUT': str(directory / 'benchmark.json')}
        if args.legacy_nccl:
            env.update(NCCL_CUMEM_ENABLE='0', NCCL_CUMEM_HOST_ENABLE='0', NCCL_NVLS_ENABLE='0')
        env['SUSPEND_TEST_NCCL_SHIM'] = '1' if args.nccl_shim else '0'
        atomic_write(directory / 'launch.json', {'command': command, 'gpus': gpu_ids,
                     'compile': args.compile, 'legacy_nccl': args.legacy_nccl,
                     'nccl_shim': args.nccl_shim, 'ld_preload': env.get('LD_PRELOAD'),
                     'full_size': args.full_size, 'cycle_budget': args.cycle_budget, 'sandwich': args.sandwich, 'ouro': args.ouro, 'embla': args.embla,
                     'pause_seconds': args.pause_seconds,
                     'nccl_environment': {k: v for k, v in env.items() if k.startswith('NCCL_') or k.startswith('TORCH_NCCL_')},
                     'allocator_fraction': None})
        begin = time.monotonic()
        phases = []
        with open(directory / 'train.log', 'w') as log:
            proc = subprocess.Popen(command, env=env, cwd=repo, stdout=log,
                                    stderr=subprocess.STDOUT, start_new_session=True)
            try:
                released = set()
                while proc.poll() is None:
                    if time.monotonic() - begin > args.timeout:
                        raise TimeoutError('Smoke deadline exceeded')
                    for path in directory.glob('control/*/suspend_ready.json'):
                        ready = read_json(path)
                        key = (ready['job_id'], ready['generation'])
                        if key in released:
                            continue
                        controller = Controller(path.parent, backend)
                        start = time.monotonic()
                        try:
                            controller.offload(lease_seconds=max(120, args.pause_seconds + 120))
                            offloaded = time.monotonic()
                            atomic_write(directory / 'pause.json', {'generation': key[1],
                                         'offloaded_at': time.time(),
                                         'restore_after': time.time() + args.pause_seconds})
                            print(f'{mode}: generation {key[1]} offloaded; waiting {args.pause_seconds}s', flush=True)
                            wait_offloaded(proc, backend, controller, args.pause_seconds,
                                           begin + args.timeout, root / 'finish_early.request')
                            restore_started = time.monotonic()
                            controller.restore()
                        except Exception:
                            # Best effort recovery affects only the manifest's smoke PIDs.
                            try:
                                controller.restore()
                            except Exception:
                                pass
                            raise
                        phases.append({'generation': key[1], 'offload_seconds': offloaded - start,
                                       'pause_seconds': restore_started - offloaded,
                                       'restore_seconds': time.monotonic() - restore_started})
                        released.add(key)
                    time.sleep(.1)
                if proc.returncode:
                    raise RuntimeError(f'{mode} failed with {proc.returncode}; inspect {directory / "train.log"}')
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait(timeout=10)
        summaries[mode] = {'elapsed_seconds': time.monotonic() - begin, 'phases': phases,
                           'benchmark': read_json(directory / 'benchmark.json')}
        atomic_write(root / 'progress.json', summaries)
    print(json.dumps({'result': str(root / 'result.json'), 'parity': compare(root)}))


if __name__ == '__main__':
    main()
