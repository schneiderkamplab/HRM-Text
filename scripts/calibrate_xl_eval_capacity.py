"""Bounded real-prompt eval capacity replay. CPU prepare; explicit execute required."""
import argparse
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import signal
import socket
import statistics
import subprocess
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dfm12.io import file_hash,load,write_json,lock

MODEL=ROOT/'exports/dfm12_XL_epoch11_step_3100000_ema_hf'
TEMPLATE=ROOT/'evaluation/chat_templates/gemma4_native_chat.jinja'
DFM=ROOT/'logs/dfm_evals/dfm12_XL_epoch11/step_3100000'
STANDARD=ROOT/'logs/eval/dfm12_XL_epoch11/step_3100000/standard_shards'
FAMILIES=('standard','dfm_short','summaries','ifeval')
CUDA=Path('/home/ucloud/miniforge3/envs/hrm-cu132')
STANDARD_CONFIG=ROOT/'evaluation/config/dfm6_vllm_benchmarking.yaml'


def resolve(value,attachments):
    if isinstance(value,str) and value.startswith('attachment://'):
        return attachments[value.removeprefix('attachment://')]
    if isinstance(value,list):return [resolve(x,attachments) for x in value]
    if isinstance(value,dict):return {k:resolve(v,attachments) for k,v in value.items()}
    return value


def inspect_rows(paths):
    for path in sorted(paths):
        with zipfile.ZipFile(path) as archive:
            for name in sorted(n for n in archive.namelist() if n.startswith('samples/') and n.endswith('.json')):
                row=json.loads(archive.read(name))
                events=[e for e in row.get('events',[]) if e.get('event')=='model']
                if not events:continue
                event=resolve(events[0],row.get('attachments',{}))
                if event.get('tools'):continue
                messages=[{k:v for k,v in m.items() if k in ('role','content','name','tool_calls','tool_call_id')}
                          for m in event['input']]
                config=event.get('config',{})
                yield dict(id=str(row['id']),source=str(path),member=name,messages=messages,
                           max_tokens=int(config.get('max_tokens',512)),temperature=config.get('temperature',0))


def source_rows(family):
    if family=='standard':
        import yaml
        config=yaml.safe_load(STANDARD_CONFIG.read_text())
        tasks={b['name']:{**config['generation_config'],**b.get('generation_config',{})} for b in config['benchmarks']}
        def task_rows(task):
            settings=tasks[task]
            for path in sorted((STANDARD/task).rglob('*.generations.jsonl')):
                with path.open() as handle:
                    for number,line in enumerate(handle):
                        row=json.loads(line)
                        prompt=row['prompt']
                        if not isinstance(prompt,str):continue
                        yield dict(id=f'{task}-{row.get("index",number)}',source=str(path),line=number,
                                   messages=[dict(role='user',content=prompt)],max_tokens=settings['max_tokens'],
                                   temperature=settings['temperature'])
        iterators=[iter(task_rows(task)) for task in ('GSM8k','ARC','MATH','HellaSwag','DROP')]
        while iterators:
            for iterator in iterators.copy():
                try:yield next(iterator)
                except StopIteration:iterators.remove(iterator)
    else:
        names={'dfm_short':['dala','gec_dala','generative_talemaader'],
               'summaries':['nordjyllandnews','govreport'],
               'ifeval':[f'ifeval_shard_{i}' for i in range(32)]}[family]
        # Round-robin tasks/shards so a family does not silently become one task.
        iterators=[iter(inspect_rows((DFM/name).rglob('*.eval'))) for name in names]
        while iterators:
            for iterator in iterators.copy():
                try:yield next(iterator)
                except StopIteration:iterators.remove(iterator)


