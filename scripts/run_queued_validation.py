"""Serial isolated qualification commands during the authorized 232K hold."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.qualify_cycle_variants import gpu_snapshot,idle,write_json

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--embla-retry',action='store_true');args=parser.parse_args()
    output=ROOT/'logs/diagnostics/queued-validation-232k-20261116'
    inventory=json.loads((output/'inventory.json').read_text())
    tasks=[]
    for name in ('embla-causal-all','embla-prefix-target','embla-loop-prefix-target'):
        config=ROOT/'logs/diagnostics/embla/candidate-configs-v5'/f'{name}.yaml'
        directory=ROOT/'logs/diagnostics/embla/full-size-v5'/name
        tasks.append((name,'scripts/smoke_embla_fsdp.py',config,directory))
        tasks.append((name+'-native','scripts/qualify_queued_training.py',config,output/(name+'-native-v5')))
    for entry in ([] if args.embla_retry else inventory):
        tasks.append((entry['name'],'scripts/qualify_queued_training.py',Path(entry['config']),output/entry['name']))
    receipts=[]
    for name,script,config,directory in tasks:
        if not idle(gpu_snapshot([str(i) for i in range(8)])):
            raise RuntimeError('GPUs occupied before '+name)
        directory.mkdir(parents=True,exist_ok=True)
        log=directory/'qualification.log'
        if log.exists():raise RuntimeError('Existing evidence; use explicit reviewed retry: '+str(log))
        command=[sys.executable,'-m','torch.distributed.run','--standalone','--nproc_per_node=8',script,'--config',str(config),'--output',str(directory)]
        print('Starting '+name,flush=True);start=time.time()
        with log.open('x') as stream:
            result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,env=os.environ.copy())
        receipts.append(dict(name=name,command=command,returncode=result.returncode,elapsed_seconds=time.time()-start,directory=str(directory)))
        write_json(output/('campaign-embla-v5.json' if args.embla_retry else 'campaign.json'),dict(tasks=receipts,complete=False))
        print(json.dumps(receipts[-1]),flush=True)
        # Driver accounting may lag worker exit briefly. This never kills peers.
        for _ in range(30):
            if idle(gpu_snapshot([str(i) for i in range(8)])):break
            time.sleep(1)
    write_json(output/('campaign-embla-v5.json' if args.embla_retry else 'campaign.json'),dict(tasks=receipts,complete=True))
if __name__=='__main__':main()
