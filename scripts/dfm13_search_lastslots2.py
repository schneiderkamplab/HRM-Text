"""Two targeted searches, durable original campaign cap, then isolated candidates."""
import argparse
import asyncio
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import jinja2
from tokenizers import Tokenizer

from scripts import dfm13_search_budgeted_remaining as previous
from scripts import dfm13_search_asof_repair3 as temporal
from scripts import dfm13_search_supplement9 as supplement

base = previous.base
pilot = previous.pilot
read = previous.read
ROOT = Path('data/dfm13/search-lastslots2-20261001')
PLANS = {
    'e5913568': dict(query='site:cisco.com "IE 1000" "data sheet" managed industrial',
        purpose='Replace neighboring-product IE1000 specifications with model-specific manufacturer evidence.',
        scope='Only model-specific claims supported by these exact passages. Model existence or an undated/current datasheet does not establish every feature or availability at the original date.'),
    'c95778af': dict(query='"боярышник" "яблоко" "малина" "многокостянка" ботаника',
        purpose='Verify hawthorn versus raspberry fruit classification and whole-fruit versus constituent-fruitlet distinction.',
        scope='Botanical classification evidence, not a keyed examination answer. Preserve distinctions between an aggregate fruit and a constituent fruitlet; do not invent an answer key.'),
}


class Budget(supplement.SupplementBudget):
    def __init__(self, root, allowed):
        if len(allowed) != 2:
            raise ValueError('exact two-query scope required')
        super().__init__(root, allowed)


def prepare():
    if ROOT.exists():
        raise ValueError('new isolated root required')
    source = previous.ROOT / 'jobs.json'
    jobs = [dict(job=j, **PLANS[j['id'][:8]]) for j in read(source) if j['id'][:8] in PLANS]
    if len(jobs) != 2:
        raise ValueError('two source tasks required')
    base.atomic(ROOT / 'planned-queries.json', jobs)
    pins = {str(p.resolve()):base.file_hash(p) for p in
            (Path(__file__), Path(supplement.__file__), Path(temporal.__file__), source, ROOT / 'planned-queries.json')}
    base.atomic(ROOT / 'authorization.json', dict(pins=pins, allowed={j['job']['id']:j['query'] for j in jobs},
        original_campaign=str(base.CAMPAIGN), campaign_paid_ceiling=100, maximum_new_queries=2,
        no_paid_retries=True, new_original_tasks=0, remaining_two_slots_unallocated=True,
        admission_authorized=False, scope='Explicit user authorization for targeted missing evidence within last four original paid slots.'))
    base.atomic(ROOT / 'date-policy.json', dict(version='original-asof-only-v1',
        original_user_immutable=True, answer_asof='original_timestamp',
        actual_retrieval_timestamp_location='metadata and raw provider receipts only; never answer-current-time cue',
        remove_only='Recognized controller Current retrieval date sentence; no source/user date deletion',
        selection='Require source/entity relevance and claim-specific applicability at the question date. A later retrospective source can support a dated past event, never make its later current facts current earlier.',
        uncertain_applicability='hold or explicitly bounded partial answer; no current/version inference from URL authority',
        factual_teacher_only_hints_forbidden=True, applies_to='New branches only; historical roots immutable'))


def relevant_payload(payload, prefix):
    pages = []
    for page in payload.get('data', []):
        body = page.get('content', '')
        if not isinstance(body, str):
            continue
        if prefix == 'e5913568':
            host = (urlsplit(page.get('url', '')).hostname or '').lower()
            if not (host == 'cisco.com' or host.endswith('.cisco.com')):
                continue
            label = (page.get('title', '') + '\n' + body[:2000]).lower()
            if not any(term in label for term in ('ie 1000', 'ie1000', 'ethernet 1000')):
                continue
        else:
            lower = body.lower()
            if not any(term in lower for term in ('боярышник', 'малина', 'многокостян')):
                continue
        pages.append(page)
    return dict(data=pages)