def prepare(root,per_family=128):
    from transformers import AutoTokenizer
    root.mkdir(parents=True,exist_ok=False)
    if load(MODEL/'tokenizer_config.json').get('fix_mistral_regex') is not False:
        raise ValueError('Export tokenizer must explicitly disable Mistral regex fix')
    tokenizer=AutoTokenizer.from_pretrained(MODEL,local_files_only=True,fix_mistral_regex=False)
    rows=[];excluded=Counter();sources={}
    for family in FAMILIES:
        count=0
        for row in source_rows(family):
            rendered=tokenizer.apply_chat_template(row['messages'],chat_template=TEMPLATE.read_text(),
                    tokenize=False,add_generation_prompt=True,enable_thinking=False)
            ids=tokenizer.encode(rendered,add_special_tokens=False)
            if len(ids)+row['max_tokens']>4096:
                excluded[family+':context_overflow']+=1
                continue
            row.update(family=family,prompt_tokens=len(ids))
            rows.append(row);count+=1
            sources.setdefault(row['source'],None)
            if count==per_family:break
        if count<16:raise ValueError(f'Insufficient real prompts: {family}={count}')
    for path in sources:sources[path]=file_hash(path)
    write_json(root/'prompts.json',rows)
    pins={str(p):file_hash(p) for p in [Path(__file__).resolve(),TEMPLATE,STANDARD_CONFIG,MODEL/'config.json',
           MODEL/'tokenizer.json',MODEL/'tokenizer_config.json']}
    pins[str((root/'prompts.json').resolve())]=file_hash(root/'prompts.json')
    write_json(root/'prepared.json',dict(model=str(MODEL),source_checkpoint=3100000,pins=pins,
        sources=sources,counts=dict(Counter(r['family'] for r in rows)),excluded=dict(excluded),
        truncation=False,ignore_eos=False,wandb=False,judge_process_launched=False,
        matrix=[dict(gpu=g,family=FAMILIES[g%4],utilization=.95 if g<4 else .85) for g in range(8)]))


def server_command(gpu,port,utilization,max_seqs):
    return [sys.executable,'-m','vllm.entrypoints.openai.api_server','--model',str(MODEL),
            '--served-model-name','xl-capacity','--host','127.0.0.1','--port',str(port),
            '--dtype','bfloat16','--attention-backend','FLASH_ATTN','--max-model-len','4096',
            '--gpu-memory-utilization',str(utilization),'--max-num-seqs',str(max_seqs),
            '--max-cudagraph-capture-size','512',
            '--max-num-batched-tokens','16384','--chat-template',str(TEMPLATE),'--seed','0']


def metrics(text):
    from prometheus_client.parser import text_string_to_metric_families
    names={'vllm:kv_cache_usage_perc':'kv','vllm:gpu_cache_usage_perc':'kv',
           'vllm:num_preemptions_total':'preemptions','vllm:num_requests_running':'running',
           'vllm:num_requests_waiting':'waiting','vllm:generation_tokens_total':'output_tokens',
           'vllm:prompt_tokens_total':'input_tokens'}
    result={}
    for family in text_string_to_metric_families(text):
        for sample in family.samples:
            if sample.name in names:
                key=names[sample.name];result[key]=result.get(key,0)+sample.value
    return result


def safe_next(result):
    return not result['errors'] and result['preemptions']==0 and result['kv_peak']<.90


async def probe(session,endpoint):
    async with session.get(endpoint+'/metrics',timeout=5) as response:
        response.raise_for_status();return metrics(await response.text())


