"""Preserve the next full checkpoint before stopping only the recorded owner."""
import argparse
import os
from pathlib import Path
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import load, lock, write_json
from scripts.identity_corrective_supervisor import (
    descendant_of, process_identity, same_process,
)
from scripts.stop_training_at_complete_checkpoint import complete, preserve


def stop_at_checkpoint(state, destination, step):
    state, destination = Path(state).resolve(), Path(destination).resolve()
    with lock(state / '.mixture-handoff.lock'):
        supervisor = load(state / 'supervisor-process.json')
        trainer = load(state / 'configs/train.process.json')['identity']
        spec = load(state / 'spec.json')
        source, tag = Path(spec['output']), f'ephemeral_step_{step}'
        if not same_process(supervisor) or not same_process(trainer):
            raise RuntimeError('Recorded supervisor/trainer no longer live')
        write_json(state / 'mixture-handoff-watcher.json', dict(
            identity=process_identity(os.getpid()), step=step, source=str(source),
            destination=str(destination), supervisor=supervisor, trainer=trainer))
        while not complete(source, tag):
            if not same_process(supervisor) or not same_process(trainer):
                raise RuntimeError('Owner exited before complete checkpoint')
            time.sleep(1)
        preserve(source, destination, tag)
        if not complete(destination, tag):
            raise RuntimeError('Preserved checkpoint incomplete')
        workers = []
        for p in Path('/proc').iterdir():
            if p.name.isdigit() and descendant_of(int(p.name), trainer['pid']):
                try:
                    workers.append(process_identity(int(p.name)))
                except (FileNotFoundError, ProcessLookupError):
                    pass
        if not same_process(supervisor) or not same_process(trainer):
            raise RuntimeError('Owner changed before signal')
        # Its registered handler stops its verified torchrun and rank sessions.
        os.kill(supervisor['pid'], signal.SIGTERM)
        deadline = time.monotonic() + 120
        while any(same_process(p) for p in [supervisor, trainer, *workers]):
            if time.monotonic() > deadline:
                raise RuntimeError('Owned processes have not exited; no restart allowed')
            time.sleep(1)
        write_json(destination / 'handoff-stopped.json', dict(
            step=step, tag=tag, source=str(source), preserved=str(destination),
            supervisor=supervisor, trainer=trainer, workers=workers,
            complete_checkpoint=True, all_recorded_owned_processes_exited=True,
            final_end_step=2897261, remaining_updates=2897261-step,
            foreign_processes_signalled=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--step', type=int, required=True)
    stop_at_checkpoint(**vars(parser.parse_args()))
