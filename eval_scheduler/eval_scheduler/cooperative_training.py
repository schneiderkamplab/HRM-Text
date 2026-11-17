"""Training rows lease GPUs until a verified offload, then reuse the launcher.

Only the SQLite exclusive-job path should enable this metadata. Each normal
training row remains a boundary in the DAG; the process survives those rows.
"""
import os
from pathlib import Path
import shlex
import subprocess
import time


def user_held(root, active):
    hold = root / 'hold'
    return ((hold.exists() and not hold.read_text().startswith('scheduler owns evaluation interval'))
            or (active / 'hold').exists())


def disk_handoff(settings):
    """Release only a verified, offloaded predecessor before switching models."""
    from training_suspend.protocol import atomic_write, read_json, validate_process, matches
    root = Path(settings['control_root'])
    active = Path(read_json(root / 'active.json')['control_dir'])
    ready = read_json(active / 'suspend_ready.json')
    if ready['step'] != settings['step']:
        raise RuntimeError('Disk handoff is not at the scheduled boundary')
    state = read_json(Path(ready['checkpoint']))
    if state['step'] != ready['step'] or state['checkpoint_kind'] != 'regular':
        raise RuntimeError('Disk handoff checkpoint does not match suspension')
    generation = active / f"generation_{ready['generation']:06d}"
    if not matches(read_json(generation / 'offloaded.json'), ready):
        raise RuntimeError('Disk handoff requires verified GPU offload')
    resumed = active / 'resumed.json'
    if resumed.exists() and matches(read_json(resumed), ready):
        raise RuntimeError('Cannot disk-stop a trainer that already resumed')
    atomic_write(root / 'hold', 'Scheduled model switch; resume from disk\n')
    atomic_write(root / 'stop.request', 'Scheduled model switch\n')
    identities = [read_json(root / 'launcher.json')['identity'], *ready['ranks']]
    deadline = time.monotonic() + 180
    while True:
        live = []
        for identity in identities:
            try:
                validate_process(identity)
                live.append(identity)
            except (OSError, RuntimeError):
                pass
        if not live:
            return
        if time.monotonic() > deadline:
            raise RuntimeError('Previous trainer did not stop for disk handoff')
        time.sleep(1)


