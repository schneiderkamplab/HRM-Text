"""Single-node controller; never discovers or signals unrelated processes."""

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from .protocol import (atomic_write, exclusive, matches, read_json, submit,
                       validate_process, process_identity)


def run(args, timeout=30):
    return subprocess.run(args, check=True, text=True, capture_output=True,
                          timeout=timeout).stdout.strip()


class CudaBackend:
    def __init__(self, executable, action_timeout=300):
        self.executable = executable
        self.action_timeout = action_timeout

    def state(self, pid):
        result = run([self.executable, '--get-state', '--pid', str(pid)]).lower().strip()
        if result not in {'running', 'locked', 'checkpointed'}:
            raise RuntimeError(f'Unsupported CUDA state for {pid}: {result!r}')
        return result

    def action(self, pid, action):
        args = [self.executable, '--action', action, '--pid', str(pid)]
        if action == 'lock':
            args += ['--timeout', '60000']
        run(args, timeout=self.action_timeout)

    def memory(self):
        output = run(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid,used_gpu_memory',
                      '--format=csv,noheader,nounits'])
        memory = {}
        for row in output.splitlines():
            pid, gpu, used = (v.strip() for v in row.split(','))
            memory[(int(pid), gpu)] = int(used)
        return memory

    def free(self):
        output = run(['nvidia-smi', '--query-gpu=uuid,memory.free',
                      '--format=csv,noheader,nounits'])
        return {gpu.strip(): int(free.strip()) for gpu, free in
                (row.split(',') for row in output.splitlines())}


class RestoreDeferred(RuntimeError):
    """A safety gate, not a failed CUDA restore; never trigger disk fallback."""