async def stage(session,endpoint,rows,concurrency,seconds,path):
    initial=await probe(session,endpoint)
    if not {'kv','preemptions','running','waiting'}<=initial.keys():
        raise ValueError('Required KV/preemption/queue metrics unavailable')
    started=time.monotonic();deadline=started+seconds;index=0;results=[];samples=[]
    stop=asyncio.Event();finished=asyncio.Event()
    async def monitor():
        while not finished.is_set():
            snapshot=await probe(session,endpoint)
            snapshot['elapsed']=time.monotonic()-started;samples.append(snapshot)
            if snapshot['kv']>=.90 or snapshot['preemptions']>initial['preemptions']:stop.set()
            await asyncio.sleep(1)
    async def worker():
        nonlocal index
        while time.monotonic()<deadline and not stop.is_set():
            number=index;index+=1;row=rows[number%len(rows)]
            payload=dict(model='xl-capacity',messages=row['messages'],max_tokens=row['max_tokens'],
                         temperature=row['temperature'],chat_template_kwargs={'enable_thinking':False})
            tick=time.monotonic();result=dict(number=number,id=row['id'],source=row['source'])
            try:
                async with session.post(endpoint+'/v1/chat/completions',json=payload,timeout=300) as response:
                    body=await response.text();result.update(http_status=response.status,body=body)
                    response.raise_for_status();parsed=json.loads(body)
                    result['usage']=parsed['usage'];result['finish_reason']=parsed['choices'][0]['finish_reason']
            except Exception as exc:
                result['error']=repr(exc);stop.set()
            result['elapsed']=time.monotonic()-tick
            results.append(result)
    watcher=asyncio.create_task(monitor())
    try:
        await asyncio.wait_for(asyncio.gather(*(worker() for _ in range(concurrency))),seconds+310)
    finally:
        finished.set()
        await watcher
    elapsed=time.monotonic()-started;last=await probe(session,endpoint)
    latencies=sorted(r['elapsed'] for r in results)
    steady=[s for s in samples if 5<=s['elapsed']<=seconds and s['running']>0]
    result=dict(concurrency=concurrency,requests=len(results),elapsed=elapsed,
        errors=sum('error' in r for r in results),output_tokens=sum(r.get('usage',{}).get('completion_tokens',0) for r in results),
        kv_peak=max([initial['kv']]+[r['kv'] for r in samples]),
        kv_median=statistics.median([r['kv'] for r in samples]) if samples else initial['kv'],
        kv_steady_median=statistics.median([s['kv'] for s in steady]) if steady else None,
        kv_steady_fraction_above_half=sum(s['kv']>.5 for s in steady)/len(steady) if steady else None,
        steady_samples=len(steady),
        preemptions=last['preemptions']-initial['preemptions'],
        latency_p50=statistics.median(latencies) if latencies else None,
        latency_p95=latencies[min(len(latencies)-1,int(len(latencies)*.95))] if latencies else None,
        stop_reasons=dict(Counter(r.get('finish_reason','error') for r in results)),samples=samples)
    result['output_tokens_per_second']=result['output_tokens']/elapsed
    result['requests_per_second']=len(results)/elapsed
    result['steady_output_tokens_per_second']=((steady[-1]['output_tokens']-steady[0]['output_tokens'])/
        (steady[-1]['elapsed']-steady[0]['elapsed'])) if len(steady)>1 and 'output_tokens' in steady[0] else None
    write_json(path,dict(summary=result,requests=results))
    return result


def free_gpus():
    raw=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.total,memory.free',
                                 '--format=csv,noheader,nounits'],text=True)
    rows=[tuple(map(int,line.split(','))) for line in raw.strip().splitlines()]
    if len(rows)!=8 or {r[0] for r in rows}!=set(range(8)):
        raise RuntimeError('Require all8 GPUs')
    for gpu,total,free in rows:
        if free<total*(.95 if gpu<4 else .85)+512:
            raise RuntimeError(f'GPU{gpu} occupied: {free}/{total}MiB; never stopping unrelated owners')
    active=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).strip()
    if active:raise RuntimeError('Compute processes remain; await owner release, no launch')
    return rows


def cleanup(processes):
    for proc in processes:
        try:
            os.killpg(proc.pid,signal.SIGTERM)
        except ProcessLookupError:pass
    for proc in processes:
        try:proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=10)


