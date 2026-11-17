"""Resume the Transformer PrefixLM355K trainer after >5 continuous minutes of all-GPU idle."""
import argparse,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from training_suspend.protocol import read_json,atomic_write,exclusive,matches,validate_process,submit
from training_suspend.controller import Controller,CudaBackend
CONTROL=ROOT/'logs/training/transformer48_dfm11_prefixlm_targetonly_20261114/control'
OUT=CONTROL/'idle-resume-355000'
HOLD='Explicit user pause at355000; resume from memory only on user command\n'
def probe():
    result=subprocess.run(['nvidia-smi','--query-gpu=index,utilization.gpu,memory.used','--format=csv,noheader,nounits'],check=True,capture_output=True,text=True,timeout=15)
    rows={int(i):{'utilization':int(u),'memory_mib':int(m)} for i,u,m in (line.split(',') for line in result.stdout.splitlines())}
    apps=subprocess.run(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],check=True,capture_output=True,text=True,timeout=15).stdout.strip()
    idle=set(rows)==set(range(8)) and all(r['utilization']==0 and r['memory_mib']<=128 for r in rows.values()) and not apps
    return idle,rows,apps

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--probe',action='store_true');args=parser.parse_args()
    if args.probe:print(json.dumps(probe()));return
    OUT.mkdir(exist_ok=True)
    with exclusive(OUT/'watcher.lock'):
        active=Path(read_json(CONTROL/'active.json')['control_dir'])
        submit(active,[355000])
        atomic_write(OUT/'status.json',{'stage':'armed','target_step':355000,'time':time.time()})
        # Do not hold the preceding350K evaluation/resume handoff.
        while True:
            if (OUT/'cancel.request').exists():
                atomic_write(OUT/'status.json',{'stage':'cancelled','time':time.time()});return
            assert read_json(CONTROL/'active.json')['control_dir']==str(active),'Trainer changed'
            ready=read_json(active/'suspend_ready.json')
            if ready['step']==355000 and not matches(read_json(active/'resumed.json'),ready):break
            assert ready['step']<355000,'Missed requested suspension'
            time.sleep(2)
        assert not (active/'hold').exists(),'Respect existing active hold'
        with (CONTROL/'hold').open('x') as f:f.write(HOLD)
        controller=Controller(active,CudaBackend('/home/ucloud/miniforge3/envs/cuda-checkpoint-test/bin/cuda-checkpoint'))
        controller.offload(lease_seconds=3600)
        atomic_write(CONTROL/'user-pause-355000.json',{'ready':ready})
        launcher=read_json(CONTROL/'launcher.json')['identity']
        generation=active/f"generation_{ready['generation']:06d}"
        assert ready['step']==355000 and matches(read_json(generation/'offloaded.json'),ready)
        since=None
        while True:
            if (OUT/'cancel.request').exists():
                atomic_write(OUT/'status.json',{'stage':'cancelled','time':time.time()});return
            validate_process(launcher)
            assert read_json(CONTROL/'active.json')['control_dir']==str(active),'Trainer changed'
            assert (CONTROL/'hold').read_text()==HOLD,'Hold changed; do not override'
            error=None
            try:idle,rows,apps=probe()
            except (ValueError,subprocess.SubprocessError,OSError) as e:
                idle=False;rows={};apps='';error=str(e)
            now=time.monotonic()
            since=(now if since is None else since) if idle else None
            seconds=now-since if since is not None else 0
            atomic_write(OUT/'status.json',{'stage':'watching','idle_seconds':seconds,'required_seconds':300,'gpus':rows,'compute_pids':apps,'error':error,'time':time.time()})
            if seconds>300:
                # Recheck immediately before yielding the GPUs to the trainer.
                if not probe()[0]:since=None;continue
                for rank in ready['ranks']:validate_process(rank)
                assert (CONTROL/'hold').read_text()==HOLD
                assert matches(read_json(active/'suspend_ready.json'),ready)
                assert matches(read_json(generation/'offloaded.json'),ready)
                (CONTROL/'hold').unlink()
                atomic_write(generation/'restore.request',ready)
                atomic_write(OUT/'status.json',{'stage':'restore_requested','idle_seconds':seconds,'time':time.time()})
                deadline=time.monotonic()+1200
                while time.monotonic()<deadline:
                    p=active/'resumed.json'
                    if p.exists() and matches(read_json(p),ready):
                        validate_process(launcher)
                        for rank in ready['ranks']:validate_process(rank)
                        assert not (generation/'disk_fallback.json').exists()
                        atomic_write(OUT/'status.json',{'stage':'resumed_from_memory','step':355000,'launcher':launcher,'time':time.time()})
                        return
                    time.sleep(2)
                raise TimeoutError('No memory-resume acknowledgement; inspect supervisor')
            time.sleep(10)
if __name__=='__main__':main()
