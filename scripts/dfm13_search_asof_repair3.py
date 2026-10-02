"""Three scoped cached-evidence repairs with one unambiguous question date."""
import argparse
import asyncio
from copy import deepcopy
import fcntl
import hashlib
from pathlib import Path
import re

import jinja2
from tokenizers import Tokenizer

from scripts import dfm13_search_budgeted_remaining as previous

base = previous.base
pilot = previous.pilot
read = previous.read
ROOT = Path('data/dfm13/search-asof-scoped-repair3-20261001')
RECEIPT = Path('docs/reports/dfm13_search_remaining48_keeps8_manual_assessment_20261001.json')
PLANS = {
    '42c1b060': dict(root=previous.ROOT,
        url='https://keia.org/analysis/what-happened-to-u-s-korea-trade-one-year-after-tariffs/',
        anchors=['Along these lines, there was indeed a'],
        scope='Retrospective report about auto tariffs. This excerpt does not establish a complete tariff schedule for all goods at the question date; do not substitute its later current situation.'),
    '56c21202': dict(root=previous.ROOT,
        url='https://qwenlm.github.io/blog/qwen2/',
        anchors=['### Qwen2-57B-A14B-Instruct', '| Datasets | Mixtral-8x7B-Instruct-v0.1', '| Models | M-MMLU (5-shot)'],
        scope='Vendor benchmark tables, not independent community-reception evidence. Preserve model names, benchmark settings and attribution; state the reception-evidence limitation.'),
    '7213d507': dict(root=previous.batch.ROOT,
        url='https://next.gazeta.pl/next/7,151003,12858742,biedronka-przegrala-w-sadzie-spor-o-nazwe-forum-pracownikow.html',
        anchors=['14 listopada 2012, 21:04', 'Forum internetowe Nasza-Biedronka.pl,',
                 'Na początku roku stroną zainteresował', 'We wrześniu Sąd Polubowny', 'Dlaczego tak późno?'],
        scope='Dated newspaper report. Distinguish the reported ruling from subsequent settlement discussions; do not treat party allegations as findings.'),
}


def replace_controller_date(messages, timestamp):
    result = deepcopy(messages)
    system = result[0]
    if system.get('role') != 'system' or not system['content'].startswith(
            'Create a new evidence-grounded answer to the user. Historical request timestamp: ' + timestamp + '.'):
        raise ValueError('unrecognized controller system provenance')
    pattern = r'Current retrieval date: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?\+00:00\. '
    matches = list(re.finditer(pattern, system['content']))
    if len(matches) != 1:
        raise ValueError('one exact controller retrieval-date sentence required')
    match = matches[0]
    old = match.group()
    system['content'] = system['content'][:match.start()] + (
        'Answer as of the original question timestamp: ' + timestamp +
        '. Retrieval time is provenance only, not the answer date. ') + system['content'][match.end():]
    return result, old


def exact_chunks(page, anchors):
    body = page['content']
    spans = list(re.finditer(r'\S[\s\S]*?(?=\n[ \t]*\n|\Z)', body))
    chunks = []
    for anchor in anchors:
        matches = [m for m in spans if m.group().startswith(anchor)]
        if len(matches) != 1:
            raise ValueError('missing or ambiguous complete source passage: ' + anchor)
        match = matches[0]
        chunks.append(dict(url=page['url'], title=page.get('title', ''), text=match.group(),
            start=match.start(), end=match.end(), full_content_sha256=hashlib.sha256(body.encode()).hexdigest()))
    return chunks


