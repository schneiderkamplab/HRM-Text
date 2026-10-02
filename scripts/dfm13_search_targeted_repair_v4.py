"""Bounded cache-only trajectory repairs after saved-answer reviewer assessment."""
import argparse
import asyncio
from collections import Counter
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import aiohttp
from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_followup as old
from scripts import dfm13_search_followup_v2 as replay
from scripts import dfm13_search_reviewer_v3 as reviewer
from scripts import dfm13_search_reviewer_controls as controls
from scripts import dfm13_search_review_validation_v4 as validation
from scripts import dfm13_search_links_v4 as links

PRIORITY=('64b59e0d','12490c96','82071459','b6dacbac','032d2d0c','0cfb74ac','42c1b060','a1f76a3a','06cd049f')


def select_pages(payload, query):
    pages=replay.excerpts(payload,query,max_chunks=4)
    # Technical benchmark identifiers need local table/header context, not titles.
    technical=[t for t in re.findall(r'[A-Za-z][A-Za-z0-9_-]{3,}',query) if any(c.isdigit() for c in t)]
    technical.sort(key=lambda t: -sum(c.isdigit() for c in t)/len(t))
    for item in payload.get('data',[])[:1]:
        body=item.get('content') or '';url=item.get('url','')
        windows=[]
        for term in technical:
            for match in re.finditer(re.escape(term),body,re.I):
                start=max(0,match.start()-1800);end=min(len(body),match.end()+1400)
                if not any(abs(start-a)<1500 for a,_ in windows): windows.append((start,end))
                if len(windows)>=2: break
            if len(windows)>=2: break
        if windows:
            base.public_url(url)
            page=pages.setdefault(url,dict(url=url,title=item.get('title',''),body='',excerpts=[],
                full_content_sha256=hashlib.sha256(body.encode()).hexdigest()))
            for start,end in windows:
                page['body']+='\n[Technical context '+str(start)+':'+str(end)+']\n'+body[start:end]
                page['excerpts'].append(dict(start=start,end=end,text=body[start:end]))
    return pages


def prepare(args):
    if args.root.exists(): raise ValueError('new root required')
    source=Path('data/dfm13/search-reviewer-v3-20261001')
    previous=Path('data/dfm13/search-calibration-100-20261001-followup2')
    manifest=json.loads((source/'manifest.json').read_text())
    alljobs=json.loads((source/'jobs.json').read_text())
    db=sqlite3.connect('file:'+str(base.CAMPAIGN/'cache.sqlite')+'?mode=ro',uri=True)
    chosen=[]; excluded=[]
    def order(job):
        prefix=job['id'][:8]
        return (PRIORITY.index(prefix) if prefix in PRIORITY else len(PRIORITY),job['id'])
    for job in sorted(alljobs,key=order):
        outcome_path=source/'records'/job['id']/'outcome.json'
        outcome=json.loads(outcome_path.read_text())
        former=json.loads((previous/'records'/job['id']/'outcome.json').read_text())
        if (outcome.get('verdict')=='keep' and job['id'][:8] not in PRIORITY) or outcome['status']=='error': continue
        if former['status']=='unresolved' and not job['id'].startswith('64b59'):
            excluded.append(dict(id=job['id'],reason='known missing essential evidence; no blind repair'));continue
        if len(chosen)>=24:
            excluded.append(dict(id=job['id'],reason='bounded pass limit'));continue
        cached=db.execute('SELECT query,raw FROM searches WHERE owner=? AND status="done"',(job['id'],)).fetchone()
        if not cached: continue
        query,raw=cached;payload=json.loads(raw)
        full=select_pages(payload,query)
        job['extraction_provenance']=full
        job['pages']={u:{k:p[k] for k in ('url','title','body')} for u,p in full.items()}
        job['cache_sha256']=hashlib.sha256(raw).hexdigest()
        job['prior_review']=json.loads((source/'records'/job['id']/'review.json').read_text())
        manifest['pins'][str(outcome_path.resolve())]=base.file_hash(outcome_path)
        chosen.append(job)
    db.close()
    base.atomic(args.root/'jobs.json',chosen)
    base.atomic(args.root/'excluded.json',excluded)
    for p in (Path(__file__),Path(validation.__file__),Path(links.__file__),Path(controls.__file__),args.root/'jobs.json'):
        manifest['pins'][str(p.resolve())]=base.file_hash(p)
    manifest.update(total=len(chosen),review_only=False,paid_calls_allowed=0,max_passes=1,
        wait_for=str(Path('data/dfm13/search-review-error-retry-20261001/finished.json').resolve()),
        source=str(source.resolve()),created_at=base.now(),production_authorized=False)
    base.atomic(args.root/'manifest.json',manifest)
    print(json.dumps(dict(queued=len(chosen),excluded=len(excluded),paid_calls=0)))


