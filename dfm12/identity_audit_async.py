"""High-concurrency identity audits with one SQLite owner and bounded HTTP work."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
import uuid

import aiohttp

from .jobs import Queue, response_json, validate_audit


async def run(path, endpoints, concurrency):
    if not endpoints or not 1 <= concurrency <= 512:
        raise ValueError('Expected 1..512 requests per endpoint')
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=1) as database:
        queue = await loop.run_in_executor(database, Queue, path)

        async def call(method, *args):
            return await loop.run_in_executor(database, getattr(queue, method), *args)

        def indexes():
            queue.db.execute('CREATE INDEX IF NOT EXISTS identity_pending ON jobs(stage,status)')
            queue.db.execute('CREATE INDEX IF NOT EXISTS identity_running ON jobs(lease) WHERE status="running"')
        await loop.run_in_executor(database, indexes)
        headers = {}
        if os.environ.get('DFM12_API_KEY'):
            headers['Authorization'] = 'Bearer ' + os.environ['DFM12_API_KEY']
        try:
            async with aiohttp.ClientSession(headers=headers,
                    timeout=aiohttp.ClientTimeout(total=300),
                    connector=aiohttp.TCPConnector(limit=len(endpoints)*concurrency,
                                                   limit_per_host=concurrency)) as session:
                async def worker(endpoint):
                    owner = uuid.uuid4().hex
                    while True:
                        job = await call('claim', 'audit', owner)
                        if job is None:
                            return
                        key, encoded, attempts = job
                        try:
                            request = json.loads(encoded)['request']
                            async with session.post(endpoint.rstrip('/')+'/chat/completions', json=request) as response:
                                response.raise_for_status()
                                body = await response.json()
                            choice = body['choices'][0]
                            if choice.get('finish_reason') != 'stop':
                                raise ValueError('Incomplete generation: '+str(choice.get('finish_reason')))
                            result = response_json(choice['message']['content'])
                            validate_audit(result)
                        except Exception as exc:
                            await call('finish', key, owner, attempts+1, None,
                                       f'{type(exc).__name__}: {exc}'[:4000])
                            await asyncio.sleep(min(30, 2**attempts))
                        else:
                            await call('finish', key, owner, attempts+1, result)
                await asyncio.gather(*(worker(endpoint) for endpoint in endpoints for _ in range(concurrency)))
        finally:
            await call('close')