async def execute(args):
    import aiohttp
    prepared=load(args.root/'prepared.json')
    for path,sha in prepared['pins'].items():
        if file_hash(path)!=sha:raise ValueError('Prepared implementation/input changed: '+path)
    write_json(args.root/'gpu-before.json',free_gpus())
    if not (CUDA/'bin/nvcc').exists():raise FileNotFoundError('Verified hrm-cu132 CUDA compiler unavailable')
    rows=load(args.root/'prompts.json');processes=[];ports=[];report={}
    try:
        for entry in prepared['matrix']:
            gpu=entry['gpu'];port=args.port_base+gpu
            with socket.socket() as sock:sock.bind(('127.0.0.1',port))
            command=server_command(gpu,port,entry['utilization'],max(args.levels))
            env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
                     WANDB_MODE='disabled',TOKENIZERS_PARALLELISM='false',VLLM_USE_FLASHINFER_SAMPLER='0',
                     FLASHINFER_DISABLE_VERSION_CHECK='1')
            env['PATH']=str(Path(sys.executable).parent)+':'+env.get('PATH','')
            env['CUDA_HOME']=env['CUDA_PATH']=str(CUDA)
            env['PATH']=str(CUDA/'bin')+':'+env['PATH']
            env['LD_LIBRARY_PATH']=str(CUDA/'lib')+':'+str(CUDA/'lib64')+':'+env.get('LD_LIBRARY_PATH','')
            for key,dirname in [('VLLM_CACHE_ROOT','vllm'),('TORCHINDUCTOR_CACHE_DIR','inductor'),
                                ('TRITON_CACHE_DIR','triton'),('CUDA_CACHE_PATH','cuda')]:
                env[key]=str((args.root/f'gpu{gpu}'/dirname).resolve());Path(env[key]).mkdir(parents=True,exist_ok=True)
            with (args.root/f'gpu{gpu}.server.log').open('w') as log:
                proc=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            processes.append(proc);ports.append(port)
            write_json(args.root/'owned-processes.json',[dict(pid=p.pid,gpu=i,port=ports[i]) for i,p in enumerate(processes)])
            write_json(args.root/f'gpu{gpu}.launch.json',dict(command=command,pid=proc.pid,entry=entry))
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=8*max(args.levels)+16)) as session:
            async def endpoint(entry,proc,port):
                gpu=entry['gpu'];url=f'http://127.0.0.1:{port}';deadline=time.monotonic()+args.startup_timeout
                while True:
                    if proc.poll() is not None:raise RuntimeError(f'GPU{gpu} server exited {proc.returncode}')
                    if time.monotonic()>deadline:raise TimeoutError(f'GPU{gpu} startup timed out')
                    try:
                        async with session.get(url+'/health',timeout=2) as response:
                            if response.status==200:break
                    except (aiohttp.ClientError,asyncio.TimeoutError):pass
                    await asyncio.sleep(2)
                print('READY',gpu,entry,flush=True)
                selected=[r for r in rows if r['family']==entry['family']]
                await stage(session,url,selected,4,3,args.root/f'gpu{gpu}.warmup.json')
                summaries=[]
                for level in args.levels:
                    outcome=await stage(session,url,selected,level,args.seconds,args.root/f'gpu{gpu}.c{level}.json')
                    summaries.append(outcome)
                    print('STAGE',gpu,level,'kv',outcome['kv_peak'],'preemptions',outcome['preemptions'],
                          'tokens/s',outcome['output_tokens_per_second'],flush=True)
                    if not safe_next(outcome):break
                safe=[s for s in summaries if safe_next(s)]
                report[str(gpu)]=dict(**entry,stages=summaries,
                    recommendation=max(safe,key=lambda s:s['output_tokens_per_second'])['concurrency'] if safe else None,
                    kv_target_reached=any((s['kv_steady_median'] or 0)>.5 for s in safe))
                write_json(args.root/f'gpu{gpu}.summary.json',report[str(gpu)])
            async with asyncio.timeout(args.runtime_timeout):
                async with asyncio.TaskGroup() as tasks:
                    for entry,proc,port in zip(prepared['matrix'],processes,ports):
                        tasks.create_task(endpoint(entry,proc,port))
        write_json(args.root/'report.json',dict(status='complete',gpus=report,wandb=False,
            judged_note='.85 reserves capacity only; no concurrent judge process measured',
            judged_concurrency_16_unchanged=True,
            real_prompt_replay=True,quality_evaluation=False,policy_changed=False))
    except BaseException as exc:
        write_json(args.root/'failure.json',dict(error=repr(exc),completed=report))
        raise
    finally:
        cleanup(processes)
        write_json(args.root/'cleanup.json',dict(pids=[p.pid for p in processes],
            exit_codes=[p.poll() for p in processes],owned_processes_only=True,time=time.time()))


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('mode',choices=['prepare','run']);parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--levels',type=int,nargs='+',default=[32,64,128,256,512])
    parser.add_argument('--seconds',type=int,default=30);parser.add_argument('--startup-timeout',type=int,default=900)
    parser.add_argument('--runtime-timeout',type=int,default=1200);parser.add_argument('--port-base',type=int,default=59100)
    args=parser.parse_args()
    if sorted(set(args.levels))!=args.levels or not args.levels or min(args.levels)<1 or max(args.levels)>1024:
        parser.error('Strictly increasing concurrency levels1..1024 required')
    if args.mode=='prepare':prepare(args.root);return
    if not args.execute:parser.error('GPU execution requires explicit --execute after owner go')
    with lock(Path(str(args.root)+'.lock')):
        if (args.root/'owned-processes.json').exists():raise FileExistsError('Preserve previous launch; use fresh prepared root')
        loop=asyncio.new_event_loop();asyncio.set_event_loop(loop)
        task=loop.create_task(execute(args))
        for sig in (signal.SIGTERM,signal.SIGINT):loop.add_signal_handler(sig,task.cancel)
        try:loop.run_until_complete(task)
        finally:loop.close()


if __name__=='__main__':main()
