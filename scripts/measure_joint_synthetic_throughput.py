#!/usr/bin/env python3
"""Read-only joint progress and shared-server throughput sampling; never generates."""
import argparse
import asyncio
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import time

import aiohttp
from prometheus_client.parser import text_string_to_metric_families

COUNTERS = ('request_success_total', 'generation_tokens_total',
            'prompt_tokens_total', 'num_preemptions_total')
GAUGES = ('num_requests_running', 'num_requests_waiting', 'kv_cache_usage_perc')


def parse_metrics(text):
    values = {}
    for family in text_string_to_metric_families(text):
        for sample in family.samples:
            name = sample.name.removeprefix('vllm:')
            if name == 'gpu_cache_usage_perc':
                name = 'kv_cache_usage_perc'
            if name in (*COUNTERS, *GAUGES, 'process_start_time_seconds'):
                if not math.isfinite(sample.value):
                    raise ValueError('Non-finite metric: ' + name)
                if name == 'kv_cache_usage_perc':
                    values[name] = max(values.get(name, 0), sample.value)
                else:
                    values[name] = values.get(name, 0) + sample.value
    missing = set((*COUNTERS, *GAUGES)) - values.keys()
    if missing:
        raise ValueError('Missing metrics: ' + ', '.join(sorted(missing)))
    return values


async def sample(root, endpoints, session):
    result = dict(time=time.time(), monotonic=time.monotonic())
    try:
        progress = json.loads((root / 'progress.json').read_text())
        result['progress'] = {k: progress.get(k) for k in
                              ('pid', 'time', 'phase', 'accepted', 'active', 'candidates')}
        result['progress_age_seconds'] = result['time'] - progress['time']
        if not isinstance(progress['accepted'], int):
            raise ValueError('Integer accepted count required')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result['progress_error'] = repr(exc)

    async def endpoint_sample(endpoint):
        try:
            async with session.get(endpoint + '/metrics') as response:
                response.raise_for_status()
                return endpoint, dict(metrics=parse_metrics(await response.text()),
                                      monotonic=time.monotonic())
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            return endpoint, dict(error=repr(exc))
    result['endpoints'] = dict(await asyncio.gather(*(endpoint_sample(e) for e in endpoints)))
    healthy = [e['metrics'] for e in result['endpoints'].values() if 'metrics' in e]
    result['gauges'] = dict(healthy_endpoints=len(healthy),
        running=sum(e['num_requests_running'] for e in healthy) if len(healthy) == len(endpoints) else None,
        waiting=sum(e['num_requests_waiting'] for e in healthy) if len(healthy) == len(endpoints) else None,
        kv_max=max((e['kv_cache_usage_perc'] for e in healthy), default=None),
        kv_mean=sum(e['kv_cache_usage_perc'] for e in healthy)/len(healthy) if healthy else None)
    return result


def interval(before, after, max_progress_age):
    elapsed = after['monotonic'] - before['monotonic']
    row = dict(seconds=elapsed, start=before['time'], end=after['time'],
               accepted_delta=None, accepted_per_minute=None, counters={}, errors=[])
    a, b = before.get('progress', {}), after.get('progress', {})
    if (before.get('progress_error') or after.get('progress_error')
            or not a.get('pid') or a.get('pid') != b.get('pid')
            or before.get('progress_age_seconds', math.inf) > max_progress_age
            or after.get('progress_age_seconds', math.inf) > max_progress_age
            or not isinstance(a.get('accepted'), int) or not isinstance(b.get('accepted'), int)
            or b['accepted'] < a['accepted']):
        row['errors'].append('Progress unavailable, stale, restarted, or accepted count decreased')
    else:
        row['accepted_delta'] = b['accepted'] - a['accepted']
        row['accepted_per_minute'] = row['accepted_delta'] * 60 / elapsed
        row['progress_timestamp_seconds'] = b['time'] - a['time']
    for metric in COUNTERS:
        changes, rates = {}, {}
        for endpoint, old in before['endpoints'].items():
            new = after['endpoints'].get(endpoint, {})
            x, y = old.get('metrics', {}), new.get('metrics', {})
            if (metric not in x or metric not in y or y[metric] < x[metric]
                    or x.get('process_start_time_seconds') != y.get('process_start_time_seconds')):
                row['errors'].append(f'{endpoint}: unavailable/reset {metric}')
                continue
            changes[endpoint] = y[metric] - x[metric]
            rates[endpoint] = changes[endpoint] / (new['monotonic'] - old['monotonic'])
        complete = len(changes) == len(before['endpoints'])
        row['counters'][metric] = dict(delta=sum(changes.values()) if complete else None,
            per_second=sum(rates.values()) if complete else None, per_endpoint_delta=changes,
            per_endpoint_per_second=rates)
    return row


