"""Bounded26B source-grounded QA/P3 re-audit; never changes source holds."""
import argparse
import asyncio
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import signal
import sqlite3
import time

import aiohttp
from jsonschema import Draft202012Validator

from .io import digest, file_hash, load, lock, write_json
from . import wave_compact_review as compact
from .multilingual_calibration_v6 import raw_query, strict_json, RawResponseWriter
from .generation_constraints import DEFAULT_TOKENIZER
from .wave_synthetic_runtime import Budget, endpoint_limit

QA = Path('data/dfm13/baltic/qa31-article-full-consumer-v3')
P3 = Path('data/dfm13/latvian-p3-content-alignment-20261003-v1/fused-review-v2')
ASSESSMENT = Path('data/dfm13/latvian-p3-independent20-20261003/assessment.json')
QA_REPORT = Path('docs/reports/baltic-qa31-article20-review-20261003/report.md')
COUNTS = {'qa': 118866, 'p3': 7680}
POLICY = compact.PROMPT + '''
This is source-grounded salvage of held data, NOT general knowledge answering.
Review ALL assistant turns, not merely the supervised final target. Sources and
English answer keys are fallible. No prior assistant answer proves another.
QA: establish entity identity, scope and dates before using a retrieved article.
Candidate articles are NOT verified original generation sources. An unrelated
hit or no hit cannot substantiate a claim. Reject unresolvable evidence for this
salvage (not a claim that the answer is false). Preserve uncertainty and reject
unsafe advice or material unsupported history even when the final answer is right.
P3: match one English question by CONTENT in BOTH directions: all premises,
options, negation, entities and requested output must survive translation and
repair. Ignore IDs/order for matching. Check the full current conversation AND
original translated source. A correct answer does not cure a changed question.
Answer keys are not infallible; reject conflicting or unresolvable matches.
Do not demand stylistic perfection, native certification or identical wording.
Keep requires task fidelity, correct answer and sufficient relevant supplied
evidence. reference_id must name a supplied article/question supporting the
decision; use empty string if none. source_quote is an exact short substring
of that reference's text/question; candidate_quote is an exact short substring
of the current conversation. These quotes locate evidence, not a substitute for
checking every claim. Rejects may leave these three strings empty.
Return verdict, issues, reason, reference_id, source_quote, candidate_quote only.
Use a concise English reason, no repair or deliberation. No blanket clearance.
'''


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)


def schema():
    value = compact.schema()
    for key in ('reference_id', 'source_quote', 'candidate_quote'):
        value['properties'][key] = dict(type='string', maxLength=500)
        value['required'].append(key)
    return value


def qa_record(packet):
    candidate = packet['candidate']
    if digest(candidate) != packet['candidate_sha256']:
        raise ValueError('QA candidate drift')
    refs = []
    for article in packet['candidate_articles']:
        if hashlib.sha256(article['text'].encode()).hexdigest() != article['text_sha256']:
            raise ValueError('QA article drift')
        refs.append({k: article[k] for k in ('source_document_id','title','text','snapshot','url')})
    return dict(kind='qa', language=candidate['language'], messages=candidate['messages'],
        tools=candidate.get('tools', []), references=refs,
        exact_generation_source_verified=False)


def p3_record(record):
    return dict(kind='p3', language='lv', messages=record['messages'],
        translated_source={k: record['translated_source'][k] for k in ('question','answer')},
        references=[{k: c[k] for k in ('candidate_id','config','question','source_answers')}
                    for c in record['english_candidates']])


def validate(value, record):
    Draft202012Validator(schema()).validate(value)
    compact.validate({k: value[k] for k in ('verdict','issues','reason')})
    if value['verdict'] != 'keep' and not value['issues']:
        raise ValueError('Nonkeep requires named issue')
    if value['verdict'] == 'keep':
        key = 'source_document_id' if record['kind'] == 'qa' else 'candidate_id'
        refs = [r for r in record['references'] if r[key] == value['reference_id']]
        if len(refs) != 1:
            raise ValueError('Keep requires exact supplied reference')
        source = refs[0]['text' if record['kind'] == 'qa' else 'question']
        if not value['source_quote'].strip() or value['source_quote'] not in source:
            raise ValueError('Nonliteral source evidence')
        if not value['candidate_quote'].strip() or not any(
                value['candidate_quote'] in m.get('content', '') for m in record['messages']):
            raise ValueError('Nonliteral candidate evidence')
    return value


