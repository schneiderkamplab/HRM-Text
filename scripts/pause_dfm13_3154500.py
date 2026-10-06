"""User-authorized checkpoint-safe pause only; never resumes training."""
import os
from pathlib import Path
import signal
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dfm12.io import write_json
from dfm12.diagnostic_server import identity,pidfd_open,pidfd_signal
from scripts.stop_training_at_complete_checkpoint import complete,preserve,alive

def main():
    work=ROOT/'logs/dfm13/pause-3154500-20261006'
    work.mkdir(parents=True,exist_ok=True)
    source=ROOT/'checkpoints/dfm13/XL-from-dfm12-step3150000'
    target=ROOT/'checkpoints/preserved/dfm13-pause-3154500'
    tag='ephemeral_step_3154500';pid=2095661
    command=Path(f'/proc/{pid}/cmdline').read_bytes()
    if b'torchrun' not in command or b'data=dfm13' not in command or b'stop_after_step=3200000' not in command:
        raise RuntimeError('Unexpected training identity')
    owner=identity(pid);fd=pidfd_open(pid)
    stop=ROOT/'logs/scheduler/dfm12_XL_epoch11_noidentity/stop.request'
    marker=stop.read_bytes()
    write_json(work/'armed.json',dict(owner=owner,watcher_pid=os.getpid(),tag=tag,preserve_dir=str(target),no_auto_resume=True))
    print('Armed for complete '+tag,flush=True)
    try:
        while not complete(source,tag):
            if not alive(pid) or identity(pid)['start_ticks']!=owner['start_ticks']:raise RuntimeError('Training exited/changed')
            time.sleep(1)
        preserve(source,target,tag)
        if stop.read_bytes()!=marker or identity(pid)['start_ticks']!=owner['start_ticks'] or Path(f'/proc/{pid}/cmdline').read_bytes()!=command:
            raise RuntimeError('Ownership changed before stop')
        pidfd_signal(fd,signal.SIGTERM)
        write_json(work/'signaled.json',dict(owner=owner,tag=tag,preserved=str(target),time=time.time()))
        print('Checkpoint preserved; exact torchrun signaled',flush=True)
        deadline=time.monotonic()+180
        while alive(pid):
            if time.monotonic()>deadline:raise RuntimeError('Torchrun did not exit')
            time.sleep(1)
        write_json(work/'stopped.json',dict(tag=tag,step=3154500,resume_checkpoint_path=str(target),
            resume_checkpoint_tag=tag,checkpoint_complete=complete(target,tag),no_auto_resume=True,time=time.time()))
        print('Stopped; no resume',flush=True)
    finally:os.close(fd)

if __name__=='__main__':main()
