"""Bounded CPU-only successor preparation after the transition owner freezes."""
import argparse
import os
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dfm12.io import load,write_json,file_hash,lock
from dfm12.wave4_gemma31_fresh import prepare,verify,adapter,DOWNLOAD

DIRECTORY=Path('data/dfm13/wave4')
FREEZE=DIRECTORY/'transition-frozen-v2.json'
STATUS=DIRECTORY/'fresh42-successor-status-v2.json'
PAIRS=[('wave4',DIRECTORY/'gemma31-fresh-comparison30-v4',DIRECTORY/'gemma31-fresh-comparison30-v5'),
       ('baltic',Path('data/dfm13/baltic/gemma31-fresh-comparison12-v2'),Path('data/dfm13/baltic/gemma31-fresh-comparison12-v3'))]


def frozen():
    receipt=load(FREEZE)
    path=Path('dfm12/wave4_gemma31_transition.py').resolve()
    if receipt.get('frozen') is not True or Path(receipt['path']).resolve()!=path or receipt['sha256']!=file_hash(path):
        raise ValueError('Owner freeze receipt does not match current transition')
    return file_hash(FREEZE)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wait-seconds',type=int,default=0);a=p.parse_args()
    if not 0<=a.wait_seconds<=1800:raise ValueError('Wait bound0..1800')
    with lock(DIRECTORY/'fresh42-successor.lock'):
        end=time.monotonic()+a.wait_seconds
        while not FREEZE.exists():
            write_json(STATUS,dict(pid=os.getpid(),phase='waiting_owner_freeze',deadline_seconds=a.wait_seconds,
                production_approved=False,server_actions=False))
            if time.monotonic()>=end:
                write_json(STATUS,dict(pid=None,phase='blocked_owner_freeze_timeout',server_actions=False))
                return
            time.sleep(5)
        seal=frozen();ready=load(DOWNLOAD/'ready.json');reports=[]
        for wave,old,new in PAIRS:
            write_json(STATUS,dict(pid=os.getpid(),phase='preparing_cpu',wave=wave,server_actions=False))
            if new.exists():raise ValueError('New root already exists; inspect, never overwrite/repin')
            prepare(new,wave)
            for name in ('specifications.json','generation-requests.json'):
                if load(old/name)!=load(new/name):raise ValueError('Original42 prompts changed: '+name)
            c=adapter(new);r,g=c.v6.adapters();b=c.v6.Budget(ready['snapshot']);budgets=[]
            for s in load(new/'specifications.json'):
                payload,schema=c.v6.compact_request(c.v6.generation_request(s,g))
                budgets.append(b.measure(payload))
            verify(new)
            report=dict(root=str(new),total=len(budgets),max_prompt_plus_reserve=max(v['total_tokens'] for v in budgets),
                original_prompts_equal=True,weights_receipt_sha256=file_hash(DOWNLOAD/'ready.json'),
                transition_freeze_sha256=seal,no_gpu_requests=True)
            write_json(new/'cpu-preflight.json',report);reports.append(report)
        if frozen()!=seal:raise ValueError('Freeze changed during CPU preparation')
        from dfm12.wave31_production import verify as production_verify
        production={}
        for wave in ('wave4','baltic'):
            root=Path('data/dfm13')/wave/'synthetic31-full-staged-v2'
            try:production[str(root)]=dict(target=production_verify(root)['target'],verified=True)
            except Exception as exc:production[str(root)]=dict(verified=False,error_type=type(exc).__name__)
        write_json(STATUS,dict(pid=None,previous_pid=os.getpid(),phase='ready',roots=reports,
            production=production,server_actions=False,production_approved=False))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        write_json(STATUS,dict(pid=None,phase='failed_cpu_preparation',error=repr(exc),server_actions=False))
        raise
