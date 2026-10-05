"""Wait for current calibration clients, then retry only unfinished examples once."""
import concurrent.futures
from pathlib import Path
import subprocess
import sys

import psutil

from dfm12.io import lock


def retry(pid, arguments, log):
    try:
        process=psutil.Process(pid)
        if 'dfm12.baltic_calibration' not in process.cmdline():
            raise ValueError('PID no longer belongs to expected calibration')
        process.wait()
    except psutil.NoSuchProcess:
        pass
    with open(log,'ab') as out:
        result=subprocess.run([sys.executable,'-u','-m','dfm12.baltic_calibration',
            *arguments,'--simple-json','--unbounded-schema'],stdout=out,stderr=subprocess.STDOUT)
    print(pid,'retry exit',result.returncode,flush=True)
    result.check_returncode()


def main():
    with lock(Path('logs/dfm13/wave4/calibration-retries.lock')):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(retry,2054808,
                ['--root','data/dfm13/baltic/calibration-review-schema','--per-group','10'],
                'logs/dfm13/baltic-calibration-review-schema.log'),
                pool.submit(retry,2057023,
                ['--wave4','--root','data/dfm13/wave4/calibration/results-run','--per-group','2',
                 '--requests','data/dfm13/wave4/calibration/generation-requests.jsonl'],
                'logs/dfm13/wave4/calibration.log')]
            for future in futures:
                future.result()


if __name__=='__main__':
    main()
