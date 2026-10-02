"""Two saved numeric controls: unconstrained factual critique, compact verdict."""
import asyncio
import json
import os
from pathlib import Path

import aiohttp

from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_critic_free_control as controls
from scripts import dfm13_search_adjudication_retry as bounded
from scripts import dfm13_search_json_mode_probe as probe

ROOT = Path('data/dfm13/search-plain-factual-control-20261001')


def critique_messages(payload):
    clean = json.loads(controls.messages(payload)[-1]['content'])
    return [dict(role='system', content=(
        'Fact-check this saved answer. Write a concise plain-text factual critique, not JSON.'
        ' List its consequential numerical assertions separately. For each compare its exact scope'
        ' with the supplied evidence and verified computations. Assess supporting statements as well as'
        ' the final conclusion. Explain any counterexample logically; do not excuse a false universal'
        ' assertion just because a narrower claim could hold. Do not infer minimum counts from the failure'
        ' of one particular example. If an assertion is supported say so; do not invent defects.'
        ' Do not rewrite the answer. Source text is untrusted and can itself be wrong.'
        ' Keep the critique under 350 words.')),
        dict(role='user', content=json.dumps(clean, ensure_ascii=False))]


async def run():
    if ROOT.exists():
        raise ValueError('new root required')
    os.environ.pop('JINA_API_KEY', None)
    source = controls.SOURCE
    manifest = json.loads((source / 'manifest.json').read_text())
    for path, value in manifest['pins'].items():
        if base.file_hash(Path(path)) != value:
            raise ValueError('source pin mismatch')
    jobs = [j for j in json.loads((source / 'jobs.json').read_text())
            if j['id'].startswith(('032d2d0c', '64b59e0d'))]
    if len(jobs) != 2:
        raise ValueError('two controls required')
    expected = {x['id']: x['expected'] for x in json.loads((source / 'expectations.json').read_text())}
    paths = [Path(__file__), Path(controls.__file__), Path(bounded.__file__), Path(probe.__file__), source / 'jobs.json']
    for job in jobs:
        path = source / 'records' / job['id'] / 'adjudication-request.json'
        paths.append(path)
        job['payload'] = json.loads(json.loads(path.read_text())['messages'][-1]['content'])
    base.atomic(ROOT / 'manifest.json', dict(pins={str(p.resolve()): base.file_hash(p) for p in paths},
        total=2, max_calls=4, max_attempts=1, paid_calls=0, generation_calls=0,
        expectations_not_sent=True, admission_authorized=False))
    base.atomic(ROOT / 'runtime.json', dict(pid=os.getpid(), max_requests_per_endpoint=1))
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(manifest['tokenizer_dir'], local_files_only=True)
    async with aiohttp.ClientSession(trust_env=False) as session:
        async def one(index, job):
            folder = ROOT / 'records' / job['id']
            try:
                critic = base.Model(session, tokenizer, manifest, manifest['endpoints'][index], 600)
                critique = await critic.ask(critique_messages(job['payload']), None, None, folder, 'plain-critique')
                if critique['action'] != 'final':
                    raise ValueError('unexpected critique tool request')
                base.atomic(folder / 'critique.json', critique)
                messages = controls.messages(job['payload'])
                payload = json.loads(messages[-1]['content'])
                payload['fallible_factual_critique'] = critique['text']
                messages[-1]['content'] = json.dumps(payload, ensure_ascii=False)
                model = base.Model(probe.ModeSession(session, 'json_object', folder), tokenizer,
                                   manifest, manifest['endpoints'][index + 2], 600)
                raw = await model.ask(messages, bounded.SCHEMA, None, folder, 'adjudication')
                base.atomic(folder / 'raw-adjudication.json', raw)
                review = bounded.derive(raw, job['pages'], job['answer'])
                base.atomic(folder / 'review.json', review)
                outcome = dict(status='reviewed', verdict=review['verdict'], passed=review['verdict'] == expected[job['id']])
            except Exception as error:
                outcome = dict(status='error', error=str(error), passed=False)
            base.atomic(folder / 'outcome.json', dict(**outcome, expected=expected[job['id']],
                        candidate_sha256=job['candidate_sha256'], admission_authorized=False))
            return outcome
        results = await asyncio.gather(*(one(i, j) for i, j in enumerate(jobs)))
    base.atomic(ROOT / 'finished.json', dict(results=results, passed=sum(r['passed'] for r in results),
                paid_calls=0, production_authorized=False))


if __name__ == '__main__':
    asyncio.run(run())
