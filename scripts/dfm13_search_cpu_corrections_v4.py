"""Two exact attribution corrections, with fresh hash-bound unchanged reviews."""
import asyncio
from copy import deepcopy
import fcntl
import os
from pathlib import Path

import aiohttp
import jinja2
from tokenizers import Tokenizer

from scripts import dfm13_search_budgeted_pilot as pilot

base = pilot.base
read = pilot.previous.read
ROOT = Path('data/dfm13/search-heldout-cpu-corrections-20261001-v4')
SOURCE = Path('data/dfm13/search-heldout-cpu-corrections-20261001-v3')
ASSESSMENT = Path('docs/reports/dfm13_search_cpu_corrections_v3_assessment_20261001.json')
EDITS = {
    '918bee08': ('Forum suggestions about contact, sound change or population size should therefore be presented as proposals requiring language-specific evidence, not a demonstrated universal explanation.',
                 'A causal explanation requires language-specific evidence.'),
    '81484873': ('El material consultado trata la integración, evaluación, planificación y paralización de actividades.',
                 'El material consultado trata la integración y la paralización de actividades.'),
}


def correct(candidate):
    result = deepcopy(candidate)
    old, new = EDITS[candidate['id'][:8]]
    text = result['messages'][-1]['content']
    if text.count(old) != 1:
        raise ValueError('exact unique correction anchor required')
    result['messages'][-1]['content'] = text.replace(old, new)
    return result


def prepare():
    if ROOT.exists():
        raise ValueError('new root required')
    assessment = read(ASSESSMENT)
    if base.file_hash(SOURCE / 'queue.json') != assessment['queue_sha256']:
        raise ValueError('assessment queue changed')
    config = read(pilot.ROOT / 'manifest.json')
    info = config['student_tokenizer_info']
    tokenizer = Tokenizer.from_file(info['tokenizer_path'])
    template = jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
    jobs = []
    pins = {str(p.resolve()): base.file_hash(p) for p in
            (Path(__file__), ASSESSMENT, SOURCE / 'queue.json')}
    for case in assessment['cases']:
        if case['id'][:8] not in EDITS:
            continue
        source = SOURCE / case['id'] / 'candidate.json'
        if base.file_hash(source) != case['candidate_sha256']:
            raise ValueError('reviewed candidate changed')
        candidate = correct(read(source))
        candidate['correction_provenance']['localized_revision'] = dict(
            parent_sha256=base.file_hash(source), assessment_sha256=base.file_hash(ASSESSMENT),
            change='Only the independently identified unsupported attribution replaced.',
            original_hold_not_cleared=True)
        checked, _ = pilot.contract.strict_row(candidate, candidate['provenance']['prompt'])
        rendering = pilot.contract.rendered_targets(checked, tokenizer, template, info, 4096)
        if not all(r['fits_student_context'] for r in rendering):
            raise ValueError('student overflow')
        folder = ROOT / case['id']
        base.atomic(folder / 'candidate.json', candidate)
        base.atomic(folder / 'render.json', rendering)
        support = SOURCE / case['id'] / 'support.json'
        base.atomic(folder / 'support.json', read(support))
        for path in (source, support, folder / 'candidate.json', folder / 'support.json'):
            pins[str(path.resolve())] = base.file_hash(path)
        jobs.append(dict(id=case['id'], candidate=str(folder / 'candidate.json'),
            candidate_sha256=base.file_hash(folder / 'candidate.json'), render=rendering,
            admission_authorized=False))
    base.atomic(ROOT / 'queue.json', jobs)
    pins[str((ROOT / 'queue.json').resolve())] = base.file_hash(ROOT / 'queue.json')
    base.atomic(ROOT / 'manifest.json', dict(**{k: config[k] for k in
        ('tokenizer_dir', 'context_tokens', 'model', 'endpoints')}, pins=pins,
        paid_calls=0, admission_authorized=False))


async def run():
    from transformers import AutoTokenizer
    config = pilot.previous.verify(ROOT)
    os.environ.pop('JINA_API_KEY', None)
    tokenizer = AutoTokenizer.from_pretrained(config['tokenizer_dir'], local_files_only=True)
    base.atomic(ROOT / 'runtime.json', dict(pid=os.getpid(), max_requests_per_endpoint=1, paid_calls=0))
    async with aiohttp.ClientSession(trust_env=False) as session:
        for index, job in enumerate(read(ROOT / 'queue.json')):
            folder = ROOT / job['id']
            if (folder / 'outcome.json').exists():
                continue
            if (folder / 'started.json').exists():
                base.atomic(folder / 'outcome.json', dict(status='interrupted', admission_authorized=False))
                continue
            base.atomic(folder / 'started.json', dict(at=base.now()))
            try:
                candidate = read(Path(job['candidate']))
                pages = read(folder / 'support.json')['pages']
                payload = dict(requirements=dict(original_user_prompt=candidate['provenance']['prompt'],
                    original_timestamp=candidate['provenance']['original_timestamp'], retrieval_date='2026-10-01'),
                    answer=candidate['messages'][-1]['content'], pages=pages, verified_checks=[])
                model = base.Model(pilot.mode.ModeSession(session, 'json_object', folder / 'audit'),
                    tokenizer, config, config['endpoints'][index], 600)
                raw = await model.ask(pilot.reviewer.messages(payload), pilot.bounded.SCHEMA,
                                      None, folder / 'audit', 'review')
                base.atomic(folder / 'raw-review.json', raw)
                result = pilot.bounded.derive(raw, pages, payload['answer'])
                outcome = dict(status='reviewed', **result)
            except Exception as error:
                outcome = dict(status='error', error=str(error))
            base.atomic(folder / 'outcome.json', dict(**outcome,
                candidate_sha256=job['candidate_sha256'], admission_authorized=False))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run'])
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    else:
        with (ROOT / 'run.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            asyncio.run(run())
