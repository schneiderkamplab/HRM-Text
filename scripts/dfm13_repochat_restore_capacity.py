"""One-shot exact-client graceful restart at the existing three-case allocation."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import urllib.request

from scripts import dfm13_repochat_candidate_recovery as c


def main():
    root = c.ROOT
    import fcntl
    with (root / 'capacity-transition.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        old = c.b.load(root / 'launcher.json')
        proc = Path('/proc') / str(old['pid'])
        def alive():
            if not proc.exists():
                return False
            fields = (proc / 'stat').read_text().split()
            return fields[21] == old['start_ticks'] and fields[2] != 'Z'
        receipt = dict(old=old, target_concurrency=3, started=time.time(), status='draining', admission=False)
        c.b.save(root / 'capacity-transition.json', receipt)
        if alive():
            if 'scripts.dfm13_repochat_candidate_recovery' not in (proc / 'cmdline').read_text():
                raise ValueError('owned client command mismatch')
            os.kill(old['pid'], signal.SIGTERM)
        deadline = time.monotonic() + 1500
        while alive():
            if time.monotonic() > deadline:
                raise TimeoutError('old client did not drain; no second client launched')
            time.sleep(2)
        c.prepare(root)  # Verify all pinned inputs before restart.
        deadline = time.monotonic() + 300
        while True:
            metrics = urllib.request.urlopen('http://127.0.0.1:8810/metrics', timeout=10).read().decode()
            if c.r.metric_admission(metrics, .70):
                break
            if time.monotonic() > deadline:
                raise TimeoutError('headroom unavailable; no launch')
            time.sleep(5)
        with (root / 'runner.log').open('a') as log:
            process = subprocess.Popen(['/home/ucloud/miniforge3/envs/hrm/bin/python', '-m',
                'scripts.dfm13_repochat_candidate_recovery', '--concurrency', '3'],
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        receipt.update(status='launched', pid=process.pid,
                       start_ticks=(Path('/proc') / str(process.pid) / 'stat').read_text().split()[21],
                       launched=time.time())
        c.b.save(root / 'capacity-transition.json', receipt)
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
