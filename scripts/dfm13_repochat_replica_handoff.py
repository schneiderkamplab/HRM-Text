"""Launch ready replicas' client and publish terminal only after exact child exit."""
import fcntl
from pathlib import Path
import subprocess
import time

from scripts import dfm13_repochat_candidate_recovery as c

WORK = Path('logs/dfm13/repo-bulk-interlude-2981000')


def main():
    with (c.ROOT / 'replica-handoff.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ready = c.b.load(WORK / 'servers-ready.json')
        terminal = Path(ready['completion_receipt'])
        if terminal.exists():
            raise ValueError('terminal receipt already exists; refuse relaunch')
        command = ['/home/ucloud/miniforge3/envs/hrm/bin/python', '-m',
                   'scripts.dfm13_repochat_replica_recovery', '--endpoints',
                   ','.join(ready['endpoints']), '--model', ready['model'],
                   '--per-endpoint', '256', '--parent-gpus-cleared']
        with (c.ROOT / 'replica-runner.log').open('a') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
        identity = dict(pid=child.pid, start_ticks=Path(f'/proc/{child.pid}/stat').read_text().split()[21],
                        command=command, time=time.time(), readiness=c.r.pin(WORK / 'servers-ready.json'))
        c.b.save(c.ROOT / 'replica-launcher.json', identity)
        print(identity, flush=True)
        code = child.wait()
        path = c.ROOT / 'gpu-work-terminal.json'
        receipt = c.b.load(path) if path.exists() else None
        valid = receipt and receipt.get('pid') == child.pid and receipt.get('start_ticks') == identity['start_ticks']
        complete = code == 0 and valid and receipt['status'] == 'complete'
        c.b.save(terminal, dict(status='complete' if complete else 'failed',
            all_gpu_stages_terminal=True, gpu_clients_stopped=True, time=time.time(),
            child=identity, exit_code=code, campaign_receipt=c.r.pin(path) if valid else None,
            admission=False, no_further_gpu_work=True,
            scope='686 pinned finalization/audit recoveries; bounded timeout retries; no semantic repair loop'))


if __name__ == '__main__':
    main()
