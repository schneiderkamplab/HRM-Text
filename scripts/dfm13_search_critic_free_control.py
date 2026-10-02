"""Bounded critic-free comparison on saved controls; no retrieval or admission."""
import asyncio
from collections import Counter
import json
import os
from pathlib import Path

import aiohttp

from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_json_mode_probe as probe
from scripts import dfm13_search_adjudication_retry as bounded

SOURCE = Path('data/dfm13/search-critique-adjudication-20261001')
ROOT = Path('data/dfm13/search-critic-free-control-20261001')


def messages(payload):
    # An earlier model's verdict must not anchor this independent assessment.
    clean = {k: payload[k] for k in ('requirements', 'answer', 'pages', 'verified_checks')}
    clean['verified_check_plain_text'] = bounded.check_text(clean['verified_checks'])
    result = probe.messages(clean)
    result[0]['content'] += (
        ' Evaluate every consequential factual assertion, including supporting explanations, not only the main conclusion.'
        ' A demonstrated false supporting assertion is a confirmed error even if the main conclusion might be true.'
        ' Failure of one example does not prove a universal minimum or impossibility for all alternatives.'
        ' Distinguish what the answer actually says from a charitable corrected interpretation.'
        ' Check whether future events are expressly described as future, rather than assuming they are.'
        ' Do not infer that source agreement defeats a verified counterexample.'
    )
    return result


async def run():
    if ROOT.exists():
        raise ValueError('new control root required')
    os.environ.pop('JINA_API_KEY', None)
    manifest = json.loads((SOURCE / 'manifest.json').read_text())
    for path, expected_hash in manifest['pins'].items():
        if base.file_hash(Path(path)) != expected_hash:
            raise ValueError('source pin mismatch')
    jobs = json.loads((SOURCE / 'jobs.json').read_text())
    if len(jobs) != 8 or len(manifest['endpoints']) != 8:
        raise ValueError('bounded eight-case control required')
    expected = {x['id']: x['expected'] for x in json.loads((SOURCE / 'expectations.json').read_text())}
    pins = {}
    for job in jobs:
        path = SOURCE / 'records' / job['id'] / 'adjudication-request.json'
        job['payload'] = json.loads(json.loads(path.read_text())['messages'][-1]['content'])
        pins[str(path.resolve())] = base.file_hash(path)
    for path in (Path(__file__), Path(probe.__file__), Path(bounded.__file__), SOURCE / 'jobs.json', SOURCE / 'expectations.json'):
        pins[str(path.resolve())] = base.file_hash(path)
    base.atomic(ROOT / 'manifest.json', dict(pins=pins, total=8, paid_calls=0,
        generation_calls=0, max_attempts=1, response_format='json_object', penalties='none',
        max_tokens=2048, changes=['remove prior critique', 'assess supporting assertions explicitly'],
        expectations_not_sent=True, admission_authorized=False))
    base.atomic(ROOT / 'runtime.json', dict(pid=os.getpid(), requests_per_endpoint=1, paid_calls=0))
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(manifest['tokenizer_dir'], local_files_only=True)
    async with aiohttp.ClientSession(trust_env=False) as session:
        async def one(index, job):
            folder = ROOT / 'records' / job['id']
            try:
                model = base.Model(probe.ModeSession(session, 'json_object', folder), tokenizer,
                                   manifest, manifest['endpoints'][index], 600)
                raw = await model.ask(messages(job['payload']), bounded.SCHEMA, None, folder, 'adjudication')
                base.atomic(folder / 'raw-adjudication.json', raw)
                try:
                    review = bounded.derive(raw, job['pages'], job['answer'])
                except ValueError as error:
                    review = dict(verdict='needs_verification', reason=str(error))
                base.atomic(folder / 'review.json', review)
                outcome = dict(status='reviewed', verdict=review['verdict'],
                               passed=review['verdict'] == expected[job['id']])
            except Exception as error:
                outcome = dict(status='error', error=str(error), passed=False)
            base.atomic(folder / 'outcome.json', dict(**outcome, expected=expected[job['id']],
                        candidate_sha256=job['candidate_sha256'], admission_authorized=False))
            rows = [json.loads(p.read_text()) for p in (ROOT / 'records').glob('*/outcome.json')]
            base.atomic(ROOT / 'progress.json', dict(terminal=len(rows), total=8,
                        passed=sum(r['passed'] for r in rows),
                        counts=dict(Counter(r.get('verdict', r['status']) for r in rows))))
        await asyncio.gather(*(one(i, job) for i, job in enumerate(jobs)))
    base.atomic(ROOT / 'finished.json', dict(json.loads((ROOT / 'progress.json').read_text()),
                paid_calls=0, production_authorized=False))


if __name__ == '__main__':
    asyncio.run(run())
