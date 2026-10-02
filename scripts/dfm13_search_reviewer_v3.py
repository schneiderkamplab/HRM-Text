"""Review saved Search answers only; no generation, retrieval or admission."""
import argparse
import asyncio
from collections import Counter
import fcntl
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit, quote

import aiohttp
from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_followup as prior
from scripts import dfm13_search_followup_v2 as replay
from scripts import dfm13_search_citation_rescore as citation
from scripts.dfm13_search_temporal_followup import POLICY

SCHEMA = json.loads(json.dumps(prior.AUDIT))
del SCHEMA['properties']['verdict']
SCHEMA['required'].remove('verdict')
SCHEMA['properties']['findings'] = dict(type='array', items=dict(type='object',
    properties=dict(kind=dict(type='string',enum=['incorrect_fact','unsupported_claim','temporal_mismatch','task_failure','uncertainty']),
                    explanation=dict(type='string')),required=['kind','explanation'],additionalProperties=False))
SCHEMA['required'].append('findings')
RUBRIC = replay.RUBRIC.replace('Historical relative dates refer to original_timestamp, not retrieval time. ', '') + POLICY + (
    'Review the saved answer without rewriting it. Full page content bundled in a real Jina search is valid '
    'observation evidence; a separate open_page call is not required. Do not require literal quote spans. '
    'Do not infer retrieval success from a URL alone. Navigation/error pages do not establish factual claims. '
    'Do not emit a verdict label. Emit typed findings with concrete explanations for defects or uncertainty; '
    'an empty findings array means no defect identified. The controller derives the verdict from these findings. '
    'Use uncertainty rather than inventing an error or approving unsupported details. '
    'Return concise JSON; reason at most 150 words. The source prompt date and retrieval date are distinct.')


def equivalent(url):
    parsed = urlsplit(base.public_url(url))
    def normalize(text):
        text = quote(text, safe="/%:@!$&'()*+,;=-._~[]?")
        return re.sub(r'%([0-9a-fA-F]{2})', lambda m: chr(int(m[1],16))
                      if chr(int(m[1],16)) in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~'
                      else '%'+m[1].upper(), text)
    host = parsed.netloc.lower()
    if parsed.scheme == 'https' and host.endswith(':443'):
        host = host[:-4]
    if parsed.scheme == 'http' and host.endswith(':80'):
        host = host[:-3]
    return urlunsplit((parsed.scheme.lower(), host, normalize(parsed.path or '/'), normalize(parsed.query), ''))


def validate(value, pages, answer):
    if not isinstance(value, dict) or set(value) != set(SCHEMA['required']):
        raise ValueError('review schema invalid')
    issues = value['findings']
    allowed = SCHEMA['properties']['findings']['items']['properties']['kind']['enum']
    if not isinstance(issues,list) or not all(isinstance(x,dict) and set(x)=={'kind','explanation'} and
            x['kind'] in allowed and isinstance(x['explanation'],str) and x['explanation'].strip() for x in issues):
        raise ValueError('invalid typed findings')
    aliases = {equivalent(url): url for url in pages}
    raw = {k:v for k,v in value.items() if k != 'findings'}
    raw['verdict'] = 'reject' if any(x['kind']!='uncertainty' for x in issues) else (
        'needs_verification' if issues or value['unsupported_claims'] else 'keep')
    if not isinstance(raw['supporting_urls'],list):
        raise ValueError('invalid supporting URLs')
    raw['supporting_urls'] = [aliases.get(equivalent(u),u) for u in raw['supporting_urls']]
    # Only normalize parsed URLs, never alter the answer or accept URL prefixes.
    # Citation parser below accepts aliases by enumerating observed equivalent forms.
    expanded = dict(pages)
    from markdown_it import MarkdownIt
    def visit(tokens):
        for t in tokens:
            if t.type in ('link_open','image'):
                u=t.attrGet('href' if t.type=='link_open' else 'src')
                if u and equivalent(u) in aliases:
                    expanded[u]=pages[aliases[equivalent(u)]]
            if t.children:
                visit(t.children)
    visit(MarkdownIt().parse(answer))
    for u in re.findall(r'https?://[^\s<>"`]+',answer):
        u=u.rstrip('.,;!。。，；！')
        while u.endswith((']',')')) and ((u.endswith(']') and u.count(']')>u.count('[')) or (u.endswith(')') and u.count(')')>u.count('('))):
            u=u[:-1]
        if equivalent(u) in aliases:
            expanded[u]=pages[aliases[equivalent(u)]]
    return dict(citation.rescore(raw, expanded, answer), findings=issues)


