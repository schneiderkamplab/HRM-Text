#!/usr/bin/env python3
"""Two read-only snapshots of shared DFM13 servers; no inference requests."""
import argparse
import asyncio
import csv
import io
import json
import math
from pathlib import Path
import subprocess
import time

import aiohttp
try:
    from measure_joint_synthetic_throughput import COUNTERS, parse_metrics
except ModuleNotFoundError:
    from scripts.measure_joint_synthetic_throughput import COUNTERS, parse_metrics


async def snapshot(session):
    async def endpoint(port):
        base = f'http://127.0.0.1:{port}'
        row = dict(port=port, errors={})
        for route in ('/v1/models', '/metrics'):
            try:
                async with session.get(base + route) as response:
                    response.raise_for_status()
                    body = await response.text()
                if route == '/v1/models':
                    row['models'] = json.loads(body)['data']
                    row['ready'] = any(m['id'] == 'dfm13-gemma4' for m in row['models'])
                else:
                    row['metrics'] = parse_metrics(body)
                    row['monotonic'] = time.monotonic()
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError) as exc:
                row['errors'][route] = repr(exc)
        return str(port), row
    result = dict(time=time.time(), endpoints=dict(await asyncio.gather(
        *(endpoint(p) for p in range(8800, 8808)))))
    try:
        output = subprocess.run(['nvidia-smi', '--query-gpu=index,utilization.gpu,memory.used,memory.total',
            '--format=csv,noheader,nounits'], capture_output=True, text=True, check=True, timeout=5).stdout
        result['gpus'] = [dict(zip(('index', 'utilization_percent', 'memory_used_mib', 'memory_total_mib'),
                                  (v.strip() for v in row))) for row in csv.reader(io.StringIO(output))]
    except (OSError, subprocess.SubprocessError) as exc:
        result['gpu_error'] = repr(exc)
    return result


def rates(before, after):
    result = {}
    for port, new in after['endpoints'].items():
        old = before['endpoints'][port]
        x, y = old.get('metrics', {}), new.get('metrics', {})
        valid = (old.get('ready') and new.get('ready') and x and y
                 and x.get('process_start_time_seconds') == y.get('process_start_time_seconds'))
        result[port] = {}
        for key in COUNTERS:
            delta = y[key] - x[key] if valid and y[key] >= x[key] else None
            result[port][key] = dict(delta=delta, per_second=delta / (new['monotonic'] - old['monotonic'])
                                    if delta is not None else None)
    totals = {k: sum(row[k]['per_second'] for row in result.values())
              if all(row[k]['per_second'] is not None for row in result.values()) else None for k in COUNTERS}
    return dict(per_endpoint=result, all_eight_per_second=totals)


async def run(args):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
        first = await snapshot(session)
        await asyncio.sleep(args.seconds)
        last = await snapshot(session)
    document = dict(requested_seconds=args.seconds, snapshots=[first, last], rates=rates(first, last),
        notes='Counters cover all shared clients. Success rate means completions/sec, not task accuracy. KV is a fraction. Missing/reset counters yield null rates; GPU utilization is instantaneous.')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as handle:
            json.dump(document, handle, indent=2, allow_nan=False)
            handle.write('\n')
    print(json.dumps(document, indent=2, allow_nan=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error('--seconds must be finite and positive')
    asyncio.run(run(args))
