"""Isolated schema A/B diagnostic; outputs are never training candidates.

Requires an idle existing endpoint. Does not manage production or servers.
"""
import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time

import httpx
import psutil

from audit_pipeline.dfm14 import Generation
from dfm12.io import load, write_json
from scripts.diagnose_dfm14_utilization import metrics


def prepare(root):
    adapter = Generation(root, root, 'http://127.0.0.1:8800/v1')
    adapter.initialize_cpu()
    jobs = load(root / 'manifest.json')['jobs']
    payloads = []
    seen = set()
    for job in jobs:
        key = (job['language'], job['family'])
        if key in seen:
            continue
        for slot in range(job['start'], min(job['end'], job['start'] + 8)):
            try:
                _, _, payload, _ = adapter.prepare(job, slot, 0)
            except ValueError:
                continue
            payload = copy.deepcopy(payload)
            payload.update(max_tokens=256, temperature=0, seed=0)
            payloads.append(payload)
            seen.add(key)
            break
        if len(payloads) == 64:
            break
    if len(payloads) < 16:
        raise ValueError('Too few representative prompts')
    return payloads


async def bench(args, payloads):
    endpoint = f'http://127.0.0.1:{args.port}/v1'
    engine = psutil.Process(args.engine_pid)
    def cpu_seconds():
        c = engine.cpu_times()
        return c.user + c.system

    async with httpx.AsyncClient(timeout=600, trust_env=False,
            limits=httpx.Limits(max_connections=512, max_keepalive_connections=128)) as client:
        for _ in range(3):
            m = await asyncio.to_thread(metrics, args.port)
            if m.get('vllm:num_requests_running', 0) or m.get('vllm:num_requests_waiting', 0):
                raise RuntimeError('Endpoint is not isolated/idle')
            await asyncio.sleep(1)

        async def request(payload):
            response = await client.post(endpoint + '/chat/completions', json=payload)
            response.raise_for_status()
            body = response.json()
            return dict(tokens=body['usage']['completion_tokens'],
                        finish=body['choices'][0]['finish_reason'])

        # Warm both variants and all prompt prefixes before timing.
        for constrained in (True, False):
            warm = []
            for original in payloads:
                p = copy.deepcopy(original)
                p['max_tokens'] = 1
                if not constrained:
                    p.pop('response_format', None)
                warm.append(request(p))
            await asyncio.gather(*warm)

        results = []
        for constrained in (True, False, False, True):
            encoded = []
            for i in range(args.requests):
                p = copy.deepcopy(payloads[i % len(payloads)])
                if not constrained:
                    p.pop('response_format', None)
                encoded.append(json.dumps(p).encode())
            samples = []
            async def observe():
                while True:
                    def sample():
                        gpu = subprocess.check_output(['nvidia-smi', '-i', str(args.gpu),
                            '--query-gpu=utilization.gpu,power.draw',
                            '--format=csv,noheader,nounits'], text=True)
                        util, watts = map(float, gpu.strip().split(','))
                        return dict(time=time.time(), gpu=util, watts=watts,
                                    metrics=metrics(args.port))
                    samples.append(await asyncio.to_thread(sample))
                    await asyncio.sleep(.5)
            observation = asyncio.create_task(observe())
            sem = asyncio.Semaphore(512)
            async def timed(p):
                async with sem:
                    r = await client.post(endpoint + '/chat/completions', content=p,
                                          headers={'Content-Type': 'application/json'})
                    r.raise_for_status()
                    b = r.json()
                    return b['usage']['completion_tokens'], b['choices'][0]['finish_reason']
            start_cpu, start = cpu_seconds(), time.monotonic()
            try:
                rows = await asyncio.gather(*(timed(p) for p in encoded))
            finally:
                observation.cancel()
                await asyncio.gather(observation, return_exceptions=True)
            elapsed = time.monotonic() - start
            result = dict(schema=constrained, seconds=elapsed,
                tokens=sum(r[0] for r in rows), tokens_per_sec=sum(r[0] for r in rows)/elapsed,
                mean_gpu=statistics.mean(s['gpu'] for s in samples),
                engine_cpu_cores=(cpu_seconds()-start_cpu)/elapsed,
                length_limited=sum(r[1]=='length' for r in rows), requests=len(rows), samples=samples)
            results.append(result)
            write_json(args.output, dict(training_ready=False, prompt_count=len(payloads),
                prompt_sha256=hashlib.sha256(json.dumps(payloads,sort_keys=True).encode()).hexdigest(),
                concurrency=512, max_tokens=256, rounds=results))
            print(json.dumps({k:v for k,v in result.items() if k!='samples'}), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path('data/dfm14/production-v1'))
    p.add_argument('--payloads', type=Path, required=True)
    p.add_argument('--prepare', action='store_true')
    p.add_argument('--port', type=int, default=8800)
    p.add_argument('--gpu', type=int, default=0)
    p.add_argument('--engine-pid', type=int)
    p.add_argument('--requests', type=int, default=1024)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    if args.prepare:
        write_json(args.payloads, prepare(args.root))
        print('Prepared', args.payloads)
    else:
        if not args.output or not args.engine_pid:
            p.error('--output and --engine-pid required')
        asyncio.run(bench(args, load(args.payloads)))


if __name__ == '__main__':
    main()
