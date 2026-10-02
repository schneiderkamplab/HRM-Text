"""One sequential cached-only salvage stream; no provider implementation."""
import argparse
import asyncio
from collections import Counter
from copy import deepcopy
import fcntl
import os
from pathlib import Path
import aiohttp
import jinja2
from tokenizers import Tokenizer
from scripts import dfm13_search_cached_recovery36 as previous

base, pilot, prior = previous.base, previous.pilot, previous.prior
ROOT = Path('data/dfm13/search-salvage32-20261001')
INVENTORY = Path('data/dfm13/search-final-inventory-20261001/inventory.json')
ENDPOINT = 'http://127.0.0.1:8810/v1/chat/completions'


def pages_from_history(messages):
    pages = {}
    def visit(value):
        if isinstance(value, dict):
            body = value.get('body', value.get('content'))
            if isinstance(value.get('url'), str) and isinstance(body, str) and body:
                url = value['url']
                page = pages.setdefault(url, dict(url=url, title=value.get('title', ''), body=''))
                page['body'] += body + '\n'
            for item in value.values(): visit(item)
        elif isinstance(value, list):
            for item in value: visit(item)
    for message in messages:
        if message['role'] == 'tool': visit(base.strict_json(message['content']))
    if not pages: raise ValueError('no actual cached page observations')
    return pages


def prepare():
    if ROOT.exists(): raise ValueError('immutable root already exists')
    inventory = prior.read(INVENTORY)
    config = prior.read(previous.ROOT/'manifest.json')
    jobs, retained = [], []
    pins = {str(INVENTORY.resolve()): base.file_hash(INVENTORY)}
    for task in inventory['tasks']:
        if task['disposition'] == 'manual_supported':
            retained.append(task)
            continue
        if task['disposition'] != 'automated_only': continue
        version = next(v for v in reversed(task['versions']) if v['automated_verdict']=='keep'
                       and v['student_fit_verified'] and v['complete_final']
                       and not v['exact_hold'] and not v['negative_same_content_reviews'])
        path = Path(version['candidate'])
        if base.file_hash(path) != version['candidate_sha256']: raise ValueError('candidate changed')
        candidate = prior.read(path)
        messages = candidate['messages'][:-1]
        jobs.append(dict(id=task['id'], messages=messages, tools=candidate['tools'],
                         sample=candidate['provenance']['sample'], pages=pages_from_history(messages),
                         parent_candidate=str(path), parent_sha256=version['candidate_sha256']))
        pins[str(path.resolve())] = version['candidate_sha256']
    if len(jobs)!=16 or len(retained)!=16: raise ValueError('unexpected inventory')
    base.atomic(ROOT/'jobs.json', jobs)
    base.atomic(ROOT/'retained-manual.json', retained)
    for path in (Path(__file__), Path(previous.__file__), Path(base.__file__), Path(pilot.__file__),
                 Path(pilot.contract.__file__), Path(pilot.bounded.__file__), Path(prior.temporal.__file__),
                 Path(previous.source.__file__), Path(pilot.mode.__file__), ROOT/'jobs.json', ROOT/'retained-manual.json'):
        pins[str(path.resolve())] = base.file_hash(path)
    base.atomic(ROOT/'manifest.json', dict(config, pins=pins, total=16, endpoints=[ENDPOINT],
        concurrency_per_endpoint=1, max_attempts=1, paid_calls_allowed=0, provider_calls_allowed=0,
        admission_authorized=False, existing_holds_preserved=True))
    print('Prepared 16 one-attempt jobs; retained 16 manual versions unchanged', flush=True)


