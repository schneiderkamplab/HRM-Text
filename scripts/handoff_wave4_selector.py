"""One bounded, exact-identity handoff at the sequential selector's idle boundary."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import psutil

from dfm12.diagnostic_server import identity,pidfd_open,pidfd_signal
from dfm12.io import file_hash,load,lock,write_json


def idle_evidence(root,pin):
    current=identity(pin['pid'])
    if any(current[k]!=pin[k] for k in ('start_ticks','session_id','cmdline')):
        raise ValueError('Selector identity changed')
    path=root/'translation-release/selection-status.json'
    if not path.exists():return None
    state=load(path);age=time.time()-state['time']
    expected={'-'.join(p) for p in load(root/'translations/config.json')['requested_pairs']}
    if set(state['pairs'])!=expected or not 0<=age<=120:return None
    if state['time']<pin['create_time']:return None
    if Path(f"/proc/{pin['pid']}/wchan").read_text().strip() not in ('hrtimer_nanosleep','do_nanosleep'):
        return None
    files=[p.path for p in psutil.Process(pin['pid']).open_files()]
    # Controller lock remains held during sleep; pair/component locks must not.
    if any(p.endswith('/.lock') or p.endswith('-journal') or '/audit-ready/' in p for p in files):
        return None
    controller=str((root/'translation-release/selection-advance.lock').resolve())
    if controller not in files:return None
    return dict(time=time.time(),status_sha256=file_hash(path),status_time=state['time'],
        completed_pairs=len(expected),open_files=files,remaining_sleep_min_seconds=480)


def run(root,pid,watch_seconds):
    pin=identity(pid)
    if pin['cmdline'][1:]!=['-u','-m','scripts.advance_wave4_selections']:
        raise ValueError('Not the expected sequential selector command')
    directory=root/'translation-release';receipt=directory/'parallel-handoff.json'
    with lock(directory/'parallel-handoff.lock'):
        if receipt.exists() and load(receipt).get('successor'):
            raise ValueError('Handoff already recorded; no duplicate launch')
        successor_path=Path('scripts/advance_wave4_selections_parallel.py')
        successor_sha=file_hash(successor_path)
        deadline=time.monotonic()+watch_seconds
        write_json(receipt,dict(phase='watching_idle',old=pin,workers=2,
            watch_seconds=watch_seconds,successor_implementation_sha256=successor_sha))
        while time.monotonic()<deadline:
            proof=idle_evidence(root,pin)
            print(dict(time=time.time(),pid=pid,idle=proof is not None),flush=True)
            if proof:
                if file_hash(successor_path)!=successor_sha:raise ValueError('Successor changed while watching')
                fd=pidfd_open(pid)
                try:
                    proof=idle_evidence(root,pin)
                    if not proof:continue
                    write_json(receipt,dict(phase='verified_idle',old=pin,proof=proof,workers=2))
                    pidfd_signal(fd,signal.SIGTERM)
                finally:os.close(fd)
                end=time.monotonic()+30
                while True:
                    try:
                        if psutil.Process(pid).status()==psutil.STATUS_ZOMBIE:break
                    except psutil.NoSuchProcess:break
                    if time.monotonic()>end:raise TimeoutError('Old selector did not exit; no escalation')
                    time.sleep(.2)
                with lock(directory/'selection-advance.lock'):pass
                command=[sys.executable,'-u','-m','scripts.advance_wave4_selections_parallel',
                    '--root',str(root),'--workers','2']
                log=Path('logs/dfm13/wave4')/f'advance-selections-parallel2-{int(time.time())}.log'
                with log.open('xb') as output:
                    child=subprocess.Popen(command,stdout=output,stderr=subprocess.STDOUT,
                        start_new_session=True,env={**os.environ,'CUDA_VISIBLE_DEVICES':''})
                successor=identity(child.pid)
                write_json(receipt,dict(phase='launched',old=pin,proof=proof,successor=successor,
                    command=command,log=str(log),workers=2,successor_implementation_sha256=successor_sha))
                print('LAUNCHED',child.pid,str(log),flush=True)
                return
            time.sleep(10)
        write_json(receipt,dict(phase='no_idle_within_watch',old=pin,workers=2,
            watch_seconds=watch_seconds,signaled=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('data/dfm13/wave4'))
    parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--watch-seconds',type=float,default=900)
    args=parser.parse_args()
    run(args.root,args.pid,args.watch_seconds)