async def execute(job,model,folder):
    instructions=reviewer.RUBRIC+(
        'Now repair this answer once; do not return reviewer findings. Return answer, evidence_sufficient, reason. '
        'Use only the supplied page URLs for citations, with [source](exact URL) syntax. No invented destination links. '
        'URLs inside example code are not evidence. Add a citation only where its page actually supports the claim. '
        'Do not add unsupported material to make the answer more complete. Do not mention previous answers. '
        'For historical/relative-time questions do not replace unavailable past facts with current facts. '
        'If essential facts are missing set evidence_sufficient=false. Keep prose concise (under 600 words), '
        'and do not give a proof of a mathematical minimum unless established; in particular bases 2,3,5,7 '
        'do NOT guarantee Miller-Rabin correctness for all 32-bit integers: 3215031751 is a composite counterexample. '
        'For a benchmark distinguish base and chat model, shot count and evaluation protocol explicitly.')
    repair=await model.ask([dict(role='system',content=instructions),dict(role='user',content=json.dumps(dict(
        prompt=job['sample'],previous_answer=job['answer'],pages=job['pages'],retrieval_date='2026-10-01'),ensure_ascii=False))],
        old.REPAIR,None,folder,'repair')
    base.atomic(folder/'repair.json',repair)
    if not isinstance(repair,dict) or set(repair)!=set(old.REPAIR['required']) or type(repair['evidence_sufficient']) is not bool or not all(isinstance(repair[k],str) for k in ('answer','reason')):
        raise ValueError('invalid repair schema')
    if not repair['evidence_sufficient']:
        return dict(status='unresolved',verdict='needs_verification',reason=repair['reason'])
    if not repair['answer'].strip(): raise ValueError('empty repair')
    candidate=json.loads(json.dumps(job['candidate']))
    history=candidate['messages']
    tool_index=max(i for i,m in enumerate(history) if m['role']=='tool')
    history=history[:tool_index+1]
    history[-1]['content']=json.dumps(dict(provider='jina_full_cache_replay',paid_calls=0,
        cache_sha256=job['cache_sha256'],results=list(job['pages'].values()),
        note='New CPU excerpt selection from saved real observations.'),ensure_ascii=False)
    history.append(dict(role='assistant',content=repair['answer']))
    candidate.update(messages=history,admission_authorized=False,repair_version=4,
        target_message_indices=[i for i,m in enumerate(history) if m['role']=='assistant'],
        extraction_provenance=job['extraction_provenance'])
    tokens=model.tokenizer.apply_chat_template(history,tools=base.TOOLS,tokenize=True,enable_thinking=False)
    if len(tokens)>model.manifest['context_tokens']: raise ValueError('repaired conversation exceeds context')
    candidate['teacher_rendered_tokens']=len(tokens)
    base.atomic(folder/'candidate.json',candidate)
    raw=await model.ask([dict(role='system',content=reviewer.RUBRIC),dict(role='user',content=json.dumps(dict(
        prompt=job['sample'],answer=repair['answer'],pages=job['pages'],retrieval_date='2026-10-01'),ensure_ascii=False))],
        reviewer.SCHEMA,None,folder,'review')
    try: result=validation.validate_review(raw,job['pages'],repair['answer'])
    except ValueError as error: result=dict(verdict='needs_verification',reason=str(error),original_review=raw)
    base.atomic(folder/'review.json',result)
    return dict(status='reviewed',verdict=result['verdict'])


