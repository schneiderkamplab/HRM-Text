"""Eight new native trajectories with evidence budgeted before generation."""
import argparse
import asyncio
from collections import Counter
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3

import aiohttp
import jinja2
from sklearn.feature_extraction.text import TfidfVectorizer
from tokenizers import Tokenizer

from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_cached_repairs as previous
from scripts import dfm13_search_training_contract as contract
from scripts import dfm13_search_critic_free_control as reviewer
from scripts import dfm13_search_json_mode_probe as mode
from scripts import dfm13_search_adjudication_retry as bounded

ROOT = Path('data/dfm13/search-budgeted-trajectory-pilot8-20261001')
PLANS = {
    '42e19429': (['https://it.wikipedia.org/wiki/Sergio_Mattarella', 'https://legrandcontinent.eu/it/2023/10/09/3167-giorni-al-quirinale-mattarella-diventa-il-presidente-della-repubblica-italiana-ad-aver-ricoperto-piu-a-lungo-la-carica/'], []),
    'bfd8c382': (['https://www.fec.gov/resources/cms-content/documents/2020presgeresults.pdf', 'https://www.presidency.ucsb.edu/statistics/elections/2020'], []),
    'efa6c961': (['https://en.wikipedia.org/wiki/Baseball_(ball)', 'https://www.childrensmuseum.org/blog/why-does-baseball-have-red-stitching'], []),
    '74f0b1aa': (['https://www.japan-guide.com/e/e5903.html', 'https://visitgifu.com/see-do/takayama-historical-district/'], []),
    '020d55a2': (['https://lib.pravmir.ru/library/readbook/1118', 'https://spzh.eu/ru/news/36825-prepodobnyy-paisiy-velichkovskiy-molitva-i-post-otgonyayut-grekhovnye-pomyshleniya'], []),
    '64b59e0d': (['https://arxiv.org/pdf/2412.19437'], ['In Table 3, we compare the base model', 'Math GSM8K (EM) 8-shot']),
    '0bdd931b': (['https://portal.once.es/empleado/publicaciones/asi-somos/asi-somos-1/asi-somos-319-1/juego-social/la-evolucion-de-las-baterias-en-los-dispositivos-moviles-de-los-comienzos-a-la-actualidad', 'https://www.elcomercio.com/tecnologia/evolucion-baterias-telefonos-celulares/'], []),
    '31dbdb34': (['https://ru.wikipedia.org/wiki/%D0%9C%D0%B5%D1%82%D0%B0%D0%BA%D0%BE%D0%B3%D0%BD%D0%B8%D1%82%D0%B8%D0%B2%D0%BD%D1%8B%D0%B5_%D0%BF%D1%80%D0%BE%D1%86%D0%B5%D1%81%D1%81%D1%8B', 'https://4brain.ru/blog/kak-razvivat-sposobnost-myslit-o-svoem-myshlenii/'], []),
}
STUDENT_LIMIT = 4096
ANSWER_RESERVE = 896


def paragraphs(payload, allowed):
    result = []
    for page in payload.get('data', []):
        if page.get('url') not in allowed or not isinstance(page.get('content'), str):
            continue
        body = page['content']
        for match in re.finditer(r'\S[\s\S]*?(?=\n[ \t]*\n|\Z)', body):
            text = match.group()
            if not 35 <= len(text) <= 4000:
                continue
            if text.count('https://') > 8 or any(x in text.lower() for x in
                    ('access denied', 'blocked by network security', 'verify you are human', 'accept all cookies')):
                continue
            result.append(dict(url=page['url'], title=page.get('title', ''), start=match.start(), end=match.end(),
                text=text, full_content_sha256=hashlib.sha256(body.encode()).hexdigest()))
    return result


