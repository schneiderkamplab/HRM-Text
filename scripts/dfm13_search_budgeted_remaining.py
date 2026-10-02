"""Cached-only remaining candidates and isolated one-shot truncation retries."""
import argparse
import asyncio
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import re
import sqlite3

import jinja2
from tokenizers import Tokenizer

from scripts import dfm13_search_budgeted_pilot as pilot
from scripts import dfm13_search_budgeted_batch1 as batch

base = pilot.base
read = pilot.previous.read
ROOT = Path('data/dfm13/search-budgeted-remaining48-20261001')
RETRY = Path('data/dfm13/search-budgeted-truncation-retry3-20261001')
RECEIPT = Path('docs/reports/dfm13_search_budgeted_batch1_v2_manual_assessment_20261001.json')
RESERVE = 1600
OUTPUT = 1536
RULES = ('\nGeneration-only constraints: Use only facts supported by the retained tool observations. '
         'Do not introduce factual background from these instructions or from unobserved sources. '
         'Do not claim latestness or current validity without dated evidence at the original request date. '
         'Keep distinct versions, Base and Instruct models, benchmark settings, and historical versus current claims separate. '
         'Attribute source claims rather than certifying them independently. Explicitly label creative proposals and inferences. '
         'Cite exact observed URLs supporting factual claims. State specific evidence gaps instead of inventing details. '
         'Complete the requested answer concisely within the output allocation; avoid unnecessary introductions.')


def generation_request(request):
    result = deepcopy(request)
    # Remove only the known pilot-added suffix; no learner text is altered.
    suffix = ('\nGeneration-only instruction: Answer from the selected cached passages in at most 220 words. '
        'Cite supporting pages with exact URLs. Distinguish supported facts from proposed examples. '
        'Respect the original question date. If essential facts are missing, say so specifically. '
        'No additional tool calls or old answers are available. Do not fabricate evidence.')
    system = result['messages'][0]['content']
    if not system.endswith(suffix):
        raise ValueError('unexpected controller suffix')
    result['messages'][0]['content'] = system[:-len(suffix)] + RULES
    result['max_tokens'] = OUTPUT
    result['tool_choice'] = 'none'
    return result


class GenerationSession:
    def __init__(self, session, folder):
        self.session, self.folder = session, folder

    def post(self, *args, **kwargs):
        kwargs['json'] = generation_request(kwargs['json'])
        base.atomic(self.folder / 'actual-request.json', kwargs['json'])
        return self.session.post(*args, **kwargs)


def eligible_paragraphs(payload):
    allowed = []
    for page in payload.get('data', []):
        body = page.get('content', '')
        if not isinstance(body, str) or len(body) < 150:
            continue
        if any(x in body[:700].lower() for x in ('403 forbidden', 'access denied', 'blocked by network security',
                'verify you are human', 'performing security verification', 'captcha', '404 not found')):
            continue
        allowed.append(page.get('url'))
    result = []
    for chunk in pilot.paragraphs(payload, allowed):
        text = chunk['text']
        if any(x in text.lower() for x in ('cookie', 'privacy policy', 'sign up', 'log in', 'subscribe',
                'all rights reserved', 'skip to content', 'money-back guarantee')):
            continue
        plain = re.sub(r'!?\[[^\]]*\]\([^)]*\)', '', text)
        if text.startswith('[![') or sum(c.isalpha() for c in plain) < 60 or text.count('https://') > 3:
            continue
        result.append(chunk)
    return result


def seal(root, jobs, excluded, pins, info, teacher):
    base.atomic(root / 'jobs.json', jobs)
    base.atomic(root / 'screening.json', dict(excluded=excluded, queued=len(jobs), paid_calls=0,
        selection='Cached native-query match; blocked/navigation filter; query-ranked complete paragraphs; exact student budget.',
        semantic_sufficiency_not_certified=True, admission_authorized=False))
    for path in (Path(__file__), Path(pilot.__file__), Path(batch.__file__), RECEIPT,
                 root / 'jobs.json', root / 'screening.json', pilot.contract.METADATA,
                 Path(info['tokenizer_path']), Path(info['chat_template_path']),
                 Path(pilot.contract.__file__), Path(base.__file__), Path(pilot.reviewer.__file__),
                 Path(pilot.mode.__file__), Path(pilot.bounded.__file__)):
        pins[str(path.resolve())] = base.file_hash(path)
    base.atomic(root / 'manifest.json', dict(**{k: teacher[k] for k in ('tokenizer_dir', 'context_tokens', 'model', 'endpoints')},
        pins=pins, student_tokenizer_info=info, total=len(jobs), max_attempts=1,
        generation_max_tokens=OUTPUT, answer_reserve_tokens=RESERVE, student_context=4096,
        paid_calls_allowed=0, admission_authorized=False, no_case_specific_teacher_facts=True))