async def run(args):
    authorization = read(ROOT / 'authorization.json')
    for name, sha in authorization['pins'].items():
        if base.file_hash(Path(name)) != sha:
            raise ValueError('scoped input changed')
    if (ROOT / 'generation/manifest.json').exists():
        await generate()
        return
    base.atomic(ROOT / 'runtime.json', dict(pid=os.getpid(), status='waiting_for_credential',
        planned_queries=2, inference_started=False, campaign_paid_ceiling=100))
    key = supplement.load_key(args.credential_file)
    while not key:
        await asyncio.sleep(15)
        key = supplement.load_key(args.credential_file)
    os.environ['JINA_API_KEY'] = key
    info = read(pilot.contract.METADATA)['tokenizer_info']
    tokenizer = Tokenizer.from_file(info['tokenizer_path'])
    template = jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
    def count(messages):
        return len(tokenizer.encode(pilot.contract.training.render(template, messages, base.TOOLS, True, False),
                                    add_special_tokens=False).ids)
    jobs = []; excluded = []; pins = {}
    base.atomic(ROOT / 'runtime.json', dict(pid=os.getpid(), status='targeted_retrieval',
        planned_queries=2, inference_started=False, campaign_paid_ceiling=100))
    async with base.Web('jina', ROOT / 'provider-snapshots') as web:
        web.budget = Budget(base.CAMPAIGN, authorization['allowed'])
        for item in read(ROOT / 'planned-queries.json'):
            original = item['job']; key_id = original['id']; prefix = key_id[:8]
            try:
                result = await web.search(item['query'], owner=key_id)
                base.atomic(ROOT / 'retrieval' / (key_id + '.json'), result)
                row = web.budget.db.execute('SELECT raw,provenance FROM searches WHERE query=? AND status=?',
                    (item['query'], 'done')).fetchone()
                if row is None:
                    raise ValueError('full completed response absent')
                raw, provenance_json = row
                payload = base.strict_json(raw)
                first_call = next(i for i,m in enumerate(original['messages']) if m.get('tool_calls'))
                history, removed = temporal.replace_controller_date(original['messages'][:first_call],
                                                                    original['sample']['original_timestamp'])
                callid = 'controller-targeted-' + key_id[:16]
                history.append(dict(role='assistant', content='', tool_calls=[dict(id=callid,type='function',
                    function=dict(name='search', arguments=dict(query=item['query'])))]))
                chunks = pilot.select_evidence(previous.eligible_paragraphs(relevant_payload(payload, prefix)),
                    item['query'] + '\n' + original['sample']['prompt'], history, count, reserve=previous.RESERVE + 200)
                messages = pilot.history_with_observation(history, chunks, item['query'])
                observation = base.strict_json(messages[-1]['content'])
                observation['evidence_scope'] = item['scope']
                messages[-1]['content'] = json.dumps(observation, ensure_ascii=False)
                if count(messages) + previous.RESERVE > 4096:
                    raise ValueError('evidence scope plus answer reserve exceeds student window')
                cache = ROOT / 'metadata/cache' / (key_id + '.json')
                evidence = ROOT / 'metadata/evidence' / (key_id + '.json')
                base.atomic(cache, payload)
                base.atomic(evidence, dict(chunks=chunks, full_response_snapshot=str(cache),
                    raw_response_sha256=hashlib.sha256(raw).hexdigest(), provider_provenance=json.loads(provenance_json),
                    actual_query=item['query'], query_author='controller', native_call_is_model_generated=False,
                    supervised_target='new final answer only; controller call and observations masked',
                    new_branch_after_message_index=first_call-1, parent_job_sha256=base.digest(original),
                    removed_controller_date_sentence=removed, original_user_unchanged=True,
                    temporal_applicability='Requires per-claim review; no automatic assertion of historical product availability',
                    student_prompt_tokens=count(messages), answer_reserve_tokens=previous.RESERVE))
                jobs.append(dict(id=key_id,sample=original['sample'],messages=messages,tools=base.TOOLS,
                    pages={p['url']:p for p in observation['results']}, evidence=str(evidence)))
                for path in (cache,evidence,ROOT / 'retrieval' / (key_id + '.json')):
                    pins[str(path.resolve())] = base.file_hash(path)
            except Exception as error:
                excluded.append(dict(id=key_id, reason=str(error).replace(key, '[REDACTED]'), admission_authorized=False))
        paid_count = web.budget.db.execute('SELECT count(*) FROM searches').fetchone()[0]
    os.environ.pop('JINA_API_KEY', None)
    previous.seal(ROOT / 'generation', jobs, excluded, pins, info, read(previous.ROOT / 'manifest.json'))
    config = read(ROOT / 'generation/manifest.json')
    for path in (Path(__file__), Path(temporal.__file__), Path(supplement.__file__),
                 ROOT / 'authorization.json', ROOT / 'date-policy.json'):
        config['pins'][str(path.resolve())] = base.file_hash(path)
    base.atomic(ROOT / 'generation/manifest.json', config)
    base.atomic(ROOT / 'retrieval-finished.json', dict(ready=len(jobs), excluded=excluded,
        paid_reservations=paid_count, admission_authorized=False))
    await generate()


async def generate():
    config = pilot.previous.verify(ROOT / 'generation')
    pilot.GenerationSession = previous.GenerationSession
    pilot.reviewer.messages = temporal.review_messages
    original_atomic = base.atomic
    def atomic(path, value):
        if Path(path) == ROOT / 'generation/progress.json':
            value = dict(value,total=config['total'])
        original_atomic(path, value)
    base.atomic = atomic
    base.atomic(ROOT / 'runtime.json', dict(pid=os.getpid(),status='bounded_generation',
        queued=config['total'],concurrency_per_endpoint=1,paid_calls_allowed=0))
    await pilot.run(argparse.Namespace(root=ROOT / 'generation', concurrency_per_server=1, timeout=600))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare','run'])
    parser.add_argument('--credential-file', type=Path, default=Path.home()/'.config/dfm13/jina-api-key')
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    else:
        with (ROOT / 'run.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            asyncio.run(run(args))