def observation(chunks, query):
    pages = {}
    for chunk in sorted(chunks, key=lambda c: (c['url'], c['start'])):
        page = pages.setdefault(chunk['url'], dict(url=chunk['url'], title=chunk['title'], body=''))
        page['body'] += ('\n\n' if page['body'] else '') + chunk['text']
    return dict(provider='jina_cached_extractive_summary', query=query,
        note='Controller selected complete passages from a previously retrieved response; omissions between passages. No new retrieval or invented facts.',
        results=list(pages.values()))


def history_with_observation(prefix, chunks, query):
    history = deepcopy(prefix)
    history.append(dict(role='tool', name='search', tool_call_id=prefix[-1]['tool_calls'][0]['id'],
                        content=json.dumps(observation(chunks, query), ensure_ascii=False)))
    return history


def select_evidence(chunks, query, prefix, count_prompt, required=(), limit=STUDENT_LIMIT, reserve=ANSWER_RESERVE):
    if not chunks:
        raise ValueError('no complete relevant cached paragraphs')
    matrix = TfidfVectorizer(analyzer='char', ngram_range=(3, 5), max_features=30000).fit_transform(
        [query] + [c['title'] + '\n' + c['text'] for c in chunks])
    scores = (matrix[1:] @ matrix[0].T).toarray().ravel()
    selected = []
    for anchor in required:
        matches = [c for c in chunks if anchor in c['text']]
        if len(matches) != 1:
            raise ValueError('required table context absent or ambiguous')
        if matches[0] not in selected:
            selected.append(matches[0])
    if count_prompt(history_with_observation(prefix, selected, query)) + reserve > limit:
        raise ValueError('required evidence does not fit; no truncation')
    for index in sorted(range(len(chunks)), key=lambda i: (-scores[i], chunks[i]['url'], chunks[i]['start'])):
        if scores[index] <= 0 or chunks[index] in selected:
            continue
        trial = selected + [chunks[index]]
        if count_prompt(history_with_observation(prefix, trial, query)) + reserve <= limit:
            selected = trial
        if len(selected) >= 10:
            break
    if not selected:
        raise ValueError('no supported evidence fits the pre-generation budget')
    return selected