def run_boundary(job, gpus):
    from training_suspend.protocol import atomic_write, exclusive, matches, read_json, process_identity, validate_process
    from training_suspend.supervisor import overrides
    from .runtime import training_checkpoint_ready, checkpoint_ready, split_command_environment
    from .ownership import spawn

    settings = job.metadata['cooperative_training']
    if settings.get('disk_handoff_from'):
        disk_handoff(settings['disk_handoff_from'])
    root = Path(settings['control_root']).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = int(job.metadata['stop_after_step'])
    backend_python = str(settings['python'])
    binary = str(settings['cuda_checkpoint'])
    final = bool(settings.get('final_boundary'))
    log_dir = Path(job.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_link = log_dir / f'train_until_step_{target}.log'
    if not log_link.exists() and not log_link.is_symlink():
        log_link.symlink_to(root / 'training.log')

    def finalize():
        command = settings.get('finalize_command')
        if command:
            subprocess.run(command, check=True)
        return 0

    def complete():
        if training_checkpoint_ready(job, target)[0]:
            return True
        tag = job.metadata.get('completion_checkpoint_tag')
        return bool(final and tag and checkpoint_ready(job.with_updates(
            metadata={**job.metadata, 'ckpt_tag': tag}))[0])

    def alive():
        path = root / 'launcher.json'
        if not path.exists():
            return False
        try:
            validate_process(read_json(path)['identity'])
            return True
        except (OSError, RuntimeError):
            return False

    with exclusive(root / 'boundary.lock'):
        if not alive():
            if complete():
                return finalize()
            # A dead launcher must not hide orphaned GPU workers.
            from training_suspend.controller import CudaBackend
            environment = os.environ.copy()
            environment['CUDA_VISIBLE_DEVICES'] = ','.join(map(str, gpus))
            query = subprocess.check_output(['nvidia-smi', '--query-gpu=index,uuid',
                                             '--format=csv,noheader'], text=True)
            mapping = dict(line.strip().split(', ') for line in query.splitlines())
            selected = {mapping[str(g)] for g in gpus}
            allowed_peers = set()
            for identity in settings.get('allowed_existing_peer_identities', []):
                try:
                    validate_process(identity)
                    allowed_peers.add(identity['pid'])
                except (OSError, RuntimeError):
                    pass
            if not settings.get('side_smoke') and any(
                    gpu in selected and pid not in allowed_peers
                    for pid, gpu in CudaBackend(binary).memory()):
                raise RuntimeError('GPU workers remain; refusing duplicate cooperative launch')
            root.joinpath('hold').unlink(missing_ok=True)
            raw = settings['command']
            env, command = split_command_environment(shlex.split(raw) if isinstance(raw, str) else raw)
            environment.update(env)
            resume = job.metadata.get('resume_from_tag')
            if resume:
                resume = str(resume)
                source = str(job.metadata.get('resume_ckpt_path') or job.metadata['ckpt_path'])
                resume_job = job.with_updates(metadata={**job.metadata, 'ckpt_path': source, 'ckpt_tag': resume})
                if not checkpoint_ready(resume_job)[0]:
                    raise RuntimeError('Incomplete cooperative launch resume checkpoint')
                command = overrides(command, {'resume_checkpoint_path': source, 'resume_checkpoint_tag': resume})
            if settings.get('scheduled_disk_resume'):
                # Explicitly prepared alternating-model schedule authorizes this
                # restart; ordinary launches must still respect a user stop.
                root.joinpath('stop.request').unlink(missing_ok=True)
            with (root / 'training.log').open('a') as log:
                process = spawn([backend_python, '-m', 'training_suspend.launcher',
                                 '--settings', settings['launcher_settings'], '--control-root', str(root),
                                 '--', *command], env=environment, cwd=job.metadata.get('workdir'),
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            atomic_write(root / 'launcher.json', {'identity': process_identity(process.pid)})
        else:
            active_path = root / 'active.json'
            if active_path.exists():
                active = Path(read_json(active_path)['control_dir'])
                ready_path = active / 'suspend_ready.json'
                if ready_path.exists():
                    ready = read_json(ready_path)
                    if ready['step'] < target and not user_held(root, active):
                        root.joinpath('hold').unlink(missing_ok=True)
                        generation = active / f"generation_{ready['generation']:06d}"
                        atomic_write(generation / 'restore.request', ready)
                        # A prior offload failure may already be waiting for disk restart.

        while True:
            if not alive():
                if complete():
                    return finalize()
                raise RuntimeError('Cooperative launcher exited without the boundary checkpoint')
            active_path = root / 'active.json'
            if active_path.exists() and not final:
                active = Path(read_json(active_path)['control_dir'])
                ready_path = active / 'suspend_ready.json'
                if ready_path.exists():
                    ready = read_json(ready_path)
                    if user_held(root, active):
                        time.sleep(2)
                        continue
                    resumed = active / 'resumed.json'
                    already = resumed.exists() and matches(read_json(resumed), ready)
                    if ready['step'] < target:
                        # Out-of-band suspension below this row's target: hand it
                        # straight back unless it has already been resumed.
                        if not already:
                            root.joinpath('hold').unlink(missing_ok=True)
                            generation = active / f"generation_{ready['generation']:06d}"
                            atomic_write(generation / 'restore.request', ready)
                    elif ready['step'] == target:
                        if already:
                            # Resumed out-of-band before the loop noticed; the
                            # regular boundary checkpoint still completes the row.
                            if complete():
                                return finalize()
                            raise RuntimeError('Stale suspension published before complete boundary checkpoint')
                        if not complete():
                            raise RuntimeError('Suspension published before complete disk checkpoint')
                        generation = active / f"generation_{ready['generation']:06d}"
                        # Scheduler now owns restoration permission. No expiry races with evals.
                        atomic_write(root / 'hold', 'scheduler owns evaluation interval\n')
                        if not (generation / 'offloaded.json').exists():
                            try:
                                result = subprocess.run([backend_python, '-m', 'training_suspend.controller',
                                    '--cuda-checkpoint', binary, 'offload', str(active),
                                    '--lease-seconds', '86400'], timeout=900)
                                failed = result.returncode != 0
                            except subprocess.TimeoutExpired:
                                failed = True
                            if failed:
                                atomic_write(generation / 'fallback.request', ready)
                                deadline = time.monotonic() + 180
                                while time.monotonic() < deadline:
                                    pending = root / 'restart_pending.json'
                                    if pending.exists() and read_json(pending)['step'] == target:
                                        return finalize()
                                    time.sleep(1)
                                raise RuntimeError('Failed offload did not release workers for disk fallback')
                        # Controller has checked memory release, not merely readiness.
                        receipt = read_json(generation / 'offloaded.json')
                        if not matches(receipt, ready):
                            raise RuntimeError('Offload generation mismatch')
                        return finalize()
            time.sleep(2)
