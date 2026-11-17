"""Metadata-only epoch length; no token payload IO."""
import sys,time,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from multipack_sampler import MultipackDistributedBatchSampler

def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--gas',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
 root=ROOT/'data/sampled_dfm11/epoch_0';inst=np.load(root/'inst_len.npy',mmap_mode='r');resp=np.load(root/'resp_len.npy',mmap_mode='r');lengths=np.empty(len(inst),dtype=np.int64)
 for start in range(0,len(inst),1_000_000):
  end=min(start+1_000_000,len(inst));lengths[start:end]=inst[start:end].astype(np.int64)+resp[start:end]-1
 sampler=MultipackDistributedBatchSampler(262144//8//a.gas,lengths,num_replicas=8,rank=0,drop_last_batch=True)
 start=time.monotonic();count=sum(1 for _ in sampler.iter_with_info())
 result=dict(microbatches=count,gradient_accumulation_steps=a.gas,complete_optimizer_steps=count//a.gas,partial_microbatches=count%a.gas,seconds=time.monotonic()-start,source='actual DFM11 epoch0 Multipack lengths replay')
 a.output.write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':main()