async def run(args):
    manifest=old.verify(args.root)
    os.environ.pop('JINA_API_KEY',None)
    base.atomic(args.root/'runtime.json',dict(pid=os.getpid(),status='waiting_for_error_recovery',queued=manifest['total'],
        concurrency_per_endpoint=args.concurrency_per_server,paid_calls=0))
    while not Path(manifest['wait_for']).exists(): await asyncio.sleep(5)
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(manifest['tokenizer_dir'],local_files_only=True)
    async with aiohttp.ClientSession(trust_env=False) as session:
        async def control(i,case):
            case=dict(case)
            if case['id']=='later_document_not_fabricated':
                case['prompt']='When was this article published, and was that before its retrieval date?'
            pages={controls.URL:dict(url=controls.URL,body=case['body'])}
            answer=case['answer']+' [source]('+controls.URL+')'
            folder=args.root/'controls'/case['id']
            try:
                model=base.Model(session,tokenizer,manifest,manifest['endpoints'][i],args.timeout)
                raw=await model.ask([dict(role='system',content=reviewer.RUBRIC),dict(role='user',content=json.dumps(dict(
                    prompt=case['prompt'],answer=answer,pages=pages,retrieval_date='2026-10-01')))],reviewer.SCHEMA,None,folder,'review')
                result=validation.validate_review(raw,pages,answer)
                receipt=dict(case=case,review=result,passed=result['verdict']==case['expected'])
            except Exception as error: receipt=dict(case=case,passed=False,error=str(error))
            base.atomic(folder/'outcome.json',receipt);return receipt['passed']
        if not all(await asyncio.gather(*(control(i,c) for i,c in enumerate(controls.CASES)))):
            base.atomic(args.root/'blocked.json',dict(reason='targeted reviewer control failed; no trajectory repair dispatched'));return
        queue=asyncio.Queue()
        for job in json.loads((args.root/'jobs.json').read_text()):
            folder=args.root/'records'/job['id']
            if (folder/'outcome.json').exists(): continue
            if (folder/'started.json').exists():
                base.atomic(folder/'outcome.json',dict(status='interrupted',admission_authorized=False));continue
            queue.put_nowait(job)
        base.atomic(args.root/'runtime.json',dict(pid=os.getpid(),status='running',queued=queue.qsize(),
            concurrency_per_endpoint=args.concurrency_per_server,paid_calls=0,controls_passed=4))
        async def worker(endpoint):
            model=base.Model(session,tokenizer,manifest,endpoint,args.timeout)
            while not queue.empty():
                job=queue.get_nowait();folder=args.root/'records'/job['id']
                base.atomic(folder/'started.json',dict(endpoint=endpoint,at=base.now()))
                try: result=await execute(job,model,folder)
                except Exception as error: result=dict(status='error',error=str(error))
                base.atomic(folder/'outcome.json',dict(**result,admission_authorized=False))
                rows=[json.loads(p.read_text()) for p in (args.root/'records').glob('*/outcome.json')]
                base.atomic(args.root/'progress.json',dict(terminal=len(rows),total=manifest['total'],
                    counts=dict(Counter(r.get('verdict',r['status']) for r in rows)),paid_calls=0))
        await asyncio.gather(*(worker(e) for e in replay.worker_slots(manifest['endpoints'],args.concurrency_per_server)))
    base.atomic(args.root/'finished.json',dict(at=base.now()))


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run'])
    p.add_argument('--root',type=Path,default=Path('data/dfm13/search-targeted-repair-v4-20261001'))
    p.add_argument('--timeout',type=int,default=600);p.add_argument('--concurrency-per-server',type=int,default=8)
    args=p.parse_args()
    if args.command=='prepare':prepare(args)
    else:
        with (args.root/'run.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);asyncio.run(run(args))


if __name__=='__main__':main()