def request(record):
    return dict(model=compact.MODEL, temperature=0, max_tokens=768,
        chat_template_kwargs={'enable_thinking': False},
        messages=[dict(role='system', content=POLICY),
                  dict(role='user', content=json.dumps(record, ensure_ascii=False))],
        response_format=dict(type='json_schema', json_schema=dict(name='source_review',
            strict=True, schema=schema())))


def controls():
    # Previously inspected original conversations, not old model verdicts.
    positive = ['00015f48', '3fbe108b', '46917e39', 'c17a6d14', 'fff21bda']
    negative = ['02879ee7', '478ae939', '31b527af', '353e5619', 'ffff781d', '8075043d', '82203b7b']
    ids = load(QA/'manifest.json')['calibration_diagnostic_ids']
    result = {'qa-'+k: next(v for prefixes,v in ((positive,True),(negative,False))
                            if any(k.startswith(p) for p in prefixes))
              for k in ids if any(k.startswith(p) for p in positive+negative)}
    for row in load(ASSESSMENT)['rows']:
        if row['decision'].startswith('hold_'):
            result['p3-'+row['id']] = False
        elif row['decision'] == 'no_hard_hold':
            result['p3-'+row['id']] = True
    return result


def prepare(root):
    root.mkdir(parents=True, exist_ok=False)
    qmanifest = load(QA/'manifest.json'); pm = load(P3/'manifest.json')
    inputs = {str((QA/'catalog.sqlite').resolve()):
              qmanifest['pins'][str((QA/'catalog.sqlite').resolve())],
              str((P3/'requests.jsonl').resolve()): pm['files']['requests.jsonl']}
    for path, sha in inputs.items():
        if file_hash(path) != sha:
            raise ValueError('Source packet seal mismatch: '+path)
    pins = dict(inputs)
    for p in (QA/'manifest.json', P3/'manifest.json', ASSESSMENT, QA_REPORT,
              Path(__file__), Path(compact.__file__), Path('dfm12/io.py'),
              Path('dfm12/multilingual_calibration_v6.py'),
              Path('dfm12/multilingual_diagnose.py'), Path('dfm12/wave_synthetic_runtime.py')):
        pins[str(p.resolve())] = file_hash(p)
    for name in ('tokenizer.json','tokenizer_config.json','chat_template.jinja'):
        p = Path(DEFAULT_TOKENIZER)/name; pins[str(p.resolve())] = file_hash(p)
    labels = controls(); groups = {'qa': [], 'p3': []}
    with closing(sqlite3.connect(root/'catalog.sqlite')) as dst:
        dst.execute('CREATE TABLE items(id TEXT PRIMARY KEY,kind TEXT,source_id TEXT,record TEXT,binding TEXT)')
        with closing(readonly(QA/'catalog.sqlite')) as src:
            for key, in src.execute('SELECT id FROM catalog ORDER BY id'):
                groups['qa'].append('qa-'+key)
                dst.execute('INSERT INTO items VALUES(?,?,?,?,?)', ('qa-'+key,'qa',key,None,None))
        with (P3/'requests.jsonl').open() as handle:
            for line in handle:
                r = json.loads(line)['record']; key = 'p3-'+r['id']; groups['p3'].append(key)
                dst.execute('INSERT INTO items VALUES(?,?,?,?,?)', (key,'p3',r['id'],
                    json.dumps(p3_record(r),ensure_ascii=False),json.dumps(r,ensure_ascii=False)))
        dst.commit()
    if {k:len(v) for k,v in groups.items()} != COUNTS or not set(labels).issubset(set(sum(groups.values(), []))):
        raise ValueError('Source/control population mismatch')
    sample = {kind:sorted((k for k in keys if k not in labels),
                         key=lambda k:digest(['held-source-sample-20261004',k]))[:10]
              for kind,keys in groups.items()}
    pins[str((root/'catalog.sqlite').resolve())] = file_hash(root/'catalog.sqlite')
    manifest = dict(counts=COUNTS, pins=pins, controls=labels, sample=sample,
        model=compact.MODEL, tokenizer=str(DEFAULT_TOKENIZER), per_server=4,
        max_attempts=1, context=32768, no_truncation=True, all_turns=True,
        admission_authorized=False, source_holds_preserved=True,
        gate='zero false keeps; >=80% positive keeps; no invalid controls; sample inspection',
        scope='Known exposed controls plus deterministic sample, not fresh heldout certification')
    write_json(root/'manifest.json',manifest)
    write_json(root/'seal.json',dict(manifest_sha256=file_hash(root/'manifest.json')))
    return manifest


