"""Read-only GPU/server/client sampling; does not attach to or stop workers."""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import time
import urllib.request


def metrics(port):
    text=urllib.request.urlopen(f'http://127.0.0.1:{port}/metrics',timeout=5).read().decode()
    result={}
    for line in text.splitlines():
        if not line or line.startswith('#'): continue
        key=line.split('{')[0].split()[0]
        if key.startswith('vllm:') and not key.endswith(('_bucket','_created')):
            result[key]=result.get(key,0)+float(line.rsplit(' ',1)[1])
    return result


def processes():
    result={}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode()
            if not any(x in cmd for x in ('dfm14.audit','dfm14.production_parallel','VLLM::EngineCore')):continue
            stat=(p/'stat').read_text().rsplit(')',1)[1].split()
            result[p.name]=dict(cpu_ticks=int(stat[11])+int(stat[12]),cmd=cmd,wchan=(p/'wchan').read_text())
        except (OSError,ValueError):pass
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=int,default=60)
    parser.add_argument('--interval',type=int,default=2)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); args.output.parent.mkdir(parents=True,exist_ok=True)
    snapshots=[]; start=time.monotonic()
    with args.output.open('x') as out:
        while True:
            gpu=subprocess.check_output(['nvidia-smi','--query-gpu=index,utilization.gpu,power.draw','--format=csv,noheader,nounits'],text=True)
            r=dict(time=time.time(),gpus=[dict(gpu=int(a),util=float(b),watts=float(c)) for a,b,c in (s.split(',') for s in gpu.splitlines())],
                   servers={str(i):metrics(8800+i) for i in range(8)},processes=processes())
            snapshots.append(r);out.write(json.dumps(r)+'\n');out.flush()
            if time.monotonic()-start>=args.seconds:break
            time.sleep(args.interval)
    elapsed=snapshots[-1]['time']-snapshots[0]['time'];summary={}
    for i in range(8):
        values=[s['servers'][str(i)] for s in snapshots]
        delta=lambda k:values[-1].get('vllm:'+k,0)-values[0].get('vllm:'+k,0)
        count=delta('e2e_request_latency_seconds_count')
        summary[i]=dict(mean_gpu=round(statistics.mean(s['gpus'][i]['util'] for s in snapshots),1),
            mean_watts=round(statistics.mean(s['gpus'][i]['watts'] for s in snapshots)),
            mean_running=round(statistics.mean(v.get('vllm:num_requests_running',0) for v in values)),
            mean_queued=round(statistics.mean(v.get('vllm:num_requests_waiting',0) for v in values)),
            max_kv=round(100*max(v.get('vllm:kv_cache_usage_perc',0) for v in values),1),
            generated_tokens_sec=round(delta('generation_tokens_total')/elapsed),
            mean_request_sec=round(delta('e2e_request_latency_seconds_sum')/max(count,1),2),
            mean_queue_sec=round(delta('request_queue_time_seconds_sum')/max(count,1),2),
            preemptions=delta('num_preemptions_total'))
    print(json.dumps(summary,indent=2))
    for pid,p in snapshots[-1]['processes'].items():
        first=snapshots[0]['processes'].get(pid)
        if first:
            cpu=100*(p['cpu_ticks']-first['cpu_ticks'])/os.sysconf('SC_CLK_TCK')/elapsed
            print(pid,round(cpu,1),p['wchan'],p['cmd'][:100])


if __name__=='__main__':main()
