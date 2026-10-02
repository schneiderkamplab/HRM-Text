"""One cached-only recovery of null finals and one reviewer decoder failure."""
import argparse
import asyncio
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path

import aiohttp

from scripts import dfm13_search_budgeted_remaining as previous

pilot = previous.pilot
base = previous.base
read = previous.read
ROOT = Path('data/dfm13/search-null-final-recovery7-20261001')
AUDIT = Path('data/dfm13/search-review-decoder-recovery1-20261001')


class FinalSession(previous.GenerationSession):
    def post(self, *args, **kwargs):
        request = previous.generation_request(kwargs['json'])
        request['messages'][0]['content'] += (
            '\nThe search observation is already delivered. This turn must contain ordinary final answer text, '
            'not a tool call, tool response, role delimiter, or empty response. No tools will be executed. '
            'If the supplied evidence cannot answer the question, explain precisely what is missing in final text.')
        request['temperature'] = 0.3
        kwargs['json'] = request
        base.atomic(self.folder / 'actual-request.json', request)
        return self.session.post(*args, **kwargs)


def prepare():
    if ROOT.exists() or AUDIT.exists():
        raise ValueError('new roots required')
    manifest = deepcopy(pilot.previous.verify(previous.ROOT))
    jobs = []; audits = []
    for job in read(previous.ROOT / 'jobs.json'):
        folder = previous.ROOT / 'records' / job['id']
        outcome = read(folder / 'outcome.json')
        if outcome['status'] != 'error':
            continue
        response_path = folder / 'generation/answer-response.json'
        response = json.loads(read(response_path)['body'])['choices'][0]
        if response['message'].get('content') is None and response['finish_reason'] == 'stop':
            jobs.append(job)
        elif (folder / 'candidate.json').exists() and (folder / 'audit/review-response.json').exists():
            audits.append(dict(job=job, candidate=str(folder / 'candidate.json'),
                               candidate_sha256=base.file_hash(folder / 'candidate.json')))
        else:
            raise ValueError('unrecognized recovery case')
        for path in (folder / 'outcome.json', response_path):
            manifest['pins'][str(path.resolve())] = base.file_hash(path)
    if len(jobs) != 7 or len(audits) != 1:
        raise ValueError('expected seven null finals and one review failure')
    for root, values in ((ROOT, jobs), (AUDIT, audits)):
        config = deepcopy(manifest)
        base.atomic(root / 'jobs.json', values)
        for path in (Path(__file__), root / 'jobs.json'):
            config['pins'][str(path.resolve())] = base.file_hash(path)
        config.update(total=len(values), max_attempts=1, paid_calls_allowed=0, admission_authorized=False)
        base.atomic(root / 'manifest.json', config)


async def audit():
    from transformers import AutoTokenizer
    manifest = pilot.previous.verify(AUDIT)
    tokenizer = AutoTokenizer.from_pretrained(manifest['tokenizer_dir'], local_files_only=True)
    item = read(AUDIT / 'jobs.json')[0]
    job = item['job']; folder = AUDIT / 'records' / job['id']
    if (folder / 'outcome.json').exists():
        return
    if (folder / 'started.json').exists():
        base.atomic(folder / 'outcome.json', dict(status='interrupted', admission_authorized=False))
        return
    path = Path(item['candidate'])
    if base.file_hash(path) != item['candidate_sha256']:
        raise ValueError('candidate changed')
    candidate = read(path)
    base.atomic(folder / 'candidate.json', candidate)
    base.atomic(folder / 'student-render.json', read(path.parent / 'student-render.json'))
    base.atomic(folder / 'started.json', dict(at=base.now(), pid=os.getpid()))
    payload = dict(requirements=dict(original_user_prompt=job['sample']['prompt'],
        original_timestamp=job['sample']['original_timestamp'], retrieval_date='2026-10-01'),
        answer=candidate['messages'][-1]['content'], pages=job['pages'], verified_checks=[])
    messages = pilot.reviewer.messages(payload)
    messages[0]['content'] += (' Return compact JSON only. In finding strings describe code defects in plain words; '
        'do not reproduce source-code string literals or escape sequences. Complete all required fields and the closing brace.')
    async with aiohttp.ClientSession(trust_env=False) as session:
        try:
            model = base.Model(pilot.mode.ModeSession(session, 'json_object', folder / 'audit'),
                               tokenizer, manifest, manifest['endpoints'][0], 600)
            raw = await model.ask(messages, pilot.bounded.SCHEMA, None, folder / 'audit', 'review')
            base.atomic(folder / 'raw-review.json', raw)
            try:
                result = pilot.bounded.derive(raw, job['pages'], payload['answer'])
            except ValueError as error:
                result = dict(verdict='needs_verification', reason=str(error))
            base.atomic(folder / 'review.json', result)
            outcome = dict(status='reviewed', **pilot.previous.gated_outcome(job['id'], result['verdict'], True))
        except Exception as error:
            outcome = dict(status='error', error=str(error), admission_authorized=False)
        base.atomic(folder / 'outcome.json', dict(**outcome, candidate_sha256=item['candidate_sha256']))


async def run():
    os.environ.pop('JINA_API_KEY', None)
    with (AUDIT / 'run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        await audit()
    with (ROOT / 'run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pilot.GenerationSession = FinalSession
        original = base.atomic
        def atomic(path, value):
            if Path(path) == ROOT / 'progress.json':
                value = dict(value, total=7)
            original(path, value)
        base.atomic = atomic
        await pilot.run(argparse.Namespace(root=ROOT, concurrency_per_server=8, timeout=600))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run'])
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    else:
        asyncio.run(run())