def verify(root, full=True):
    manifest = load(root/'manifest.json')
    if file_hash(root/'manifest.json') != load(root/'seal.json')['manifest_sha256']:
        raise ValueError('Manifest drift')
    for path, sha in manifest['pins'].items():
        if (full or Path(path).suffix == '.py') and file_hash(path) != sha:
            raise ValueError('Input drift: '+path)
    return manifest


def fetch(root, key):
    with closing(readonly(root/'catalog.sqlite')) as db:
        _, kind, source_id, raw, binding = db.execute('SELECT * FROM items WHERE id=?',(key,)).fetchone()
    if kind == 'p3':
        return json.loads(raw), dict(source_record_sha256=digest(json.loads(binding)), source_id=source_id)
    with closing(readonly(QA/'catalog.sqlite')) as db:
        packet = json.loads(db.execute('SELECT packet FROM catalog WHERE id=?',(source_id,)).fetchone()[0])
    return qa_record(packet), dict(candidate_sha256=packet['candidate_sha256'],
        packet_sha256=digest(packet), binding=packet['binding'],
        articles=[{k:a[k] for k in ('source_document_id','text_sha256','source_record_sha256')}
                  for a in packet['candidate_articles']])


def gate(labels, outcomes):
    false_keeps=[]; invalid=[]; positives=0; kept=0
    for key, expected in labels.items():
        row=outcomes.get(key,{})
        if row.get('status') != 'valid': invalid.append(key)
        is_keep=row.get('decision',{}).get('verdict')=='keep'
        if not expected and is_keep: false_keeps.append(key)
        if expected: positives+=1; kept+=int(is_keep)
    return dict(passed=bool(labels) and not false_keeps and not invalid and kept>=0.8*positives,
        false_keeps=false_keeps,invalid=invalid,positive_keeps=kept,positives=positives)


async def batch(root, keys, session, budget, writer, stop):
    queue=asyncio.Queue()
    for key in keys: queue.put_nowait(key)
    async def worker(endpoint):
        while not stop.is_set():
            try: key=queue.get_nowait()
            except asyncio.QueueEmpty: return
            path=root/'outcomes'/f'{key}.json'
            if path.exists(): continue
            outcome=dict(id=key,admission_authorized=False,source_holds_preserved=True)
            try:
                record,binding=await asyncio.to_thread(fetch,root,key)
                payload=request(record)
                measurement=budget.measure(payload,32768)
                if not record['references']:
                    outcome.update(status='valid',decision=dict(verdict='reject',issues=['unsupported'],
                        reason='No supplied source reference; unresolved, not asserted false.',
                        reference_id='',source_quote='',candidate_quote=''),binding=binding)
                else:
                    rp=root/'requests'/f'{key}.json'
                    if rp.exists():
                        raise ValueError('Prior request without outcome; unknown completion, no automatic retry')
                    write_json(rp,dict(request=payload,binding=binding,budget=measurement))
                    raw=await raw_query(session,endpoint,payload,writer,dict(id=key,**measurement))
                    outcome['raw']=raw
                    if raw['finish_reason']!='stop': raise ValueError('Incomplete output')
                    decision=validate(strict_json(raw['content']),record)
                    outcome.update(status='valid',decision=decision,binding=binding,request_sha256=file_hash(rp))
            except Exception as exc:
                outcome.update(status='invalid',error=repr(exc))
            write_json(path,outcome)
    await asyncio.gather(*(worker(f'http://127.0.0.1:{p}/v1') for p in range(8800,8808) for _ in range(4)))