def prepare():
    if ROOT.exists():
        raise ValueError('new trial root required')
    receipt = read(RECEIPT)
    for item in receipt['pins']:
        if base.file_hash(Path(item['path'])) != item['sha256']:
            raise ValueError('review evidence pin changed')
    info = read(pilot.contract.METADATA)['tokenizer_info']
    student = Tokenizer.from_file(info['tokenizer_path'])
    template = jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
    jobs = []; pins = {}; changes = []
    for prefix, plan in PLANS.items():
        job = deepcopy(next(j for j in read(plan['root'] / 'jobs.json') if j['id'].startswith(prefix)))
        key = job['id']; old = Path(job['evidence']); evidence = read(old)
        cache = Path(evidence['full_response_snapshot'])
        payload = read(cache)
        page = next(p for p in payload['data'] if p['url'] == plan['url'])
        chunks = exact_chunks(page, plan['anchors'])
        history, removed = replace_controller_date(job['messages'][:-1], job['sample']['original_timestamp'])
        history = pilot.history_with_observation(history, chunks, evidence['source_query'])
        observation = base.strict_json(history[-1]['content'])
        observation['evidence_scope'] = plan['scope']
        import json
        history[-1]['content'] = json.dumps(observation, ensure_ascii=False)
        prompt_tokens = len(student.encode(pilot.contract.training.render(template, history, base.TOOLS, True, False),
                                          add_special_tokens=False).ids)
        if prompt_tokens + previous.RESERVE > 4096:
            raise ValueError('selected evidence plus real answer allocation exceeds student window')
        target = ROOT / 'metadata/evidence' / (key + '.json')
        base.atomic(target, dict(chunks=chunks, full_response_snapshot=str(cache),
            full_response_sha256=base.file_hash(cache), parent_evidence_sha256=base.file_hash(old),
            source_query=evidence['source_query'], selection_before_generation=True,
            student_prompt_tokens=prompt_tokens, answer_reserve_tokens=previous.RESERVE,
            removed_controller_sentence=removed, original_question_timestamp=job['sample']['original_timestamp'],
            original_user_unchanged=True, scope_visible_in_learner_observation=plan['scope']))
        job.update(messages=history, pages={p['url']:p for p in observation['results']}, evidence=str(target))
        jobs.append(job)
        changes.append(dict(id=key, prompt_tokens=prompt_tokens, source_scope=plan['scope'],
            original_user_sha256=base.digest([m for m in history if m['role']=='user'])))
        for path in (old, cache, target, plan['root'] / 'jobs.json'):
            pins[str(path.resolve())] = base.file_hash(path)
    previous.seal(ROOT, jobs, [], pins, info, read(previous.ROOT / 'manifest.json'))
    config = read(ROOT / 'manifest.json')
    for path in (Path(__file__), RECEIPT):
        config['pins'][str(path.resolve())] = base.file_hash(path)
    config.update(total=3, next_batch_authorized=False, max_requests_per_endpoint=1)
    base.atomic(ROOT / 'manifest.json', config)
    base.atomic(ROOT / 'changes.json', changes)
    print(changes)


ORIGINAL_REVIEW_MESSAGES = pilot.reviewer.messages


def review_messages(payload):
    payload = deepcopy(payload)
    payload['requirements'].pop('retrieval_date', None)
    messages = ORIGINAL_REVIEW_MESSAGES(payload)
    messages[0]['content'] += (
        ' For each consequential claim check the exact supplied passage, model/entity variant, '
        'and applicability at original_timestamp. A later retrospective statement may support an earlier event '
        'but not a later event being current then. Benchmark performance does not establish reception; '
        'a proposal does not establish outcomes. Source URL membership alone is not evidence support. '
        'Partial evidence must be labelled partial, not promoted to a complete answer.')
    return messages


async def run():
    pilot.GenerationSession = previous.GenerationSession
    pilot.reviewer.messages = review_messages
    original = base.atomic
    def atomic(path, value):
        if Path(path) == ROOT / 'progress.json':
            value = dict(value, total=3)
        original(path, value)
    base.atomic = atomic
    with (ROOT / 'run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        await pilot.run(argparse.Namespace(root=ROOT, concurrency_per_server=1, timeout=600))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run'])
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    else:
        asyncio.run(run())
