"""Single bounded short-DFM1024 followup after the eight-GPU replay releases."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from scripts import calibrate_xl_eval_capacity as base
from dfm12.io import load,write_json,file_hash,lock


def command(gpu,port,utilization):
    return base.server_command(gpu,port,utilization,1024)+[
        '--compilation-config',json.dumps({'max_cudagraph_capture_size':512})]


def prepare(parent,root):
    from transformers import AutoTokenizer
    root.mkdir(parents=True,exist_ok=False)
    rows=[r for r in load(parent/'prompts.json') if r['family']=='dfm_short']
    tokenizer=AutoTokenizer.from_pretrained(base.MODEL,local_files_only=True,fix_mistral_regex=False)
    candidates=[];sources={};scanned=0;excluded=0
    for row in base.source_rows('dfm_short'):
        rendered=tokenizer.apply_chat_template(row['messages'],chat_template=base.TEMPLATE.read_text(),
                    tokenize=False,add_generation_prompt=True,enable_thinking=False)
        row['prompt_tokens']=len(tokenizer.encode(rendered,add_special_tokens=False));scanned+=1
        sources[row['source']]=None
        if row['prompt_tokens']+row['max_tokens']>4096:excluded+=1;continue
        candidates.append(row)
    stress=sorted(candidates,key=lambda r:(-r['prompt_tokens'],r['source'],r['id']))[:32]
    write_json(root/'prompts.json',dict(ordinary=rows,longest_recorded=stress))
    sources={p:file_hash(p) for p in sources}
    write_json(root/'prepared.json',dict(parent=str(parent.resolve()),sources=sources,scanned=scanned,
        excluded_context=excluded,longest_prompt_tokens=stress[0]['prompt_tokens'],
        pins={str(p.resolve()):file_hash(p) for p in [Path(__file__),Path(base.__file__),root/'prompts.json',parent/'prepared.json']},
        purpose='512/1024 ordinary replay plus32-concurrency longest-recorded short prompts',
        no_universal_batch_claim=True,judge_concurrency_16_unchanged=True))


async def execute(parent,root):
    import aiohttp
    while not (parent/'cleanup.json').exists():await asyncio.sleep(2)
    if any(code is None for code in load(parent/'cleanup.json')['exit_codes']):raise RuntimeError('Parent not cleaned up')
    base.free_gpus()
    for path,sha in load(root/'prepared.json')['pins'].items():
        if file_hash(path)!=sha:raise ValueError('Followup input drift')
    for path,sha in load(parent/'prepared.json')['pins'].items():
        if file_hash(path)!=sha:raise ValueError('Parent input drift')
    rows=load(root/'prompts.json');processes=[];report={}
    try:
        for gpu,utilization in [(1,.95),(5,.85)]:
            env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
                     WANDB_MODE='disabled',TOKENIZERS_PARALLELISM='false',VLLM_USE_FLASHINFER_SAMPLER='0',
                     FLASHINFER_DISABLE_VERSION_CHECK='1',CUDA_HOME=str(base.CUDA),CUDA_PATH=str(base.CUDA))
            env['PATH']=str(base.CUDA/'bin')+':'+str(Path(sys.executable).parent)+':'+env.get('PATH','')
            env['LD_LIBRARY_PATH']=str(base.CUDA/'lib')+':'+str(base.CUDA/'lib64')+':'+env.get('LD_LIBRARY_PATH','')
            for key,name in [('VLLM_CACHE_ROOT','vllm'),('TORCHINDUCTOR_CACHE_DIR','inductor'),
                             ('TRITON_CACHE_DIR','triton'),('CUDA_CACHE_PATH','cuda')]:
                env[key]=str((parent/f'gpu{gpu}'/name).resolve())
            port=59200+gpu
            with base.socket.socket() as sock:sock.bind(('127.0.0.1',port))
            argv=command(gpu,port,utilization)
            with (root/f'gpu{gpu}.server.log').open('w') as log:
                proc=subprocess.Popen(argv,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            processes.append(proc)
            write_json(root/f'gpu{gpu}.launch.json',dict(gpu=gpu,pid=proc.pid,port=port,command=argv))
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=2064)) as session:
            async def endpoint(gpu,proc):
                url=f'http://127.0.0.1:{59200+gpu}'
                while True:
                    if proc.poll() is not None:raise RuntimeError(f'GPU{gpu} failed startup')
                    try:
                        async with session.get(url+'/health',timeout=2) as response:
                            if response.status==200:break
                    except (aiohttp.ClientError,asyncio.TimeoutError):pass
                    await asyncio.sleep(2)
                print('READY',gpu,flush=True)
                await base.stage(session,url,rows['ordinary'],4,3,root/f'gpu{gpu}.warmup.json')
                summaries=[]
                for level in (512,1024):
                    result=await base.stage(session,url,rows['ordinary'],level,20,root/f'gpu{gpu}.c{level}.json')
                    summaries.append(result);print('STAGE',gpu,level,result['kv_steady_median'],result['output_tokens_per_second'],flush=True)
                    if not base.safe_next(result):break
                stress=await base.stage(session,url,rows['longest_recorded'],32,20,root/f'gpu{gpu}.longest.c32.json')
                report[str(gpu)]=dict(stages=summaries,longest_recorded=stress)
                write_json(root/f'gpu{gpu}.summary.json',report[str(gpu)])
            async with asyncio.timeout(480):
                async with asyncio.TaskGroup() as tasks:
                    for gpu,proc in zip((1,5),processes):tasks.create_task(endpoint(gpu,proc))
        write_json(root/'report.json',dict(gpus=report,policy_changed=False))
    except BaseException as exc:
        write_json(root/'failure.json',dict(error=repr(exc),completed=report));raise
    finally:
        base.cleanup(processes)
        write_json(root/'cleanup.json',dict(pids=[p.pid for p in processes],exit_codes=[p.poll() for p in processes]))


def main():
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('mode',choices=['prepare','run'])
    parser.add_argument('--parent',type=Path,required=True);parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if args.mode=='prepare':prepare(args.parent,args.root);return
    if not args.execute:parser.error('Explicit execute required')
    with lock(Path(str(args.root)+'.lock')):
        if list(args.root.glob('gpu*.launch.json')):raise FileExistsError('Preserve prior launch')
        loop=asyncio.new_event_loop();asyncio.set_event_loop(loop);task=loop.create_task(execute(args.parent,args.root))
        for sig in (signal.SIGTERM,signal.SIGINT):loop.add_signal_handler(sig,task.cancel)
        try:loop.run_until_complete(task)
        finally:loop.close()


if __name__=='__main__':main()