def report(samples, args, complete):
    windows = [interval(a, b, args.max_progress_age) for a,b in zip(samples, samples[1:])]
    total = interval(samples[0], samples[-1], args.max_progress_age) if windows else None
    if total:
        if any(w['accepted_delta'] is None for w in windows):
            total['accepted_delta'] = total['accepted_per_minute'] = None
        for name in COUNTERS:
            if any(w['counters'][name]['delta'] is None for w in windows):
                total['counters'][name]['delta'] = total['counters'][name]['per_second'] = None
        total['interval_errors'] = [dict(window=i, errors=w['errors'])
                                  for i,w in enumerate(windows) if w['errors']]
    return dict(version=1, complete=complete, jointroot=str(args.jointroot.resolve()),
        requested_window_seconds=args.window, poll_seconds=args.poll,
        attribution='Server counters include ALL clients; accepted counts belong to jointroot only.',
        limitations='Progress is periodically published. Restarts between polls may evade detection if counters recover and no process-start metric is exposed.',
        kv_convention='Fraction, not percent; maximum across engine labels per endpoint.',
        summary=total, windows=windows, samples=samples)


async def measure(args):
    endpoints = [f'http://127.0.0.1:{port}' for port in range(8600, 8608)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve the artifact exclusively; an existing measurement is never overwritten.
    with args.output.open('x') as output:
        output.write('{}\n')
    samples = []
    start = time.monotonic()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=args.timeout),
            connector=aiohttp.TCPConnector(limit=8)) as session:
        deadline = start
        while True:
            await asyncio.sleep(max(0, deadline - time.monotonic()))
            samples.append(await sample(args.jointroot, endpoints, session))
            complete = samples[-1]['monotonic'] - start >= args.window
            document = report(samples, args, complete)
            temporary = args.output.with_suffix(args.output.suffix + '.tmp')
            temporary.write_text(json.dumps(document, indent=2, allow_nan=False) + '\n')
            temporary.replace(args.output)
            if document['windows']:
                window = document['windows'][-1]
                print(json.dumps(dict(seconds=window['seconds'], accepted_per_minute=window['accepted_per_minute'],
                    generated_tokens_per_second=window['counters']['generation_tokens_total']['per_second'],
                    errors=window['errors'])), flush=True)
            if complete:
                break
            deadline = min(deadline + args.poll, start + args.window)
    print(json.dumps(dict(output=str(args.output), summary=document['summary'])), flush=True)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--jointroot', type=Path, required=True)
    parser.add_argument('--window', type=float, default=300)
    parser.add_argument('--poll', type=float, default=30)
    parser.add_argument('--timeout', type=float, default=5)
    parser.add_argument('--max-progress-age', type=float, default=90)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if any(not math.isfinite(v) or v <= 0 for v in
           (args.window, args.poll, args.timeout, args.max_progress_age)):
        parser.error('Durations must be finite and positive')
    if not (args.jointroot / 'progress.json').is_file():
        parser.error('jointroot must have progress.json; launch the runtime first')
    if args.output is None:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        args.output = Path('logs/dfm12') / f'joint-throughput-{stamp}.json'
    asyncio.run(measure(args))


if __name__ == '__main__':
    main()