def prepare():
    if ROOT.exists() or RETRY.exists():
        raise ValueError('fresh roots required')
    receipt = read(RECEIPT)
    if receipt['decision']['advance_remaining_48_bounded_candidate_generation'] is not True:
        raise ValueError('generation gate not advanced')
    for item in receipt['pins']:
        if base.file_hash(Path(item['path'])) != item['sha256']:
            raise ValueError('manual gate pin changed')
    info = read(pilot.contract.METADATA)['tokenizer_info']
    student = Tokenizer.from_file(info['tokenizer_path'])
    template = jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
    def count(history):
        return len(student.encode(pilot.contract.training.render(template, history, base.TOOLS, True, False),
                                  add_special_tokens=False).ids)
    teacher = read(batch.ROOT / 'manifest.json')
    remaining = set(read(Path('data/dfm13/search-budgeted-remaining-plan-20261001/reconciliation.json'))['remaining_ids'])
    first = read(batch.ROOT / 'jobs.json')
    remaining -= {j['id'] for j in first}
    samples = {s['id']: s for s in read(Path('data/dfm13/search-calibration-100-20261001-v9-cited/samples.json'))}
    inventory = {r['id']: r for r in read(pilot.contract.ROOT / 'inventory.json')['rows']}
    db = sqlite3.connect('file:' + str(base.CAMPAIGN / 'cache.sqlite') + '?mode=ro', uri=True)
    jobs = []; excluded = []; pins = {}
    for key in sorted(remaining):
        try:
            if key[:8] in pilot.previous.inventory.HOLDS:
                raise ValueError('existing independent hard hold; no blind regeneration')
            path = Path(inventory[key]['candidate'])
            native, _ = pilot.contract.strict_row(read(path), samples[key]['prompt'])
            chosen = None
            for query, raw in db.execute('SELECT query,raw FROM searches WHERE owner=? AND status=? ORDER BY key', (key, 'done')):
                try:
                    index = pilot.previous.native_search(native, query)
                    payload = json.loads(raw)
                    prefix = native['messages'][:index + 1]
                    chunks = pilot.select_evidence(eligible_paragraphs(payload), query + '\n' + samples[key]['prompt'],
                        prefix, count, reserve=RESERVE)
                    chosen = query, raw, payload, prefix, chunks, index
                    break
                except ValueError:
                    continue
            if chosen is None:
                raise ValueError('no usable matched evidence within student budget')
            query, raw, payload, prefix, chunks, index = chosen
            history = pilot.history_with_observation(prefix, chunks, query)
            if count(history) + RESERVE > 4096:
                raise ValueError('student prompt exceeds budget')
            cache = ROOT / 'metadata/cache' / (key + '.json')
            evidence = ROOT / 'metadata/evidence' / (key + '.json')
            base.atomic(cache, payload)
            base.atomic(evidence, dict(chunks=chunks, raw_response_sha256=hashlib.sha256(raw).hexdigest(),
                full_response_snapshot=str(cache), original_candidate=str(path), original_candidate_sha256=base.file_hash(path),
                branch_after_message_index=index, source_query=query, selection_before_generation=True,
                student_prompt_tokens=count(history), answer_reserve_tokens=RESERVE))
            jobs.append(dict(id=key, sample=samples[key], messages=history, tools=base.TOOLS,
                pages={p['url']: p for p in pilot.observation(chunks, query)['results']}, evidence=str(evidence)))
            for p in (path, cache, evidence):
                pins[str(p.resolve())] = base.file_hash(p)
        except ValueError as error:
            excluded.append(dict(id=key, reason=str(error), admission_authorized=False))
    db.close()
    seal(ROOT, jobs, excluded, pins, info, teacher)
    retries = []; retry_pins = {}
    for row in receipt['rows']:
        if row.get('assessment') != 'hard_hold_incomplete':
            continue
        job = deepcopy(next(j for j in first if j['id'] == row['id']))
        old_evidence = Path(job['evidence'])
        original = read(old_evidence)
        query = original['source_query']
        prefix = job['messages'][:-1]
        chunks = pilot.select_evidence(original['chunks'], query + '\n' + job['sample']['prompt'],
            prefix, count, reserve=RESERVE)
        job['messages'] = pilot.history_with_observation(prefix, chunks, query)
        job['pages'] = {p['url']: p for p in pilot.observation(chunks, query)['results']}
        evidence = RETRY / 'metadata/evidence' / (job['id'] + '.json')
        base.atomic(evidence, dict(**{k:v for k,v in original.items() if k not in
            ('chunks','student_prompt_tokens','answer_reserve_tokens')}, chunks=chunks,
            student_prompt_tokens=count(job['messages']), answer_reserve_tokens=RESERVE,
            parent_evidence_sha256=base.file_hash(old_evidence), new_pregeneration_selection=True))
        job['evidence'] = str(evidence)
        retries.append(job)
        for p in (old_evidence, evidence):
            retry_pins[str(p.resolve())] = base.file_hash(p)
    if len(retries) != 3:
        raise ValueError('exactly three retries expected')
    seal(RETRY, retries, [], retry_pins, info, teacher)
    base.atomic(ROOT / 'manual-holds.json', dict(prior=read(batch.ROOT / 'manual-holds.json'),
        batch1_receipt=str(RECEIPT), batch1_sha256=base.file_hash(RECEIPT), admission_authorized=False))
    print(json.dumps(dict(remaining=len(remaining), queued=len(jobs), excluded=excluded, retries=len(retries))))


async def run():
    pilot.GenerationSession = GenerationSession
    original_atomic = base.atomic
    totals = {root / 'progress.json': read(root / 'manifest.json')['total'] for root in (RETRY, ROOT)}
    def atomic_with_total(path, value):
        if Path(path) in totals:
            value = dict(value, total=totals[Path(path)])
        original_atomic(path, value)
    base.atomic = atomic_with_total
    # Sequential roots share the same eight-per-endpoint ceiling.
    for root in (RETRY, ROOT):
        with (root / 'run.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            await pilot.run(argparse.Namespace(root=root, concurrency_per_server=8, timeout=600))
            finished = read(root / 'finished.json')
            base.atomic(root / 'progress.json', dict(terminal=finished['total'], total=read(root / 'manifest.json')['total'],
                                                   counts=finished['counts'], paid_calls=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run'])
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    else:
        asyncio.run(run())