def prepare(args):
    if args.root.exists():
        raise ValueError('new root required')
    manifest=json.loads((args.source/'manifest.json').read_text())
    jobs=json.loads((args.source/'jobs.json').read_text())
    for job in jobs:
        folder=args.source/'records'/job['id']
        candidate=folder/'candidate.json'
        repair=folder/'repair.json'
        if candidate.exists():
            saved=json.loads(candidate.read_text())
            job['answer']=saved['messages'][-1]['content']
            job['answer_origin']='saved_candidate'
            pin=candidate
        elif repair.exists():
            job['answer']=json.loads(repair.read_text())['answer']
            job['answer_origin']='saved_repair_not_completed_trajectory'
            pin=repair
        else:
            job['answer']=job['candidate']['messages'][-1].get('content','')
            job['answer_origin']='prior_saved_answer_not_new_repair'
            pin=args.source/'jobs.json'
        manifest['pins'][str(pin.resolve())]=base.file_hash(pin)
    base.atomic(args.root/'jobs.json',jobs)
    for p in (Path(__file__), Path(citation.__file__), Path(__file__).with_name('dfm13_search_temporal_followup.py'),args.root/'jobs.json'):
        manifest['pins'][str(p.resolve())]=base.file_hash(p)
    manifest.update(total=len(jobs),review_only=True,created_at=base.now())
    base.atomic(args.root/'manifest.json',manifest)


async def run(args):
    manifest=prior.verify(args.root)
    os.environ.pop('JINA_API_KEY',None)
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(manifest['tokenizer_dir'],local_files_only=True)
    queue=asyncio.Queue()
    for job in json.loads((args.root/'jobs.json').read_text()):
        folder=args.root/'records'/job['id']
        if not (folder/'outcome.json').exists():
            if (folder/'started.json').exists():
                base.atomic(folder/'outcome.json',dict(status='interrupted',admission_authorized=False))
            else:
                queue.put_nowait(job)
    slots=replay.worker_slots(manifest['endpoints'],args.concurrency_per_server)
    base.atomic(args.root/'runtime.json',dict(pid=os.getpid(),workers=len(slots),concurrency_per_endpoint=args.concurrency_per_server,
        queued=queue.qsize(),paid_calls=0,generation_calls=0))
    async with aiohttp.ClientSession(trust_env=False) as session:
        async def worker(endpoint):
            model=base.Model(session,tokenizer,manifest,endpoint,args.timeout)
            while not queue.empty():
                job=queue.get_nowait(); folder=args.root/'records'/job['id']
                base.atomic(folder/'started.json',dict(endpoint=endpoint,at=base.now()))
                messages=[dict(role='system',content=RUBRIC),dict(role='user',content=json.dumps(dict(
                    prompt=job['sample'],answer=job['answer'],pages=job['pages'],retrieval_date='2026-10-01'),ensure_ascii=False))]
                try:
                    raw=await model.ask(messages,SCHEMA,None,folder,'review')
                    try:
                        review=validate(raw,job['pages'],job['answer'])
                    except ValueError as error:
                        if 'contradiction' in str(error):
                            messages.append(dict(role='user',content='Re-review your inconsistent decision independently: '+json.dumps(raw)))
                            raw=await model.ask(messages,SCHEMA,None,folder,'consistency-review')
                        try:
                            review=validate(raw,job['pages'],job['answer'])
                        except ValueError as final_error:
                            review=dict(verdict='needs_verification',reason=str(final_error),original_review=raw)
                    base.atomic(folder/'review.json',review)
                    result=dict(status='reviewed',verdict=review['verdict'],answer_origin=job['answer_origin'])
                except Exception as error:
                    result=dict(status='error',error=str(error))
                base.atomic(folder/'outcome.json',dict(**result,admission_authorized=False))
                outcomes=[json.loads(p.read_text()) for p in (args.root/'records').glob('*/outcome.json')]
                base.atomic(args.root/'progress.json',dict(terminal=len(outcomes),total=manifest['total'],
                    counts=dict(Counter(o.get('verdict',o['status']) for o in outcomes)),paid_calls=0,generation_calls=0))
        await asyncio.gather(*(worker(e) for e in slots))
    base.atomic(args.root/'finished.json',dict(at=base.now()))


def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['prepare','run'])
    p.add_argument('--source',type=Path,default=Path('data/dfm13/search-calibration-100-20261001-followup2'))
    p.add_argument('--root',type=Path,default=Path('data/dfm13/search-reviewer-v3-20261001'))
    p.add_argument('--concurrency-per-server',type=int,default=8);p.add_argument('--timeout',type=int,default=600)
    args=p.parse_args()
    if args.command=='prepare': prepare(args)
    else:
        with (args.root/'run.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);asyncio.run(run(args))


if __name__=='__main__': main()