class Controller:
    def __init__(self, root, backend):
        self.root, self.backend = Path(root), backend

    def ready(self):
        launch = read_json(self.root / 'launch.json')
        ready = read_json(self.root / 'suspend_ready.json')
        if launch['job_id'] != ready['job_id'] or launch['ranks'] != ready['ranks']:
            raise RuntimeError('Readiness does not match launch')
        resumed = self.root / 'resumed.json'
        if resumed.exists() and matches(read_json(resumed), ready):
            raise RuntimeError('This suspension already resumed')
        generation = self.root / f"generation_{ready['generation']:06d}"
        for rank in ready['ranks']:
            validate_process(rank)
            ack = read_json(generation / f"ready.{rank['pid']}.json")
            if not matches(ack, ready) or any(ack.get(k) != v for k, v in rank.items()):
                raise RuntimeError('Rank readiness mismatch')
        return ready, generation

    def journal(self, directory, entry):
        with open(directory / 'operations.jsonl', 'a') as stream:
            stream.write(json.dumps(entry | {'time': time.time()}) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    def transition(self, directory, rank, action, expected):
        validate_process(rank)
        self.journal(directory, {'pid': rank['pid'], 'action': action, 'phase': 'intent'})
        try:
            self.backend.action(rank['pid'], action)
            state = self.backend.state(rank['pid'])
            if state != expected:
                raise RuntimeError(f'{action} left {rank["pid"]} in {state}')
        except Exception as error:
            def output(name):
                value = getattr(error, name, None)
                return value.decode(errors='replace') if isinstance(value, bytes) else value
            self.journal(directory, {'pid': rank['pid'], 'action': action,
                                    'phase': 'error', 'error': str(error),
                                    'stdout': output('stdout'), 'stderr': output('stderr')})
            raise
        self.journal(directory, {'pid': rank['pid'], 'action': action, 'phase': 'verified'})

    def offload(self, lease_seconds=600):
        with exclusive(self.root / 'controller.lock'):
            ready, directory = self.ready()
            if (directory / 'cancelled.json').exists() or (directory / 'restored.json').exists():
                raise RuntimeError('This generation has already been released')
            if (directory / 'offload.json').exists():
                raise RuntimeError('Offload already attempted; inspect status and use recover')
            ranks = ready['ranks']
            if any(self.backend.state(r['pid']) != 'running' for r in ranks):
                raise RuntimeError('All ranks must be running before initial offload')
            allocations = self.backend.memory()
            pids = {r['pid'] for r in ranks}
            needed = defaultdict(int)
            for (pid, gpu), amount in allocations.items():
                if pid in pids:
                    needed[gpu] += amount
            if not needed:
                raise RuntimeError('No owned GPU allocations detected')
            available = next(int(line.split()[1]) * 1024 for line in
                             Path('/proc/meminfo').read_text().splitlines()
                             if line.startswith('MemAvailable:'))
            if available < (sum(needed.values()) * 1.1 + 1024) * 1024**2:
                raise RuntimeError('Insufficient host RAM for offload plus safety margin')
            atomic_write(directory / 'offload.json', ready | {
                'needed_mib': dict(needed), 'lease_until': time.time() + lease_seconds,
                'allocations': [{'pid': pid, 'gpu': gpu, 'mib': amount}
                                for (pid, gpu), amount in allocations.items() if pid in pids],
                'existing_peers': [process_identity(pid) for pid in sorted({
                    pid for pid, gpu in allocations if pid not in pids and gpu in needed})]})
            # NVIDIA r610 IPC example requires separate lock and checkpoint passes.
            for rank in ranks:
                self.transition(directory, rank, 'lock', 'locked')
            for rank in ranks:
                self.transition(directory, rank, 'checkpoint', 'checkpointed')
            remaining = self.backend.memory()
            if any(amount > 64 for (pid, _), amount in remaining.items() if pid in pids):
                raise RuntimeError('Owned GPU memory not released; do not admit evaluations')
            atomic_write(directory / 'offloaded.json', ready | {
                'remaining_owned_mib': sum(amount for (pid, _), amount in remaining.items() if pid in pids)})

    def restore(self):
        with exclusive(self.root / 'controller.lock'):
            ready, directory = self.ready()
            managed = self.root / 'managed.json'
            supervisor_hold = (Path(read_json(managed)['supervisor_root']) / 'hold').exists() if managed.exists() else False
            if (self.root / 'hold').exists() or supervisor_hold:
                raise RestoreDeferred('Explicit user hold exists; remove it before restoration')
            if not (directory / 'offload.json').exists():
                # A below-target suspension can be released without ever
                # offloading. Never invent a CUDA restore receipt for it.
                if any(self.backend.state(r['pid']) != 'running' for r in ready['ranks']):
                    raise RuntimeError('Cannot release unoffloaded suspension: CUDA state is not running')
                atomic_write(directory / 'cancelled.json', ready)
                self.release(directory, ready)
                return
            receipt = read_json(directory / 'offload.json')
            if not matches(receipt, ready):
                raise RuntimeError('Offload receipt mismatch')
            states = {r['pid']: self.backend.state(r['pid']) for r in ready['ranks']}
            # After partial restore, only still-offloaded allocations need new space.
            if 'checkpointed' in states.values():
                free = self.backend.free()
                needed = defaultdict(int)
                for allocation in receipt.get('allocations', []):
                    if states[allocation['pid']] == 'checkpointed':
                        needed[allocation['gpu']] += allocation['mib']
                if not needed:
                    needed.update(receipt['needed_mib'])  # Older experimental receipts.
                allowed = {r['pid'] for r in ready['ranks']}
                for peer in receipt.get('existing_peers', []):
                    try:
                        validate_process(peer)
                        allowed.add(peer['pid'])
                    except (OSError, RuntimeError):
                        pass
                occupants = self.backend.memory()
                if any(pid not in allowed and gpu in receipt['needed_mib'] for pid, gpu in occupants):
                    raise RestoreDeferred('New GPU workload is still present; defer restore')
                if any(free.get(gpu, 0) < mib + 512 for gpu, mib in needed.items()):
                    raise RestoreDeferred('Not enough GPU headroom to restore safely')
            for rank in ready['ranks']:
                state = self.backend.state(rank['pid'])
                if state == 'checkpointed':
                    self.transition(directory, rank, 'restore', 'locked')
                    state = 'locked'
                if state == 'locked':
                    self.transition(directory, rank, 'unlock', 'running')
            if any(self.backend.state(r['pid']) != 'running' for r in ready['ranks']):
                raise RuntimeError('Not all ranks restored')
            atomic_write(directory / 'restored.json', ready)
            self.release(directory, ready)

    def release(self, directory, ready):
        for rank in ready['ranks']:
            token = directory / f"resume.{rank['pid']}"
            if not token.with_suffix(token.suffix + '.consumed').exists():
                atomic_write(token, {k: ready[k] for k in ('job_id', 'generation', 'step')}
                             | {'start_ticks': rank['start_ticks']})

    def cancel_unoffloaded(self):
        """Recover an abandoned ready handshake before any GPU operation began."""
        with exclusive(self.root / 'controller.lock'):
            ready, directory = self.ready()
            if (self.root / 'hold').exists() or (directory / 'offload.json').exists():
                raise RuntimeError('Cannot cancel: user hold or offload already attempted')
            if any(self.backend.state(r['pid']) != 'running' for r in ready['ranks']):
                raise RuntimeError('Cannot cancel: CUDA state is not running')
            atomic_write(directory / 'cancelled.json', ready)
            self.release(directory, ready)

    def status(self):
        result = {'launch': read_json(self.root / 'launch.json')}
        for name in ('queue', 'suspend_ready', 'resumed'):
            path = self.root / f'{name}.json'
            if path.exists():
                result[name] = read_json(path)
        return result


def bootstrap(root, command):
    """Materialize the fresh job handle so torchrun's close_fds cannot lose it."""
    source = os.environ.get('CUDA_CHECKPOINT_JOB_FILE')
    if not source:
        raise RuntimeError('bootstrap must be invoked through cuda-checkpoint --launch-job')
    directory = Path(tempfile.mkdtemp(prefix='cuda-job-', dir=root))
    destination = directory / 'job.bin'
    shutil.copyfile(source, destination)
    destination.chmod(0o600)
    os.environ['CUDA_CHECKPOINT_JOB_FILE'] = str(destination)
    os.execvp(command[0], command)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cuda-checkpoint', default='/home/ucloud/miniforge3/envs/cuda-checkpoint-test/bin/cuda-checkpoint')
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('status', 'request', 'offload', 'restore', 'recover', 'watch'):
        p = sub.add_parser(action)
        p.add_argument('control_dir', type=Path)
        if action == 'request':
            p.add_argument('steps', nargs='+', type=int)
        if action == 'offload':
            p.add_argument('--lease-seconds', type=int, default=600)
        if action == 'watch':
            p.add_argument('--interval', type=float, default=5)
            p.add_argument('--ready-timeout', type=float, default=600)
    for action in ('launch', '_bootstrap'):
        p = sub.add_parser(action)
        p.add_argument('--control-root', required=True, type=Path)
        p.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action in ('launch', '_bootstrap'):
        command = args.command[1:] if args.command[:1] == ['--'] else args.command
        if not command:
            parser.error('Missing training command')
        args.control_root.mkdir(parents=True, exist_ok=True)
        if args.action == '_bootstrap':
            bootstrap(args.control_root.resolve(), command)
        else:
            os.execv(args.cuda_checkpoint, [args.cuda_checkpoint, '--launch-job', sys.executable,
                     '-m', 'training_suspend.controller', '_bootstrap', '--control-root',
                     str(args.control_root.resolve()), '--', *command])
    controller = Controller(args.control_dir, CudaBackend(args.cuda_checkpoint))
    if args.action == 'request':
        print(submit(args.control_dir, args.steps))
    elif args.action == 'status':
        print(json.dumps(controller.status(), indent=2))
    elif args.action == 'offload':
        if args.lease_seconds <= 0:
            parser.error('lease-seconds must be positive')
        controller.offload(args.lease_seconds)
    elif args.action in ('restore', 'recover'):
        try:
            controller.restore()
        except RestoreDeferred as error:
            print(str(error), file=sys.stderr)
            sys.exit(75)
    else:
        if (controller.root / 'managed.json').exists():
            parser.error('This job has a supervisor; do not run a second recovery watcher')
        if args.interval <= 0:
            parser.error('interval must be positive')
        while True:
            try:
                ready, directory = controller.ready()
                receipt_path = directory / 'offload.json'
                if not receipt_path.exists():
                    if time.time() >= ready['ready_at'] + args.ready_timeout:
                        controller.cancel_unoffloaded()
                    time.sleep(args.interval)
                    continue
                receipt = read_json(receipt_path)
                if time.time() >= receipt['lease_until']:
                    controller.restore()
                    print('Restoration released; awaiting resumed acknowledgement', flush=True)
            except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                print(f'[suspend-watch] {error}', flush=True)
            time.sleep(args.interval)


if __name__ == '__main__':
    main()
