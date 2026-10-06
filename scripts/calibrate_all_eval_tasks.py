"""Replay every prepared eval task against isolated persistent servers; never sync scores."""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import statistics

from scripts.calibrate_xl_eval_capacity import CUDA, ROOT, server_command, cleanup, probe as raw_probe
from dfm12.io import load, write_json


async def probe(session, url):
    import aiohttp
    for attempt in range(3):
        try:
            return await raw_probe(session, url)
        except (aiohttp.ServerDisconnectedError, aiohttp.ClientOSError):
            if attempt == 2: raise


def candidates(task, capacity):
    rows = task['rows']
    lengths = sorted(r['prompt_tokens'] for r in rows)
    prompt = lengths[min(len(lengths)-1, int(len(lengths)*.9))]
    outputs = [r.get('historical_output_tokens') or r['payload'].get('max_tokens', 128)/2 for r in rows]
    live = max(1, prompt + statistics.median(outputs))
    upper = min(1024, max(16, 2 ** math.floor(math.log2(max(1, capacity*.65/live)))))
    return sorted({min(32, upper), max(8, upper//2), upper})


async def stage(session, url, task, count, seconds, path, judge_url=None):
    initial = await probe(session, url)
    start = time.monotonic()
    deadline = start + seconds
    samples, results = [], []
    stop = asyncio.Event()
    done = asyncio.Event()
    index = 0

    async def monitor():
        while not done.is_set():
            m = await probe(session, url)
            m['elapsed'] = time.monotonic()-start
            samples.append(m)
            if m['kv'] >= .90 or m['preemptions'] > initial['preemptions']:
                stop.set()
            await asyncio.sleep(.5)

    async def request(endpoint, payload):
        import aiohttp
        for attempt in range(3):
            try:
                async with session.post(endpoint, json=payload, timeout=240) as response:
                    body = await response.text()
                    if response.status != 200:
                        raise RuntimeError(f'{response.status}: {body[:700]}')
                    return json.loads(body)
            except (aiohttp.ServerDisconnectedError, aiohttp.ClientOSError):
                if attempt == 2: raise

    async def worker():
        nonlocal index
        while time.monotonic() < deadline and not stop.is_set():
            i = index
            index += 1
            row = task['rows'][i % len(task['rows'])]
            payload = copy.deepcopy(row['payload'])
            payload['model'] = 'xl-capacity'
            payload['stream'] = False
            t = time.monotonic()
            result = {'row': i % len(task['rows'])}
            try:
                body = await request(url+row.get('endpoint', '/v1/chat/completions'), payload)
                result['usage'] = body.get('usage', {})
                if judge_url:
                    judge = copy.deepcopy(row['judge_payload'])
                    judge['model'] = 'gemma-4-e4b-judge'
                    judge['stream'] = False
                    await request(judge_url+'/chat/completions', judge)
            except Exception as exc:
                result['error'] = repr(exc)
                stop.set()
            result['seconds'] = time.monotonic()-t
            results.append(result)

    watcher = asyncio.create_task(monitor())
    try:
        await asyncio.wait_for(asyncio.gather(*(worker() for _ in range(count))), seconds+260)
    finally:
        done.set()
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)
    elapsed = time.monotonic()-start
    last = await probe(session, url)
    steady = [x for x in samples if 2 <= x['elapsed'] <= seconds and x['running'] > 0]
    summary = dict(concurrency=count, requests=len(results), seconds=elapsed,
        errors=sum('error' in r for r in results),
        preemptions=last['preemptions']-initial['preemptions'],
        kv_peak=max([initial['kv']]+[s['kv'] for s in samples]),
        kv_steady=statistics.median(s['kv'] for s in steady) if steady else 0,
        requests_per_second=len(results)/elapsed,
        output_tokens_per_second=sum(r.get('usage',{}).get('completion_tokens',0) for r in results)/elapsed)
    summary['safe'] = not summary['errors'] and summary['preemptions']==0 and summary['kv_peak']<.90
    write_json(path, dict(summary=summary, requests=results, samples=samples))
    return summary


async def run(args):
    import aiohttp
    sys.path.insert(0,str(ROOT/'eval_scheduler'))
    from eval_scheduler.model import read_plan
    from eval_scheduler.runtime import start_managed_judge, terminate
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    processes, judges = [], []
    results = {}
    if (root/'owned-processes.json').exists():
        raise RuntimeError('Use a new runtime directory; never overwrite process ownership')
    active = subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True)
    if active.strip(): raise RuntimeError('GPUs occupied; refusing to disturb their owners')
    try:
        for gpu in range(8):
            command = server_command(gpu, args.port_base+gpu, .85 if gpu==7 else .95, 1024)
            command += ['--enable-auto-tool-choice','--tool-call-parser','gemma4']
            env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu), OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
                       WANDB_MODE='disabled',TOKENIZERS_PARALLELISM='false',VLLM_USE_FLASHINFER_SAMPLER='0',
                       FLASHINFER_DISABLE_VERSION_CHECK='1',CUDA_HOME=str(CUDA),CUDA_PATH=str(CUDA))
            env['PATH']=str(CUDA/'bin')+':'+str(Path(sys.executable).parent)+':'+env.get('PATH','')
            env['LD_LIBRARY_PATH']=str(CUDA/'lib')+':'+str(CUDA/'lib64')+':'+env.get('LD_LIBRARY_PATH','')
            cache=ROOT/'data/dfm13/xl3100-eval-capacity-20261005-v3'/f'gpu{gpu}'
            for key,sub in [('VLLM_CACHE_ROOT','vllm'),('TORCHINDUCTOR_CACHE_DIR','inductor'),
                            ('TRITON_CACHE_DIR','triton'),('CUDA_CACHE_PATH','cuda')]:
                env[key]=str(cache/sub)
            with (root/f'gpu{gpu}.server.log').open('w') as handle:
                proc=subprocess.Popen(command,env=env,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
            processes.append(proc)
            write_json(root/'owned-processes.json',[dict(pid=p.pid,gpu=i) for i,p in enumerate(processes)])
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=8400, keepalive_timeout=1)) as session:
            async def ready(gpu):
                url=f'http://127.0.0.1:{args.port_base+gpu}'
                deadline=time.monotonic()+1200
                while time.monotonic()<deadline:
                    if processes[gpu].poll() is not None: raise RuntimeError(f'GPU{gpu} startup failed')
                    try:
                        async with session.get(url+'/health',timeout=2) as response:
                            if response.status==200:return url
                    except (aiohttp.ClientError,asyncio.TimeoutError):pass
                    await asyncio.sleep(2)
                raise TimeoutError(f'GPU{gpu} startup deadline')
            urls=await asyncio.gather(*(ready(g) for g in range(8)))
            print('All servers ready; waiting for prepared task manifest',flush=True)
            while not args.manifest.exists():await asyncio.sleep(2)
            manifest=load(args.manifest)
            tasks=manifest['tasks']
            if args.reuse:
                previous=load(args.reuse)['results']
                for task in tasks:
                    if len(task.get('members',[task['key']]))==1 and previous.get(task['key'],{}).get('status')=='complete':
                        results[task['key']]={**previous[task['key']], 'reused_from':str(args.reuse)}
            if manifest.get('missing'):raise RuntimeError(f"Unprepared tasks: {manifest['missing']}")
            ordinary=asyncio.Queue()
            judged=[]
            for task in tasks:
                if task['key'] in results:continue
                if task.get('utilization',.95)<.9:judged.append(task)
                else:ordinary.put_nowait(task)
            plan_jobs=read_plan(args.plan/'plan.tsv')

            async def worker(gpu):
                url=urls[gpu]
                log=(root/f'gpu{gpu}.server.log').read_text()
                match=re.search(r'GPU KV cache size: ([\d,]+) tokens',log)
                if not match:raise RuntimeError('KV capacity missing from server log')
                capacity=int(match.group(1).replace(',',''))
                pending_judged=list(judged) if gpu==7 else []
                while pending_judged or not ordinary.empty():
                    if pending_judged:task=pending_judged.pop(0)
                    else:
                        try:task=ordinary.get_nowait()
                        except asyncio.QueueEmpty:break
                    key=task['key'];folder=root/'tasks'/key.replace(':','__');folder.mkdir(parents=True,exist_ok=True)
                    judge=None;judge_url=None
                    try:
                        if task.get('utilization',.95)<.9:
                            job=next(j for j in plan_jobs if str(j.action)==task['action'] and j.name==task['name'])
                            judge,judge_url,_=await asyncio.to_thread(start_managed_judge,job,gpu,folder)
                            if judge:judges.append(judge)
                            if not all(r.get('judge_payload') for r in task['rows']):
                                raise RuntimeError('Missing judge request evidence')
                        levels=candidates(task,capacity)
                        if judge:levels=[8,16,32]
                        stages=[]
                        print('TASK',gpu,key,'levels',levels,flush=True)
                        for count in levels:
                            s=await stage(session,url,task,count,args.seconds,folder/f'c{count}.json',judge_url)
                            stages.append(s)
                            print('STAGE',gpu,key,count,s,flush=True)
                            if not s['safe']:break
                        safe=[s for s in stages if s['safe'] and s['requests']]
                        if not safe:raise RuntimeError('No successful capacity level')
                        best=max(safe,key=lambda s:s['requests_per_second'])
                        results[key]=dict(best=best,stages=stages,gpu=gpu,capacity=capacity,
                                          utilization=.85 if gpu==7 else .95,status='complete')
                    except Exception as exc:
                        results[key]=dict(status='failed',error=repr(exc),gpu=gpu)
                        print('FAILED',key,repr(exc),flush=True)
                    finally:
                        if judge:terminate(judge)
                    write_json(folder/'result.json',results[key])
                    write_json(root/'progress.json',dict(done=len(results),total=len(tasks),results=results))
                return
            await asyncio.gather(*(worker(g) for g in range(8)))
            write_json(root/'report.json',dict(tasks=results,total=len(tasks),
                failed=[k for k,v in results.items() if v['status']!='complete'],wandb=False))
    finally:
        for judge in judges:
            if judge.poll() is None:terminate(judge)
        cleanup(processes)
        write_json(root/'cleanup.json',dict(pids=[p.pid for p in processes],exit_codes=[p.poll() for p in processes]))


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--plan',type=Path,default=ROOT/'logs/scheduler/dfm12_XL_epoch11_noidentity')
    parser.add_argument('--seconds',type=int,default=10)
    parser.add_argument('--port-base',type=int,default=59200)
    parser.add_argument('--reuse',type=Path)
    args=parser.parse_args()
    loop=asyncio.new_event_loop();asyncio.set_event_loop(loop)
    task=loop.create_task(run(args))
    for sig in (signal.SIGTERM,signal.SIGINT):loop.add_signal_handler(sig,task.cancel)
    try:loop.run_until_complete(task)
    finally:
        pending=asyncio.all_tasks(loop)
        for child in pending:child.cancel()
        loop.run_until_complete(asyncio.gather(*pending,return_exceptions=True))
        loop.close()

if __name__=='__main__':main()
