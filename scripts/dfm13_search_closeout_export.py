"""Local accepted-quality Search closeout; rights gate prevents deployment/upload."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import jinja2
from tokenizers import Tokenizer
from scripts import dfm13_search_training_contract as contract
from scripts import dfm13_search_salvage32 as run

ROOT=Path('exports_dfm13/searcharena-conservative-20261001')
FINAL=Path('data/dfm13/search-salvage-final-20261001/inventory.json')
ACCEPT={'retained_supported','retained_creative','new_supported_scoped'}


def select_version(row):
    if 'existing_manual_versions' in row:
        versions=row['existing_manual_versions']
        if not versions:raise ValueError('missing reviewed version')
        return Path(versions[0]['candidate']),versions[0]['candidate_sha256']
    return Path(row['candidate']),row['candidate_sha256']


def verify_observations(row,calls,cached):
    matches=[]
    for index,call in calls.items():
        observed=run.base.strict_json(row['messages'][index]['content'])
        eligible=[c for c in cached if call['name']!='search' or c['query']==call['arguments']['query']]
        for page in observed.get('results',[]):
            body=page.get('body',page.get('content',''))
            if not isinstance(body,str) or not body.strip():continue
            choices=[(c,p) for c in eligible for p in c['payload'].get('data',[]) if p.get('url')==page.get('url')]
            paragraphs=[s for s in body.split('\n\n') if s.strip()]
            found=[]
            for c,p in choices:
                full=p.get('content','')
                if isinstance(full,str) and all(s in full for s in paragraphs):
                    found.append(dict(raw_sha256=c['sha256'],url=p['url'],query=c['query'],
                        spans=[dict(start=full.index(s),end=full.index(s)+len(s),text_sha256=hashlib.sha256(s.encode()).hexdigest()) for s in paragraphs]))
            if not found:raise ValueError('unbound cached observation: '+str(page.get('url')))
            matches.append(dict(message_index=index,body_sha256=hashlib.sha256(body.encode()).hexdigest(),matches=found))
    if not matches:raise ValueError('no verified observations')
    return matches


def build(root=ROOT):
    if root.exists():raise ValueError('immutable export root exists')
    final=run.prior.read(FINAL)
    info=run.prior.read(contract.METADATA)['tokenizer_info']
    tokenizer=Tokenizer.from_file(info['tokenizer_path'])
    template=jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
    db=sqlite3.connect('file:'+str(run.base.CAMPAIGN/'cache.sqlite')+'?mode=ro',uri=True)
    cache={}
    for owner,query,raw,provenance in db.execute('SELECT owner,query,raw,provenance FROM searches WHERE status="done"'):
        cache.setdefault(owner,[]).append(dict(query=query,payload=json.loads(raw),sha256=hashlib.sha256(raw).hexdigest(),provenance=json.loads(provenance)))
    db.close()
    accepted=[];audits=[];nontraining=[];seen=set();ids=set()
    for row in final['rows']:
        if row['id'] in ids:raise ValueError('duplicate task ID')
        ids.add(row['id'])
        if row['lane'] not in ACCEPT:
            nontraining.append(row);continue
        path,sha=select_version(row)
        if run.base.file_hash(path)!=sha:raise ValueError('candidate changed')
        candidate=run.prior.read(path)
        try:
            original=next(m['content'] for m in candidate['messages'] if m['role']=='user')
            sample=candidate['provenance'].get('sample',candidate['provenance'])
            if sample.get('prompt')!=original:raise ValueError('original prompt provenance mismatch')
            checked,calls=contract.strict_row(candidate,original)
            if checked['target_message_indices']!=[len(checked['messages'])-1]:raise ValueError('final-only target required')
            evidence=verify_observations(checked,calls,cache.get(row['id'],[]))
            renders=contract.rendered_targets(checked,tokenizer,template,info,4096)
            if not all(r['fits_student_context'] and r['target_kind']=='final_answer' and r['target_tokens']>0 for r in renders):raise ValueError('context/mask failure')
            fingerprint=contract.fingerprint(checked)
            if fingerprint in seen:raise ValueError('duplicate training content')
            seen.add(fingerprint)
            view=next(contract.student_views(checked))
            accepted.append(dict(id=row['id'],**view))
            audits.append(dict(id=row['id'],candidate_path=str(path),candidate_sha256=sha,original_candidate=candidate,
                lane=row['lane'],evidence=evidence,rendering=renders,fingerprint=fingerprint,
                rights_status='unresolved_third_party_page_redistribution_and_source_snapshot_license',
                source_usage=[dict(query=c['query'],raw_sha256=c['sha256'],provenance=c['provenance']) for c in cache[row['id']]],
                quality_accepted=True,training_admission=False))
        except ValueError as error:
            nontraining.append(dict(row,lane='export_validation_hold',validation_error=str(error)))
    def gz(path,rows):
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('wb') as raw:
            with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as stream:
                for row in rows:stream.write((json.dumps(row,ensure_ascii=False)+'\n').encode())
    gz(root/'data/train.jsonl.gz',accepted)
    gz(root/'metadata/accepted-audits.jsonl.gz',audits)
    for lane in ('partial','held','reject'):
        selected=[r for r in nontraining if ('partial' in r['lane'] if lane=='partial' else r['lane']=='rejected_final' if lane=='reject' else 'partial' not in r['lane'] and r['lane']!='rejected_final')]
        run.base.atomic(root/'nontraining'/(lane+'.json'),selected)
    pins={str(p):run.base.file_hash(p) for p in (FINAL,run.INVENTORY,Path(__file__),Path(contract.__file__),contract.METADATA,Path(info['tokenizer_path']),Path(info['chat_template_path']),Path('dataset_new.py'))}
    manifest=dict(quality_accepted_rows=len(accepted),nontraining_counts=dict(Counter(r['lane'] for r in nontraining)),
        total_reconciled_ids=len(ids),target_tokens=sum(a['rendering'][0]['target_tokens'] for a in audits),
        rendered_tokens=sum(a['rendering'][0]['total_tokens'] for a in audits),context_limit=4096,
        upload_ready=False,training_ready=False,canonical_repository=None,license=None,
        blockers=['No validated canonical destination repository','Source snapshot has no retained README/LICENSE in the downloaded directory',
                  'Third-party cached tool-observation redistribution rights not established; public access does not establish a license'],
        user_authorization='Conservative local accepted-quality export requested; no admission of partial/held/rejected rows',
        target_policy='final assistant answer only; all controller-authored calls, user messages and tool results masked',
        paid_calls=0,files={str(p.relative_to(root)):run.base.file_hash(p) for p in root.rglob('*') if p.is_file()},pins=pins)
    run.base.atomic(root/'metadata/manifest.json',manifest)
    print(json.dumps(manifest,ensure_ascii=False))


def validate(root=ROOT):
    manifest=run.prior.read(root/'metadata/manifest.json')
    for path,sha in manifest['files'].items():
        if run.base.file_hash(root/path)!=sha:raise ValueError('export file changed')
    for path,sha in manifest['pins'].items():
        if run.base.file_hash(Path(path))!=sha:raise ValueError('source pin changed')
    with gzip.open(root/'data/train.jsonl.gz','rt') as stream:rows=[json.loads(s) for s in stream]
    assert len(rows)==manifest['quality_accepted_rows']
    assert len({r['id'] for r in rows})==len(rows)
    assert all(set(r)=={'id','messages','tools','target_message_index'} and r['target_message_index']==len(r['messages'])-1 for r in rows)
    nontraining=[r for p in (root/'nontraining').glob('*.json') for r in run.prior.read(p)]
    assert not ({r['id'] for r in rows}&{r['id'] for r in nontraining})
    assert len(rows)+len(nontraining)==manifest['total_reconciled_ids']==32
    print('Validated accepted-only separation, hashes, final-target selectors and 32 unique task dispositions')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['build','validate']);args=parser.parse_args()
    build() if args.command=='build' else validate()
