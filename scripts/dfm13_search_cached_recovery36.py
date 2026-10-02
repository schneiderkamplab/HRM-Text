"""Provider-failure accounting and one cached-only recovery of failed tasks."""
import argparse
import asyncio
from collections import Counter
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3

import aiohttp
import jinja2
from tokenizers import Tokenizer

from scripts import dfm13_search_parallel86 as source

base, pilot, prior = source.base, source.pilot, source.prior
ROOT = Path('data/dfm13/search-cached-recovery36-20261001')


def failure_bucket(attempts, outcome):
    if outcome.get('error') == 'invalid action types':
        return 'generation_invalid_action'
    if any(a.get('status') == 'done' for a in attempts):
        return 'cached_evidence_selection_failure'
    errors = [a.get('error','') for a in attempts]
    if any('HTTP 402' in e for e in errors):
        return 'provider_payment_or_credit_failure_no_new_evidence'
    return 'provider_request_failure_no_new_evidence'


def prepare():
    if ROOT.exists():
        raise ValueError('new root required')
    old = source.prior.read(source.ROOT/'manifest.json')
    if source.prior.read(source.ROOT/'runtime.json')['status'] != 'terminal':
        raise ValueError('original campaign must be terminal')
    info = old['student_tokenizer_info']
    student = Tokenizer.from_file(info['tokenizer_path'])
    template = jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
    db = sqlite3.connect('file:'+str(base.CAMPAIGN/'cache.sqlite')+'?mode=ro', uri=True)
    all_attempts=[prior.read(p) for p in (source.ROOT/'retrieval').glob('*/*.json')]
    taxonomy=[]; jobs=[]; excluded=[]; pins={}
    for task in prior.read(source.ROOT/'tasks.json'):
        path=source.ROOT/'records'/task['id']/'outcome.json'
        outcome=prior.read(path)
        if outcome['status'] != 'error':
            continue
        attempts=[a for a in all_attempts if a['query']['id']==task['id']]
        taxonomy.append(dict(id=task['id'], bucket=failure_bucket(attempts,outcome),
            original_outcome=str(path), original_outcome_sha256=base.file_hash(path),
            provider_statuses=[a.get('error',a['status']) for a in attempts],
            original_error=outcome.get('error'), implies_web_evidence_absent=False))
        # Original query owner binding is kept; never borrow another task's cache.
        rows=db.execute('SELECT query,raw,provenance FROM searches WHERE owner=? AND status="done" ORDER BY rowid DESC LIMIT 3',(task['id'],)).fetchall()
        if not rows:
            excluded.append(dict(id=task['id'],reason='no completed owner-bound cache; provider failures are not evidence absence'))
            continue
        queries=[];results=[]
        for i,(query,raw,provenance) in enumerate(rows):
            cache=ROOT/'cache'/task['id']/(str(i)+'.json')
            base.atomic(cache,base.strict_json(raw))
            queries.append(dict(id=task['id'],index=i,query=query,source_asof=task['sample']['original_timestamp'],
                reason='Reuse full actual retrieved response for the original question; no claim of historical applicability.'))
            results.append(dict(status='done',cache=str(cache),cache_sha256=base.file_hash(cache),
                raw_response_sha256=hashlib.sha256(raw).hexdigest(),provenance=json.loads(provenance),cache_hit=True))
            pins[str(cache.resolve())]=base.file_hash(cache)
        recovery_task=dict(task,queries=queries)
        try:
            messages,pages,chunks=source.prepare_evidence(recovery_task,results,student,template)
            evidence=ROOT/'evidence'/(task['id']+'.json')
            base.atomic(evidence,dict(chunks=chunks,results=results,queries=queries,source_asof=task['sample']['original_timestamp'],
                parent_outcome=str(path),parent_outcome_sha256=base.file_hash(path),
                no_paid_calls=True,controller_authored_calls=True,target_policy='final answer only',original_user_unchanged=True))
            jobs.append(dict(id=task['id'],sample=task['sample'],messages=messages,pages=pages,evidence=str(evidence)))
            pins[str(evidence.resolve())]=base.file_hash(evidence)
            pins[str(path.resolve())]=base.file_hash(path)
        except ValueError as error:
            excluded.append(dict(id=task['id'],reason=str(error),cache_rows=len(rows)))
    totals=dict(db.execute('SELECT status,count(*) FROM searches GROUP BY status'));db.close()
    base.atomic(ROOT/'failure-taxonomy.json',dict(rows=taxonomy,buckets=dict(Counter(r['bucket'] for r in taxonomy)),
        original_retrieval_counts=dict(Counter(a.get('error',a['status']) for a in all_attempts)),campaign_counts=totals,
        paid_reservations=sum(totals.values()),note='402 indicates payment/credit response; body was not saved, exact account cause unverified. No retries/refunds.',
        admission_authorized=False))
    base.atomic(ROOT/'jobs.json',jobs)
    base.atomic(ROOT/'excluded.json',excluded)
    for path in (Path(__file__),Path(source.__file__),Path(base.__file__),Path(pilot.__file__),Path(prior.temporal.__file__),
        Path(pilot.contract.__file__),Path(pilot.mode.__file__),Path(pilot.bounded.__file__),Path(pilot.reviewer.__file__),
        ROOT/'jobs.json',ROOT/'failure-taxonomy.json',pilot.contract.METADATA,Path(info['tokenizer_path']),Path(info['chat_template_path'])):
        pins[str(path.resolve())]=base.file_hash(path)
    base.atomic(ROOT/'manifest.json',dict(**{k:old[k] for k in ('model','endpoints','tokenizer_dir','context_tokens','student_tokenizer_info')},
        pins=pins,total=len(jobs),paid_calls_allowed=0,provider_calls_allowed=0,concurrency_per_endpoint=32,max_attempts=1,admission_authorized=False))
    print(json.dumps(dict(queued=len(jobs),excluded=len(excluded),paid=sum(totals.values()),taxonomy=dict(Counter(r['bucket'] for r in taxonomy)))))