def prepare(root):
    if root.exists():
        raise ValueError('new pilot root required')
    inventory = previous.read(contract.ROOT / 'inventory.json')
    samples = {s['id']: s for s in previous.read(Path('data/dfm13/search-calibration-100-20261001-v9-cited/samples.json'))}
    info = previous.read(contract.METADATA)['tokenizer_info']
    student = Tokenizer.from_file(info['tokenizer_path'])
    template = jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
    def count(history):
        rendered = contract.training.render(template, history, base.TOOLS, True, False)
        return len(student.encode(rendered, add_special_tokens=False).ids)
    db = sqlite3.connect('file:' + str(base.CAMPAIGN / 'cache.sqlite') + '?mode=ro', uri=True)
    jobs = []; pins = {}
    for row in inventory['rows']:
        if row['id'][:8] not in PLANS:
            continue
        candidate_path = Path(row['candidate']); candidate = previous.read(candidate_path)
        native, _ = contract.strict_row(candidate, samples[row['id']]['prompt'])
        allowed, required = PLANS[row['id'][:8]]
        found = None
        for query, raw in db.execute('SELECT query,raw FROM searches WHERE owner=? AND status=?', (row['id'], 'done')):
            try:
                index = previous.native_search(native, query)
                found = query, raw, index
                break
            except ValueError:
                pass
        if found is None:
            raise ValueError('no original real search call/cache match')
        query, raw, index = found
        prefix = native['messages'][:index + 1]
        payload = json.loads(raw)
        chunks = select_evidence(paragraphs(payload, allowed), query + '\n' + samples[row['id']]['prompt'],
                                 prefix, count, required)
        # Ranking uses prompt+query, but the delivered observation keeps the actual original query.
        history = history_with_observation(prefix, chunks, query)
        if count(history) + ANSWER_RESERVE > STUDENT_LIMIT:
            raise ValueError('final prompt budget exceeded')
        cache_path = root / 'metadata' / 'cache' / (row['id'] + '.json')
        base.atomic(cache_path, payload)
        evidence_path = root / 'metadata' / 'evidence' / (row['id'] + '.json')
        base.atomic(evidence_path, dict(chunks=chunks, raw_response_sha256=hashlib.sha256(raw).hexdigest(),
            full_response_snapshot=str(cache_path), original_candidate=str(candidate_path),
            original_candidate_sha256=base.file_hash(candidate_path), branch_after_message_index=index,
            controller_selection=True, selection_before_generation=True, source_query=query,
            student_prompt_tokens=count(history), answer_reserve_tokens=ANSWER_RESERVE,
            student_context=STUDENT_LIMIT, no_posthoc_truncation=True))
        jobs.append(dict(id=row['id'], sample=samples[row['id']], messages=history,
            tools=base.TOOLS, pages={p['url']: p for p in observation(chunks, query)['results']},
            evidence=str(evidence_path), student_prompt_tokens=count(history)))
        for p in (candidate_path, cache_path, evidence_path):
            pins[str(p.resolve())] = base.file_hash(p)
    paid = dict(db.execute('SELECT status,count(*) FROM searches GROUP BY status')); db.close()
    if len(jobs) != 8:
        raise ValueError('exactly eight bounded jobs required')
    base.atomic(root / 'jobs.json', jobs)
    for p in (Path(__file__), Path(base.__file__), Path(contract.__file__), Path(reviewer.__file__),
              Path(mode.__file__), Path(bounded.__file__), root / 'jobs.json', contract.METADATA,
              Path(info['tokenizer_path']), Path(info['chat_template_path'])):
        pins[str(p.resolve())] = base.file_hash(p)
    teacher = previous.read(previous.ROOT / 'manifest.json')
    base.atomic(root / 'manifest.json', dict(**{k: teacher[k] for k in ('tokenizer_dir','context_tokens','model','endpoints')},
        student_tokenizer_info=info, pins=pins, total=8, paid_snapshot=paid, paid_calls_allowed=0,
        student_context=4096, generation_max_tokens=512, answer_reserve_tokens=ANSWER_RESERVE,
        target_policy='new final answer only; native inherited search and controller observation masked',
        max_attempts=1, admission_authorized=False))
    print(json.dumps(dict(queued=8, student_prompt_tokens=[j['student_prompt_tokens'] for j in jobs], paid=sum(paid.values()))))


class GenerationSession:
    def __init__(self, session, folder):
        self.session, self.folder = session, folder

    def post(self, *args, **kwargs):
        request = deepcopy(kwargs['json'])
        request['max_tokens'] = 512
        request['tool_choice'] = 'none'
        kwargs['json'] = request
        base.atomic(self.folder / 'actual-request.json', request)
        return self.session.post(*args, **kwargs)