async def run():
    config = pilot.previous.verify(ROOT)
    os.environ.pop('JINA_API_KEY', None)
    base.atomic(ROOT/'runtime.json', dict(pid=os.getpid(), status='loading_tokenizers', endpoint=ENDPOINT,
                concurrency=1, provider_calls=0))
    from transformers import AutoTokenizer
    teacher = AutoTokenizer.from_pretrained(config['tokenizer_dir'], local_files_only=True)
    info = config['student_tokenizer_info']
    student = Tokenizer.from_file(info['tokenizer_path'])
    template = jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
    def progress():
        outcomes = [prior.read(p) for p in (ROOT/'records').glob('*/outcome.json')]
        result = dict(total=16, terminal=len(outcomes), counts=dict(Counter(o.get('verdict',o['status']) for o in outcomes)),
                      retained_manual=16, provider_calls=0, admission_authorized=False)
        base.atomic(ROOT/'progress.json', result)
        print(result, flush=True)
    async with aiohttp.ClientSession(trust_env=False, connector=aiohttp.TCPConnector(limit=1)) as session:
        for job in prior.read(ROOT/'jobs.json'):
            folder = ROOT/'records'/job['id']
            if (folder/'outcome.json').exists(): continue
            if (folder/'started.json').exists():
                base.atomic(folder/'outcome.json',dict(status='interrupted',admission_authorized=False)); progress(); continue
            base.atomic(folder/'started.json', dict(at=base.now(), endpoint=ENDPOINT))
            base.atomic(ROOT/'runtime.json', dict(pid=os.getpid(), status='active', active_id=job['id'], endpoint=ENDPOINT, concurrency=1, provider_calls=0))
            try:
                actual = deepcopy(job['messages'])
                actual[0]['content'] += (' Return a concise nonempty final answer using only the visible observations. '
                    'Preserve the original requested date, not the retrieval date. Cite exact observed URLs for supported claims. '
                    'Retain qualifications and exceptions; do not generalize partial clauses. State missing evidence explicitly. '
                    'Do not introduce facts from these instructions or call tools.')
                model = base.Model(previous.source.GenerationSession(session,folder/'generation'), teacher, config, ENDPOINT, 600)
                answer = await model.ask(actual, None, job['tools'], folder/'generation', 'answer')
                if answer['action'] != 'final': raise ValueError('cached-only final required')
                candidate = dict(id=job['id'], messages=job['messages']+[dict(role='assistant',content=answer['text'])],
                    tools=job['tools'],target_message_indices=[len(job['messages'])],admission_authorized=False,
                    provenance=dict(sample=job['sample'],parent_candidate=job['parent_candidate'],parent_sha256=job['parent_sha256'],
                                    observations_unchanged=True,teacher_generated_final=True,existing_holds_preserved=True))
                base.atomic(folder/'candidate.json',candidate)
                checked,_ = pilot.contract.strict_row(candidate,job['sample']['prompt'])
                rendered = pilot.contract.rendered_targets(checked,student,template,info,4096)
                base.atomic(folder/'student-render.json',rendered)
                if not all(r['fits_student_context'] for r in rendered): raise ValueError('student context exceeded')
                payload = dict(requirements=dict(original_user_prompt=job['sample']['prompt'],original_timestamp=job['sample']['original_timestamp']),
                               answer=answer['text'],pages=job['pages'],verified_checks=[])
                audit = base.Model(pilot.mode.ModeSession(session,'json_object',folder/'audit'),teacher,config,ENDPOINT,600)
                raw = await audit.ask(prior.temporal.review_messages(payload),pilot.bounded.SCHEMA,None,folder/'audit','review')
                base.atomic(folder/'raw-review.json',raw)
                review = pilot.bounded.derive(raw,job['pages'],answer['text'])
                base.atomic(folder/'review.json',review)
                result = dict(status='reviewed',**pilot.previous.gated_outcome(job['id'],review['verdict'],True))
            except Exception as error:
                result = dict(status='error',error=str(error))
            base.atomic(folder/'outcome.json',dict(result,admission_authorized=False,existing_holds_preserved=True,max_attempts=1))
            progress()
    base.atomic(ROOT/'runtime.json',dict(pid=None,previous_pid=os.getpid(),status='terminal',provider_calls=0))


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','run']);args=parser.parse_args()
    if args.command=='prepare': prepare()
    else:
        with (ROOT/'run.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            asyncio.run(run())
