"""Serial context probes with per-process deadlines and preserved failure receipts."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--gpu',type=int,required=True);p.add_argument('--timeout',type=int,default=40);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    results=[]
    for name in ('embla-prefix-target','embla-loop-prefix-target'):
        for length in (4096,16384,32768,65536,131072,262144):
            output=args.output/f'{name}-{length}.json'
            command=[sys.executable,str(ROOT/'scripts/benchmark_embla_context.py'),str(ROOT/'logs/diagnostics/embla/candidate-configs-v2'/f'{name}.yaml'),'--length',str(length),'--output',str(output)]
            begin=time.monotonic()
            with output.with_suffix('.log').open('w') as log:
                try:
                    run=subprocess.run(command,env={**os.environ,'CUDA_VISIBLE_DEVICES':str(args.gpu),'OMP_NUM_THREADS':'4'},stdout=log,stderr=subprocess.STDOUT,timeout=args.timeout)
                    result=json.loads(output.read_text()) if output.exists() else {'passed':False,'error':'process_failure','returncode':run.returncode}
                except subprocess.TimeoutExpired:
                    result={'passed':False,'error':'deadline','deadline_seconds':args.timeout}
            result.update(model=name,length=length,wall_seconds=time.monotonic()-begin)
            output.write_text(json.dumps(result,indent=2));results.append(result)
            (args.output/'summary.json').write_text(json.dumps(results,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':main()