async def run(args):
    root = args.root; manifest = previous.verify(root)
    if not 1 <= args.concurrency_per_server <= 8:
        raise ValueError('maximum eight per existing endpoint')
    os.environ.pop('JINA_API_KEY', None)
    from transformers import AutoTokenizer
    teacher = AutoTokenizer.from_pretrained(manifest['tokenizer_dir'], local_files_only=True)
    info = manifest['student_tokenizer_info']
    student = Tokenizer.from_file(info['tokenizer_path'])
    template = jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
    queue = asyncio.Queue()
    for job in previous.read(root / 'jobs.json'):
        folder = root / 'records' / job['id']
        if (folder / 'outcome.json').exists():
            continue
        if (folder / 'started.json').exists():
            base.atomic(folder / 'outcome.json', dict(status='interrupted', admission_authorized=False))
        else:
            queue.put_nowait(job)
    base.atomic(root / 'runtime.json', dict(pid=os.getpid(), queued=queue.qsize(),
        concurrency_per_endpoint=args.concurrency_per_server, paid_calls=0))
    async with aiohttp.ClientSession(trust_env=False) as session:
        async def worker(endpoint):
            while not queue.empty():
                job = queue.get_nowait(); folder = root / 'records' / job['id']
                base.atomic(folder / 'started.json', dict(endpoint=endpoint, at=base.now()))
                try:
                    actual = deepcopy(job['messages'])
                    if actual[0]['role'] != 'system':
                        raise ValueError('expected recorded system turn')
                    actual[0]['content'] += ('\nGeneration-only instruction: Answer from the selected cached passages in at most 220 words. '
                        'Cite supporting pages with exact URLs. Distinguish supported facts from proposed examples. '
                        'Respect the original question date. If essential facts are missing, say so specifically. '
                        'No additional tool calls or old answers are available. Do not fabricate evidence.')
                    model = base.Model(GenerationSession(session, folder / 'generation'), teacher, manifest, endpoint, args.timeout)
                    answer = await model.ask(actual, None, base.TOOLS, folder / 'generation', 'answer')
                    if answer['action'] != 'final':
                        raise ValueError('unexpected native call; no additional retrieval allowed')
                    candidate = dict(id=job['id'], messages=job['messages'] + [dict(role='assistant', content=answer['text'])],
                        tools=base.TOOLS, target_message_indices=[len(job['messages'])], admission_authorized=False,
                        provenance=dict(sample=job['sample'], evidence=job['evidence'], evidence_sha256=base.file_hash(Path(job['evidence'])),
                            teacher_generated_final=True, selection_before_generation=True, generation_suffix_excluded=True))
                    checked, _ = contract.strict_row(candidate, job['sample']['prompt'])
                    rendering = contract.rendered_targets(checked, student, template, info, 4096)
                    base.atomic(folder / 'candidate.json', candidate)
                    base.atomic(folder / 'student-render.json', rendering)
                    if not all(r['fits_student_context'] for r in rendering):
                        raise ValueError('generated final exceeds predeclared student budget; retained, not truncated')
                    payload = dict(requirements=dict(original_user_prompt=job['sample']['prompt'],
                        original_timestamp=job['sample']['original_timestamp'], retrieval_date='2026-10-01'),
                        answer=answer['text'], pages=job['pages'], verified_checks=[])
                    audit = base.Model(mode.ModeSession(session, 'json_object', folder / 'audit'), teacher, manifest, endpoint, args.timeout)
                    raw = await audit.ask(reviewer.messages(payload), bounded.SCHEMA, None, folder / 'audit', 'review')
                    base.atomic(folder / 'raw-review.json', raw)
                    try:
                        result = bounded.derive(raw, job['pages'], answer['text'])
                    except ValueError as error:
                        result = dict(verdict='needs_verification', reason=str(error))
                    base.atomic(folder / 'review.json', result)
                    outcome = dict(status='reviewed', **previous.gated_outcome(job['id'], result['verdict'], True))
                except Exception as error:
                    outcome = dict(status='error', error=str(error), admission_authorized=False)
                base.atomic(folder / 'outcome.json', outcome)
                rows = [previous.read(p) for p in (root / 'records').glob('*/outcome.json')]
                base.atomic(root / 'progress.json', dict(terminal=len(rows), total=8,
                    counts=dict(Counter(r.get('verdict', r['status']) for r in rows)), paid_calls=0))
        await asyncio.gather(*(worker(e) for _ in range(args.concurrency_per_server) for e in manifest['endpoints']))
    rows = [previous.read(p) for p in (root / 'records').glob('*/outcome.json')]
    base.atomic(root / 'finished.json', dict(total=len(rows), counts=dict(Counter(r.get('verdict',r['status']) for r in rows)),
                                           paid_calls=0, admission_authorized=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run'])
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--concurrency-per-server', type=int, default=8)
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.root)
    else:
        with (args.root / 'run.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            asyncio.run(run(args))
