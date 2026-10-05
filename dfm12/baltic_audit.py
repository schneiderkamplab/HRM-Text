"""Native-template preflight and immutable, transactionally queued Baltic audits."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path

from .baltic_sources_cpu import ROOT, renderer
from .io import atomic, digest, file_hash, load, lock, rows, write_json
from .jobs import Queue, audit_payload
from .records import validate_messages

MODEL = 'google/gemma-4-26B-A4B-it'


def preflight(job):
    component,path,output = job
    path,output=Path(path),Path(output)
    with lock(output/'.lock'):
        sha=file_hash(path)
        receipt=output/'receipt.json'
        if receipt.exists():
            result=load(receipt)
            if result['input_sha256']!=sha or file_hash(output/'candidates.jsonl')!=result['sha256']:
                raise ValueError('Sealed audit inputs changed: '+component)
            return result
        render=renderer()
        counts=Counter()
        from scripts.tokenize_chat_template import render as chat_render
        with atomic(output/'candidates.jsonl') as out, atomic(output/'rejected.jsonl') as rejected:
            for row in rows(path):
                counts['input']+=1
                row.setdefault('task','instruction')
                row['component']=component
                try:
                    validate_messages(row['messages'])
                    tokens=render.count(row['messages'])
                    if row.get('reverse_messages'):
                        validate_messages(row['reverse_messages'])
                        tokens+=render.count(row['reverse_messages'])
                    row['rendered_tokens']=tokens
                    row['admission_authorized']=False
                    payload=audit_payload(row,MODEL)
                    prompt=chat_render(render.template,payload['request']['messages'],[],True,False)
                    request_tokens=len(render.tokenizer.encode(prompt,add_special_tokens=False).ids)
                    if request_tokens+1024>32768:
                        raise ValueError('audit_context_over_32768')
                except ValueError as exc:
                    counts['rejected:'+str(exc)]+=1
                    rejected.write(json.dumps(dict(id=row['id'],reason=str(exc)),ensure_ascii=False)+'\n')
                    continue
                out.write(json.dumps(row,ensure_ascii=False)+'\n')
                counts['ready']+=1
                counts['max_audit_input_tokens']=max(counts['max_audit_input_tokens'],request_tokens)
        result=dict(component=component,path=str((output/'candidates.jsonl').resolve()),
            input=str(path.resolve()),input_sha256=sha,sha256=file_hash(output/'candidates.jsonl'),
            counts=dict(counts),student_context=4096,audit_context=32768,model=MODEL,
            audit_status='pending',tokenizer_info=render.info,
            template_sha256=file_hash(render.info['chat_template_path']),
            tokenizer_sha256=file_hash(render.info['tokenizer_path']))
        write_json(receipt,result)
        print('PREFLIGHT',component,dict(counts),flush=True)
        return result


def discover(root,stage):
    components=[]
    if stage in ('instructions','all'):
        for receipt in sorted((root/'receipts').glob('*-converted.json')):
            d=load(receipt)
            components.append((d['name'],Path(d['output'])))
        components.append(('latvian-p3',root/'p3/candidates.jsonl'))
        if (root/'euroblocks/receipt.json').exists():
            components.append(('baltic-euroblocks',root/'euroblocks/candidates.jsonl'))
    if stage in ('transforms','all'):
        for source in load(root/'transforms/manifest.json')['sources']:
            components.append(('transform-'+source['source'],root/'transforms'/source['source']/'candidates.jsonl'))
    if stage in ('translations','all'):
        requested={'-'.join(x) for x in load(root/'translations/config.json')['requested_pairs']}
        for folder,prefix in [('translations','direct'),('institutional-translations','institutional'),('pivots','pivot')]:
            for receipt in sorted((root/folder/'candidates').glob('*/receipt.json')):
                pair=receipt.parent.name.removeprefix('opus-')
                if pair in requested:
                    components.append((prefix+'-'+pair,receipt.parent/'candidates.jsonl'))
    if not components:
        raise ValueError('No components')
    return components


def prepare(root,stage,workers):
    components=discover(root,stage)
    # Large OPUS files must not serialize preflight onto one CPU per pair.
    if stage=='translations':
        expanded=[]
        for name,path in components:
            directory=root/'audit-chunks'/name
            receipt=directory/'receipt.json'
            sha=file_hash(path)
            if receipt.exists():
                meta=load(receipt)
                if meta['input_sha256']!=sha:
                    raise ValueError('Changed chunk input')
            else:
                chunks=[]
                iterator=iter(rows(path))
                from itertools import islice
                while batch:=list(islice(iterator,5000)):
                    part=directory/f'{len(chunks):05d}.jsonl'
                    with atomic(part) as out:
                        for row in batch:
                            out.write(json.dumps(row,ensure_ascii=False)+'\n')
                    chunks.append(dict(path=str(part),sha256=file_hash(part)))
                meta=dict(input_sha256=sha,chunks=chunks)
                write_json(receipt,meta)
            for i,part in enumerate(meta['chunks']):
                if file_hash(part['path'])!=part['sha256']:
                    raise ValueError('Chunk changed')
                expanded.append((name+f'-part{i:05d}',Path(part['path'])))
        components=expanded
    jobs=[(name,str(path),str(root/'audit-ready'/name)) for name,path in components]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        result=list(pool.map(preflight,jobs))
    write_json(root/'audit-ready'/f'{stage}-manifest.json',result)


def queue(root):
    with lock(root/'audit/.prepare.lock'):
        manifests=[root/'audit-ready'/f'{s}-manifest.json' for s in ('instructions','transforms','translations')]
        components=[entry for m in manifests for entry in load(m)]
        q=Queue(root/'audit/jobs.sqlite')
        try:
            # Candidate/job hash indexes outgrow SQLite's default 2 MiB cache.
            q.db.execute('PRAGMA cache_size=-524288')
            q.db.execute('CREATE TABLE IF NOT EXISTS candidate_ids (id TEXT PRIMARY KEY, content_sha256 TEXT NOT NULL)')
            n=0
            coverage=[]
            for entry in components:
                path=Path(entry['path'])
                if file_hash(path)!=entry['sha256']:
                    raise ValueError('Candidate changed: '+str(path))
                q.db.execute('BEGIN IMMEDIATE')
                try:
                    checked=0
                    for row in rows(path):
                        fingerprint=digest([row['messages'],row.get('reverse_messages')])
                        old=q.db.execute('SELECT content_sha256 FROM candidate_ids WHERE id=?',(row['id'],)).fetchone()
                        if old:
                            if old[0]!=fingerprint:
                                raise ValueError('Candidate ID collision with different messages')
                        # IDs identify content, not component-specific audit context.
                        # INSERT OR IGNORE preserves existing results and attempts.
                        before=q.db.total_changes
                        q.add('audit',audit_payload(row,MODEL))
                        n+=q.db.total_changes-before
                        if not old:
                            q.db.execute('INSERT INTO candidate_ids VALUES (?,?)',(row['id'],fingerprint))
                        checked+=1
                        if checked%1000==0:
                            q.db.execute('COMMIT')
                            q.db.execute('BEGIN IMMEDIATE')
                    q.db.execute('COMMIT')
                    coverage.append(dict(component=entry['component'],rows_checked=checked,
                                         exact_payload_jobs_ensured=checked))
                except BaseException:
                    q.db.execute('ROLLBACK')
                    raise
                print('QUEUED',entry['component'],n,flush=True)
            write_json(root/'audit/manifest.json',dict(components=components,queued=q.status(),
                preflight_manifests={str(m):file_hash(m) for m in manifests},
                audit_model=MODEL,worker='dfm12.jobs.run_clients',new_jobs=n,
                component_job_coverage=coverage,
                total_candidate_ids=q.db.execute('SELECT COUNT(*) FROM candidate_ids').fetchone()[0],
                total_unique_jobs=q.db.execute("SELECT COUNT(*) FROM jobs WHERE stage='audit'").fetchone()[0],
                training_ready=False,gpu_started=False,context_required=32768))
        finally:
            q.close()


def index_queue(path):
    q=Queue(path)
    try:
        q.db.execute('PRAGMA cache_size=-524288')
        q.db.execute('CREATE INDEX IF NOT EXISTS baltic_job_claim ON jobs(stage,status)')
        q.db.execute('CREATE INDEX IF NOT EXISTS baltic_job_expiry ON jobs(status,lease)')
    finally:
        q.close()


def finalize(root):
    with lock(root/'audit/.prepare.lock'):
        return _finalize(root)


def _finalize(root):
    from .baltic_synthetic_campaign import verify
    report=load(root/'audit/manifest.json')
    for path,sha in report['preflight_manifests'].items():
        if file_hash(path)!=sha:
            raise ValueError('Preflight changed since queue assembly: '+path)
    if any(r['status']!='pending' for r in report['queued']):
        raise ValueError('Audit already started; do not restamp CPU readiness')
    cfg=load(root/'translations/config.json')
    coverage={ '-'.join(p):0 for p in cfg['requested_pairs'] }
    for folder in ('translations','institutional-translations','pivots'):
        for receipt in (root/folder/'candidates').glob('*/receipt.json'):
            pair=receipt.parent.name.removeprefix('opus-')
            if pair in coverage:
                coverage[pair]+=load(receipt)['counts'].get('candidate_pairs',0)
    if any(n==0 for n in coverage.values()):
        raise ValueError('Uncovered pair(s): '+str([p for p,n in coverage.items() if not n]))
    ready_coverage={p:0 for p in coverage}
    for entry in report['components']:
        for prefix in ('direct-','institutional-','pivot-'):
            if entry['component'].startswith(prefix):
                pair=entry['component'][len(prefix):].split('-part')[0]
                ready_coverage[pair]+=entry['counts'].get('ready',0)
    if any(n==0 for n in ready_coverage.values()):
        raise ValueError('Pair(s) missing audit-ready candidates: '+str([p for p,n in ready_coverage.items() if not n]))
    index_queue(root/'audit/jobs.sqlite')
    verify(root/'synthetic')
    from scripts.prepare_dfm13_baltic import register,CONFIG
    register(root.resolve(),load(CONFIG))
    registry=Path('config/dfm13_sources.json')
    with lock(registry.with_suffix('.lock')):
        data=load(registry)
        data['preparations']['baltic'].update(status='cpu_ready_for_audit',
            audit_manifest=str((root/'audit/manifest.json').resolve()),
            audit_manifest_sha256=file_hash(root/'audit/manifest.json'),
            unique_audit_jobs=report['total_unique_jobs'],training_ready=False)
        write_json(registry,data)
    holds={
        'baltic_lt_summary':'NewGenLTU terms and medical/privacy review before export',
        'baltic_lt_blkt':'NewGenLTU terms and source provenance before export',
        'finepdfs':'Underlying document rights; database license alone is not blanket text licensing',
        'latvian_p3':'Retain original constituent rights; no blanket license asserted',
        'Europarl':'Original Parliament terms retained; redistribution review before publication',
    }
    status=dict(status='cpu_ready_for_audit',unique_audit_jobs=report['total_unique_jobs'],
        translation_pair_coverage=coverage,translation_budget=load(root/'translations/token-budgets.json'),
        translation_pair_audit_ready=ready_coverage,
        synthetic_generation_target=140000,synthetic_calibration=load(root/'calibration/manifest.json'),
        export_holds=holds,gpu_started=False,training_ready=False,final_sampling=False,
        audit_manifest=str((root/'audit/manifest.json').resolve()))
    write_json(root/'readiness.json',status)
    print(json.dumps(status,indent=2),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=['instructions','transforms','translations','all','queue','finalize'])
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--workers',type=int,default=16)
    a=p.parse_args()
    if a.stage=='finalize':
        finalize(a.root)
    elif a.stage=='queue':
        queue(a.root)
    else:
        prepare(a.root,a.stage,a.workers)


if __name__=='__main__':
    main()
