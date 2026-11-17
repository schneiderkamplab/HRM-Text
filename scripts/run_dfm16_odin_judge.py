"""Independent remote Odin prose checks, using the shared audit dispatcher."""
import argparse
import asyncio
from copy import deepcopy
from collections import Counter, deque
import getpass
import os
import time
from pathlib import Path

import httpx

from audit_pipeline.runtime import run
from dfm12.io import file_hash, load, lock, rows, write_json
from scripts.dfm16_mimir_judge import MimirProbe
from scripts.dfm16_story_v3 import SeedAudit
from scripts.queue_dfm16_stories_qwen import DEFAULT, prepare_stage, audited_records

ENDPOINT = 'https://api.odincore.ai/v1'
MODEL = 'odin-2-large'


class RateLimitedClient(httpx.AsyncClient):
    def __init__(self, concurrency=64, requests_per_minute=180, window_seconds=60, **kwargs):
        super().__init__(**kwargs)
        if concurrency < 1 or requests_per_minute < 1 or window_seconds <= 0:
            raise ValueError('Concurrency, rate and window must be positive')
        self.capacity = concurrency
        self.active = self.peak = self.requests = 0
        self.condition = asyncio.Condition()
        self.rate_headers = []
        self.rate_budget = requests_per_minute
        self.window_seconds = window_seconds
        self.cooldown_until = 0
        self.sent = deque()

    async def send(self, *args, **kwargs):
        # Gate actual HTTP sends, including GET preflights and retried POSTs.
        async with self.condition:
            while True:
                now = time.monotonic()
                while self.sent and self.sent[0] <= now-self.window_seconds:
                    self.sent.popleft()
                limited = len(self.sent) >= self.rate_budget
                ready_at = max(self.cooldown_until,
                    self.sent[0]+self.window_seconds if limited else now)
                if self.active < self.capacity and ready_at <= now:
                    break
                if ready_at > now:
                    try:
                        await asyncio.wait_for(self.condition.wait(), ready_at-now)
                    except TimeoutError:
                        pass
                else:
                    await self.condition.wait()
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.requests += 1
            self.sent.append(time.monotonic())
        try:
            response = await super().send(*args, **kwargs)
            if response.status_code == 429:
                headers = {k: v for k,v in response.headers.items()
                           if k == 'retry-after' or 'ratelimit' in k}
                self.rate_headers.append(headers)
                try:
                    delay = max(self.window_seconds, float(headers.get('retry-after', 0)))
                except ValueError:
                    delay = self.window_seconds
                self.cooldown_until = max(self.cooldown_until, time.monotonic()+delay)
                print('Rate limit headers: '+str(headers), flush=True)
            return response
        finally:
            async with self.condition:
                self.active -= 1
                self.condition.notify_all()


class OdinProse(SeedAudit):
    # This provider's models endpoint does not advertise context lengths.
    context_length = 0
    model = MODEL
    @staticmethod
    def parse_review(body):
        normalized = deepcopy(body)
        message = normalized['choices'][0]['message']
        message['content'] = message['content'].strip().removesuffix('.')
        return MimirProbe.parse_review(normalized)

    def prepare(self, row):
        return dict(model=self.model, temperature=0, max_tokens=8,
            messages=[dict(role='user', content=row['prompt'])])

    def report(self, snapshot):
        client = self.api_client
        snapshot.update(actual_http_inflight=client.active, actual_http_peak=client.peak,
            actual_http_requests=client.requests, concurrency_limit=client.capacity,
            requests_per_minute=client.rate_budget)
        write_json(self.output/'pipeline/endpoint-odin.json', snapshot)