async def run():
    config=pilot.previous.verify(ROOT)
    os.environ.pop('JINA_API_KEY',None)
    from transformers import AutoTokenizer
    teacher=AutoTokenizer.from_pretrained(config['tokenizer_dir'],local_files_only=True)
    info=config['student_tokenizer_info']
    student=Tokenizer.from_file(info['tokenizer_path'])
    template=jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
    semaphores=[asyncio.Semaphore(32) for _ in config['endpoints']]
    base.atomic(ROOT/'runtime.json',dict(pid=os.getpid(),status='cached_only_recovery',concurrency_per_endpoint=32,paid_calls=0,provider_calls=0))
    def progress():
        rows=[prior.read(p) for p in (ROOT/'records').glob('*/outcome.json')]
        value=dict(total=config['total'],terminal=len(rows),counts=dict(Counter(r.get('verdict',r['status']) for r in rows)),paid_calls=0,admission_authorized=False)
        base.atomic(ROOT/'progress.json',value)
        return value
    async with aiohttp.ClientSession(trust_env=False,connector=aiohttp.TCPConnector(limit=256)) as session:
        async def work(job,index):
            folder=ROOT/'records'/job['id']
            if (folder/'outcome.json').exists():return
            if (folder/'started.json').exists():
                base.atomic(folder/'outcome.json',dict(status='interrupted',admission_authorized=False));progress();return
            async with semaphores[index%8]:
                base.atomic(folder/'started.json',dict(at=base.now(),endpoint=config['endpoints'][index%8]))
                try:
                    model=base.Model(source.GenerationSession(session,folder/'generation'),teacher,config,config['endpoints'][index%8],600)
                    # Explicit final-only instruction addresses null/tool-end outputs;
                    # it contains no task-specific hidden factual correction.
                    actual=source.deepcopy(job['messages'])
                    actual[0]['content']+=' Produce a nonempty final answer, not another tool call. Cite exact supporting observed URLs. If evidence is missing, identify the missing facts; do not fill them from assumptions.'
                    answer=await model.ask(actual,None,base.TOOLS,folder/'generation','answer')
                    if answer['action']!='final':raise ValueError('unexpected tool call; cached-only run')
                    candidate=dict(id=job['id'],messages=job['messages']+[dict(role='assistant',content=answer['text'])],tools=base.TOOLS,
                        target_message_indices=[len(job['messages'])],admission_authorized=False,
                        provenance=dict(sample=job['sample'],evidence=job['evidence'],evidence_sha256=base.file_hash(Path(job['evidence'])),
                            teacher_generated_final=True,generation_only_suffix_excluded=True))
                    base.atomic(folder/'candidate.json',candidate)
                    checked,_=pilot.contract.strict_row(candidate,job['sample']['prompt'])
                    rendering=pilot.contract.rendered_targets(checked,student,template,info,4096)
                    base.atomic(folder/'student-render.json',rendering)
                    if not all(r['fits_student_context'] for r in rendering):raise ValueError('student context exceeded; no truncation')
                    payload=dict(requirements=dict(original_user_prompt=job['sample']['prompt'],original_timestamp=job['sample']['original_timestamp']),answer=answer['text'],pages=job['pages'],verified_checks=[])
                    audit=base.Model(pilot.mode.ModeSession(session,'json_object',folder/'audit'),teacher,config,config['endpoints'][index%8],600)
                    raw=await audit.ask(prior.temporal.review_messages(payload),pilot.bounded.SCHEMA,None,folder/'audit','review')
                    base.atomic(folder/'raw-review.json',raw)
                    try: review=pilot.bounded.derive(raw,job['pages'],answer['text'])
                    except ValueError as error: review=dict(verdict='needs_verification',reason=str(error))
                    base.atomic(folder/'review.json',review)
                    result=dict(status='reviewed',**pilot.previous.gated_outcome(job['id'],review['verdict'],True))
                except Exception as error:
                    result=dict(status='error',error=str(error),admission_authorized=False)
                base.atomic(folder/'outcome.json',result);progress()
        await asyncio.gather(*(work(j,i) for i,j in enumerate(prior.read(ROOT/'jobs.json'))))
    base.atomic(ROOT/'finished.json',progress())
    base.atomic(ROOT/'runtime.json',dict(pid=None,previous_pid=os.getpid(),status='terminal',paid_calls=0))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','run']);args=parser.parse_args()
    if args.command=='prepare':prepare()
    else:
        with (ROOT/'run.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);asyncio.run(run())