async def run(root):
    manifest=verify(root); budget=Budget(str(DEFAULT_TOKENIZER)); stop=asyncio.Event()
    for sig in (signal.SIGTERM,signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig,stop.set)
    writer=RawResponseWriter(root/'raw')
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),
            connector=aiohttp.TCPConnector(limit=32,limit_per_host=4)) as session:
        health=[]
        for p in range(8800,8808):
            async with session.get(f'http://127.0.0.1:{p}/v1/models') as response:
                response.raise_for_status(); document=await response.json(); endpoint_limit(document)
                matches=[m for m in document['data'] if m['id']==compact.MODEL]
                if Path(matches[0].get('root','')).resolve()!=Path(DEFAULT_TOKENIZER).resolve():
                    raise ValueError('Wrong26B snapshot')
                health.append(document)
        write_json(root/'health.json',dict(endpoints=health,time=time.time()))
        diagnostic=list(manifest['controls'])+sum(manifest['sample'].values(),[])
        await batch(root,diagnostic,session,budget,writer,stop)
        if stop.is_set(): return
        outcomes={k:load(root/'outcomes'/f'{k}.json') for k in diagnostic}
        gates={kind:gate({k:v for k,v in manifest['controls'].items() if k.startswith(kind+'-')},outcomes)
               for kind in COUNTS}
        write_json(root/'diagnostic.json',dict(gates=gates,sample=manifest['sample'],
            outcomes_sha256={k:file_hash(root/'outcomes'/f'{k}.json') for k in diagnostic},
            admission_authorized=False))
        # One bounded independent inspection of the random sample, not a permanent row gate.
        eligible=[k for k,g in gates.items() if g['passed']]
        deadline=time.monotonic()+1800
        while eligible and not (root/'sample-review.json').exists() and not stop.is_set() and time.monotonic()<deadline:
            write_json(root/'progress.json',dict(phase='awaiting_sample_inspection',eligible=eligible,time=time.time()))
            await asyncio.sleep(5)
        approval=load(root/'sample-review.json') if (root/'sample-review.json').exists() else {}
        approved=[]
        if approval.get('diagnostic_sha256')==file_hash(root/'diagnostic.json'):
            approved=[k for k in eligible if approval.get('groups',{}).get(k,{}).get('false_keeps')==[]
                      and approval['groups'][k].get('reviewed_ids')==manifest['sample'][k]]
        for kind in approved:
            verify(root,full=False)
            with closing(readonly(root/'catalog.sqlite')) as db:
                keys=[k for k, in db.execute('SELECT id FROM items WHERE kind=? ORDER BY id',(kind,))]
            for offset in range(0,len(keys),256):
                if stop.is_set(): break
                await batch(root,keys[offset:offset+256],session,budget,writer,stop)
                write_json(root/'progress.json',dict(phase='full_reaudit',kind=kind,
                    visited=min(offset+256,len(keys)),total=len(keys),time=time.time()))
        verify(root,full=False)
        counts=Counter()
        for p in (root/'outcomes').glob('*.json'):
            row=load(p); counts[p.name.split('-')[0]+':'+row.get('decision',{}).get('verdict',row['status'])]+=1
        write_json(root/'complete.json',dict(counts=dict(counts),approved_groups=approved,gates=gates,
            drained=stop.is_set(),admission_authorized=False,source_holds_preserved=True))


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('command',choices=['prepare','run','verify'])
    p.add_argument('--root',type=Path,required=True); a=p.parse_args()
    with lock(Path(str(a.root)+'.lock')):
        if a.command=='prepare': print(json.dumps(prepare(a.root)['counts']))
        elif a.command=='verify': print(json.dumps(verify(a.root)['counts']))
        else: asyncio.run(run(a.root))


if __name__=='__main__': main()