async def execute(root, key, concurrency, requests_per_minute):
    adapter = OdinProse(root/'probe', root/'probe/audit', ENDPOINT)
    async with RateLimitedClient(concurrency, requests_per_minute,
            headers={'Authorization': 'Bearer '+key},
            timeout=120, trust_env=False, follow_redirects=False,
            limits=httpx.Limits(max_connections=concurrency)) as client:
        adapter.api_client = client
        # A restarted client has no timestamps for prior in-flight API calls.
        print('Waiting 60s before this API session to clear prior local quota', flush=True)
        await asyncio.sleep(60)
        # Check model and output contract before issuing the full paid sample.
        response = await client.get(ENDPOINT+'/models')
        response.raise_for_status()
        if MODEL not in {m['id'] for m in response.json()['data']}:
            raise ValueError('Requested model is unavailable')
        first = next(rows(root/'probe/chunks/000000.jsonl'))
        response = await client.post(ENDPOINT+'/chat/completions', json=adapter.prepare(first))
        response.raise_for_status()
        body = response.json()
        write_json(root/'preflight-response.json', body)
        print('Preflight response: '+repr(body['choices'][0]['message']['content']), flush=True)
        verdict = adapter.parse_review(body)
        write_json(root/'preflight.json', dict(response=body, verdict=verdict))
        print('Preflight passed: '+str(verdict), flush=True)
        write_json(root/'probe/audit/pipeline/state.json', dict(phase='running'))
        try:
            await run(adapter, ENDPOINT, concurrency, client=client, prefetch=1)
            write_json(root/'probe/audit/pipeline/state.json', dict(phase='complete'))
        except Exception:
            write_json(root/'probe/audit/pipeline/state.json', dict(phase='failed'))
            raise
        finally:
            write_json(root/'concurrency.json', dict(final_limit=client.capacity,
                actual_requests=client.requests, actual_peak=client.peak,
                requests_per_minute=client.rate_budget,
                rate_limit_headers=client.rate_headers))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT/'odin-text-units')
    parser.add_argument('--concurrency', type=int, default=64)
    parser.add_argument('--requests-per-minute', type=int, default=180)
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 1024 or args.requests_per_minute < 1:
        parser.error('Concurrency must be 1..1024 and request budget positive')
    if (args.root/'status.json').exists() and load(args.root/'status.json')['phase'] == 'complete':
        print(load(args.root/'summary.json'))
        return
    key = os.environ.get('ODIN_API_KEY') or getpass.getpass('API key: ')
    with lock(args.root/'.lock'):
        source = DEFAULT/'mimir-text-units/probe'
        records = [row for chunk in load(source/'manifest.json')['chunks']
                   for row in rows(source/chunk['input'])]
        prepare_stage(args.root/'probe', records, 'odin_prose_comparison_v1')
        write_json(args.root/'launch.json', dict(model=MODEL, endpoint=ENDPOINT,
            source_manifest_sha256=file_hash(source/'manifest.json'),
            concurrency=args.concurrency, requests_per_minute=args.requests_per_minute,
            checks=len(records), production_authorized=False))
        write_json(args.root/'status.json', dict(phase='running'))
        try:
            asyncio.run(execute(args.root, key, args.concurrency, args.requests_per_minute))
        except Exception as exc:
            # Never serialize credentials, headers or provider exception bodies.
            write_json(args.root/'status.json', dict(phase='failed', error_type=type(exc).__name__))
            raise
        counts = Counter()
        comparisons = Counter()
        mimir = load(DEFAULT/'mimir-text-units/summary.json')['decisions']
        for row, result in audited_records(args.root/'probe'):
            outcome = result.get('review', {}).get('decision', result['status'])
            counts[(row['language'], row['aspect'], outcome)] += 1
            comparisons[(row['aspect'], mimir[row['id']]['probe'], outcome)] += 1
        summary = dict(counts={'/'.join(k): v for k,v in sorted(counts.items())},
            mimir_odin={'/'.join(k): v for k,v in sorted(comparisons.items())},
            production_authorized=False)
        write_json(args.root/'summary.json', summary)
        write_json(args.root/'status.json', dict(phase='complete'))
        print(summary, flush=True)


if __name__ == '__main__':
    main()
