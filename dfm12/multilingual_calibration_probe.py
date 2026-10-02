"""Run a pinned full calibration as measurement only, never creating pilot slots."""
import argparse
import asyncio
from pathlib import Path
import os
import time

from .io import lock, write_json
from .multilingual_diagnose import PromptBudget, RawResponseWriter, captured_query
from .multilingual_trial import gate, verify_inputs


async def run(root, endpoints):
    import aiohttp
    config = verify_inputs(root)
    if not config.get('calibration_measurement_only') or not config.get('diagnostic_followup'):
        raise ValueError('Probe requires an explicit measurement-only followup root')
    writer, budget = RawResponseWriter(root / 'raw-responses'), PromptBudget()
    write_json(root / 'probe-status.json', {'phase': 'calibrating', 'pid': os.getpid(), 'generation_authorized': False})
    async def query(session, endpoint, payload):
        count = budget.measure(payload)
        return await captured_query(session, endpoint, payload, writer, {'prompt_tokens': count, 'measurement_only': True})
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),
                connector=aiohttp.TCPConnector(limit=2)) as session:
            await gate(root, session, endpoints, query)
    except Exception as exc:
        write_json(root / 'probe-status.json', {'phase': 'failed', 'error': repr(exc), 'time': time.time(),
                                               'generation_authorized': False})
        raise
    write_json(root / 'probe-status.json', {'phase': 'complete', 'time': time.time(),
                                           'generation_authorized': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--endpoints', nargs='+', required=True)
    args = parser.parse_args()
    with lock(args.root / '.calibration-probe.lock'):
        asyncio.run(run(args.root, args.endpoints))
