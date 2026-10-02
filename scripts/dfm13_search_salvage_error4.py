"""Bounded recovery of four citation errors; cached-only, one shared request."""
import argparse
import asyncio
from copy import deepcopy
import fcntl
import os
from pathlib import Path
from collections import Counter
import aiohttp
import jinja2
from tokenizers import Tokenizer
from scripts import dfm13_search_salvage32 as parent

base, pilot, prior = parent.base, parent.pilot, parent.prior
ROOT = Path('data/dfm13/search-salvage-error4-20261001')
PREFIXES = {'99fe14a8', '0cfb74ac', '31dbdb34', 'b6dacbac'}
NOTES = {
 '31dbdb34': 'Distinguish sourced metacognitive principles from an illustrative coding exercise. Cite exact observed URLs for principles. Do not assert arbitrary timing rules, effectiveness or clinical benefits as established evidence. Keep the exercise concise.',
 'b6dacbac': 'Use only the actually observed article URLs. Do not add library homepage links or assert full text access without registration unless shown in observations. Distinguish source titles from verified page contents. Omit unsupported coverage claims; identify missing sections honestly.'}


def format_fix(prefix, text, pages):
    if prefix == '99fe14a8':
        if '<br>' not in text: raise ValueError('expected exact formatting absent')
        return text.replace('<br>', ' ')
    if prefix == '0cfb74ac':
        old = 'https://liverpoolfc.com/news/alisson-becker-why-i-believe-we-have-started-season-so-well'
        new = 'https://www.liverpoolfc.com/news/alisson-becker-why-i-believe-we-have-started-season-so-well'
        if old not in text or new not in pages: raise ValueError('exact observed URL required')
        return text.replace(old, new)
    raise ValueError('no mechanical repair for semantic citation gap')


def prepare():
    if ROOT.exists(): raise ValueError('new immutable root required')
    if prior.read(parent.ROOT/'runtime.json')['status'] != 'terminal': raise ValueError('parent still running')
    jobs=[]; pins={}
    for job in prior.read(parent.ROOT/'jobs.json'):
        prefix=job['id'][:8]
        if prefix not in PREFIXES: continue
        folder=parent.ROOT/'records'/job['id']
        outcome=prior.read(folder/'outcome.json')
        if outcome['status']!='error': raise ValueError('not an error')
        candidate=prior.read(folder/'candidate.json')
        fixed=None if prefix in NOTES else format_fix(prefix,candidate['messages'][-1]['content'],job['pages'])
        jobs.append(dict(job,original_candidate=str(folder/'candidate.json'),
            original_candidate_sha256=base.file_hash(folder/'candidate.json'),fixed_answer=fixed,
            teacher_only_note=NOTES.get(prefix),original_error=outcome['error']))
        for p in (folder/'candidate.json',folder/'outcome.json'):
            pins[str(p.resolve())]=base.file_hash(p)
    if len(jobs)!=4: raise ValueError('expected four affected jobs')
    base.atomic(ROOT/'jobs.json',jobs)
    for p in (Path(__file__),Path(parent.__file__),ROOT/'jobs.json'):
        pins[str(p.resolve())]=base.file_hash(p)
    config=prior.read(parent.ROOT/'manifest.json')
    base.atomic(ROOT/'manifest.json',dict(config,pins={**config['pins'],**pins},total=4,
        max_new_generations=2,concurrency_per_endpoint=1,admission_authorized=False))


async def run():
    config=pilot.previous.verify(ROOT)
    os.environ.pop('JINA_API_KEY',None)
    base.atomic(ROOT/'runtime.json',dict(pid=os.getpid(),status='loading',concurrency=1,provider_calls=0))
    from transformers import AutoTokenizer
    teacher=AutoTokenizer.from_pretrained(config['tokenizer_dir'],local_files_only=True)
    info=config['student_tokenizer_info'];student=Tokenizer.from_file(info['tokenizer_path'])
    template=jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
    def progress():
        rows=[prior.read(p) for p in (ROOT/'records').glob('*/outcome.json')]
        value=dict(total=4,terminal=len(rows),counts=dict(Counter(r.get('verdict',r['status']) for r in rows)),provider_calls=0,admission_authorized=False)
        base.atomic(ROOT/'progress.json',value); print(value,flush=True)
    progress()
    async with aiohttp.ClientSession(trust_env=False,connector=aiohttp.TCPConnector(limit=1)) as session:
        for job in prior.read(ROOT/'jobs.json'):
            folder=ROOT/'records'/job['id']
            if (folder/'outcome.json').exists(): continue
            if (folder/'started.json').exists():
                base.atomic(folder/'outcome.json',dict(status='interrupted',admission_authorized=False));progress();continue
            base.atomic(folder/'started.json',dict(at=base.now(),endpoint=parent.ENDPOINT))
            base.atomic(ROOT/'runtime.json',dict(pid=os.getpid(),status='active',active_id=job['id'],concurrency=1,endpoint=parent.ENDPOINT,provider_calls=0))
            try:
                answer=job['fixed_answer']
                if answer is None:
                    actual=deepcopy(job['messages'])
                    actual[0]['content']+=' Return a final answer only. Preserve original as-of date. '+job['teacher_only_note']
                    model=base.Model(parent.previous.source.GenerationSession(session,folder/'generation'),teacher,config,parent.ENDPOINT,600)
                    result=await model.ask(actual,None,job['tools'],folder/'generation','answer')
                    if result['action']!='final': raise ValueError('final required')
                    answer=result['text']
                candidate=deepcopy(prior.read(Path(job['original_candidate'])))
                candidate['messages'][-1]['content']=answer
                candidate['provenance']['recovery']=dict(parent=job['original_candidate'],parent_sha256=job['original_candidate_sha256'],
                    mechanical=job['fixed_answer'] is not None,teacher_only_note=job['teacher_only_note'],one_attempt=True)
                base.atomic(folder/'candidate.json',candidate)
                checked,_=pilot.contract.strict_row(candidate,job['sample']['prompt'])
                rendered=pilot.contract.rendered_targets(checked,student,template,info,4096)
                base.atomic(folder/'student-render.json',rendered)
                if not all(r['fits_student_context'] for r in rendered):raise ValueError('student context exceeded')
                payload=dict(requirements=dict(original_user_prompt=job['sample']['prompt'],original_timestamp=job['sample']['original_timestamp']),answer=answer,pages=job['pages'],verified_checks=[])
                model=base.Model(pilot.mode.ModeSession(session,'json_object',folder/'audit'),teacher,config,parent.ENDPOINT,600)
                raw=await model.ask(prior.temporal.review_messages(payload),pilot.bounded.SCHEMA,None,folder/'audit','review')
                base.atomic(folder/'raw-review.json',raw)
                review=pilot.bounded.derive(raw,job['pages'],answer)
                base.atomic(folder/'review.json',review)
                outcome=dict(status='reviewed',**pilot.previous.gated_outcome(job['id'],review['verdict'],True))
            except Exception as error: outcome=dict(status='error',error=str(error))
            base.atomic(folder/'outcome.json',dict(outcome,admission_authorized=False,existing_holds_preserved=True))
            progress()
    base.atomic(ROOT/'runtime.json',dict(pid=None,previous_pid=os.getpid(),status='terminal',provider_calls=0))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','run']);args=parser.parse_args()
    if args.command=='prepare':prepare()
    else:
        with (ROOT/'run.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);asyncio.run(run())
